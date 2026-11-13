import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Bot,
  Camera,
  ChevronRight,
  FileArchive,
  FileText,
  HardHat,
  History,
  LayoutDashboard,
  LogOut,
  Mic,
  Package,
  Paperclip,
  Scale,
  Settings,
  ShieldCheck,
  Square,
  Upload,
  Users,
  X,
} from "lucide-react";
import "./App.css";
import { audioToWav } from "./media";
import ErrorPage from "./components/ErrorPage";
import { accessErrorForStatus, ApiError, isWorkspaceRole } from "./errorStates";
import type { ErrorKind } from "./errorStates";

const API_BASE = import.meta.env.DEV
  ? import.meta.env.VITE_API_BASE_URL ?? "/api/v1"
  : "/api/v1";
const SESSION_KEY = "ai-interface-session";
const ROLE_KEY = "ai-interface-role";
const SESSION_LENGTH = 7 * 24 * 60 * 60 * 1000;
const MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024;
const MAX_CHAT_ATTACHMENTS = 2;

type Role = "engineer" | "customer";
type AttachmentKind = "image" | "audio" | "document";
type Citation = {
  source_id?: string;
  page?: number | null;
  excerpt?: string | null;
  title?: string;
  url?: string;
  snippet?: string;
};
type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  warnings?: string[];
  confidence?: string;
  tool_executed?: string;
  media_summary?: string;
  attachments?: string[];
  comparison?: ComparisonResult;
};
type ComparisonResult = {
  products: { id: number; [field: string]: unknown }[];
  fields: string[];
  different_fields: string[];
};
type Conversation = { id: string; title: string; status?: string; updatedAt?: string };
type StoredMessage = Pick<Message, "id" | "role" | "content"> & {
  created_at: string;
  metadata?: Pick<Message, "citations" | "warnings" | "confidence" | "tool_executed" | "attachments" | "comparison" | "media_summary">;
};
type ChatAttachment = {
  key: string;
  file: File;
  kind: AttachmentKind;
  mediaId?: string;
};
type UploadedMedia = { id: string; filename: string; kind: AttachmentKind };
type Session = { token: string; expiresAt: number };
type Product = {
  id: number;
  category: string;
  name: string;
  model_number: string;
  specifications: string;
  price_ksh: number;
};

function formatPrice(priceKsh: number): string {
  return new Intl.NumberFormat("en-KE", {
    style: "currency",
    currency: "KES",
    maximumFractionDigits: 0,
  }).format(priceKsh);
}

function productImage(category: string): string {
  const normalized = category.toLowerCase();
  if (normalized.includes("generator")) return "/products/generator.svg";
  if (normalized.includes("transformer")) return "/products/transformer.svg";
  return "/products/inverter.svg";
}

function attachmentKind(file: File): AttachmentKind | null {
  const type = file.type.toLowerCase().split(";", 1)[0];
  if (["image/jpeg", "image/png", "image/webp"].includes(type)) return "image";
  if (["audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg", "audio/webm", "audio/mp4"].includes(type)) return "audio";
  if ([
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/csv",
    "text/markdown",
    "text/plain",
  ].includes(type)) return "document";
  if (type && type !== "application/octet-stream") return null;

  const extension = file.name.toLowerCase().split(".").pop();
  if (["jpg", "jpeg", "png", "webp"].includes(extension ?? "")) return "image";
  if (["wav", "mp3", "webm", "m4a"].includes(extension ?? "")) return "audio";
  if (["pdf", "docx", "txt", "md", "csv"].includes(extension ?? "")) return "document";
  return null;
}

async function api<T>(
  path: string,
  token?: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
    throw new ApiError(response.status, typeof detail === "string" ? detail : `Request failed (${response.status})`);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function readSession(): Session | null {
  try {
    const session = JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    if (session?.token && session.expiresAt > Date.now()) return session;
  } catch {
    // Invalid saved session; start signed out.
  }
  localStorage.removeItem(SESSION_KEY);
  return null;
}

function ChatMessages({ messages, busy }: { messages: Message[]; busy: boolean }) {
  return (
    <div className="chat-messages" role="log" aria-label="Conversation">
      {messages.map((message) => (
        <article className="chat-message" key={message.id}>
          <b>{message.role === "user" ? "You" : "Copilot"}</b>
          <p>{message.comparison
            ? message.content.split("\n").filter((line) => !line.trimStart().startsWith("|")).join("\n")
            : message.content}</p>
          {message.comparison && <ComparisonTable comparison={message.comparison} />}
          {message.media_summary && <p>{message.media_summary}</p>}
          {message.attachments?.length ? <p>Attachments: {message.attachments.join(", ")}</p> : null}
          {message.warnings && message.warnings.length > 0 && (
            <ul className="chat-warnings" aria-label="Answer warnings">
              {message.warnings.map((warning, index) => <li key={index}>{warning}</li>)}
            </ul>
          )}
          {message.confidence && <p className="panel-muted">Confidence: {message.confidence}</p>}
          {message.tool_executed && (
            <details className="chat-sources">
              <summary>Tool trace</summary>
              <p>{message.tool_executed}</p>
            </details>
          )}
          {message.citations && message.citations.length > 0 && (
            <details className="chat-sources">
              <summary>Sources ({message.citations.length})</summary>
              <ul>
                {message.citations.map((citation, index) => (
                  <li key={`${citation.source_id}-${index}`}>
                    <b>{citation.source_id || citation.title || "Source"}</b>
                    {citation.page != null && <span> · Page {citation.page}</span>}
                    {(citation.excerpt || citation.snippet) && <p>{citation.excerpt || citation.snippet}</p>}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </article>
      ))}
      {busy && <p role="status">Waiting for the assistant…</p>}
    </div>
  );
}

function ComparisonTable({ comparison }: { comparison: ComparisonResult }) {
  const labels: Record<string, string> = {
    id: "Catalogue ID", name: "Product", category: "Category", model_number: "Model",
    specifications: "Stored specifications", price_ksh: "Catalogue price (KES)",
  };
  function cell(field: string, value: unknown): string {
    if (value == null || value === "") return "Not available";
    if (field === "price_ksh" && typeof value === "number" && Number.isFinite(value)) return formatPrice(value);
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
    return "Not available";
  }
  return (
    <div className="chat-comparison" role="region" aria-label="Catalogue comparison table" tabIndex={0}>
      <table>
        <caption>Synthetic demo catalogue comparison. Highlighted rows contain different stored values.</caption>
        <thead><tr><th scope="col">Field</th>{comparison.products.map((product) => (
          <th scope="col" key={product.id}>{cell("model_number", product.model_number)}</th>
        ))}</tr></thead>
        <tbody>{comparison.fields.map((field) => {
          const differs = comparison.different_fields.includes(field);
          return <tr key={field} className={differs ? "comparison-difference" : undefined}>
            <th scope="row">{labels[field] || field}{differs && <span className="comparison-marker">Different</span>}</th>
            {comparison.products.map((product) => <td key={product.id}>{cell(field, product[field])}</td>)}
          </tr>;
        })}</tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(readSession);
  const [role, setRole] = useState<Role | null>(null);
  const [verifiedToken, setVerifiedToken] = useState<string | null>(null);
  const [accessError, setAccessError] = useState<ErrorKind | null>(null);
  const [selectedRole, setSelectedRole] = useState<Role>("engineer");
  const [activeNav, setActiveNav] = useState(window.location.pathname.replace(/\/+$/, "") === "/chat" ? "Chat Assistant" : "Dashboard");
  const [productPage, setProductPage] = useState(0);
  const [products, setProducts] = useState<Product[]>([]);
  const [catalogLoaded, setCatalogLoaded] = useState(false);
  const [catalogError, setCatalogError] = useState("");
  const [username, setUsername] = useState("engineer@jenga.com");
  const [password, setPassword] = useState("engineer123");
  const [loginError, setLoginError] = useState("");
  const [busy, setBusy] = useState(false);

  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [files, setFiles] = useState<ChatAttachment[]>([]);
  const [allowExternalProcessing, setAllowExternalProcessing] = useState(false);
  const [recording, setRecording] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const audioStream = useRef<MediaStream | null>(null);
  const audioChunks = useRef<Blob[]>([]);
  const requestController = useRef<AbortController | null>(null);

  const logout = useCallback(() => {
    requestController.current?.abort();
    requestController.current = null;
    setBusy(false);
    if (recorder.current) {
      recorder.current.onstop = null;
      if (recorder.current.state !== "inactive") recorder.current.stop();
      recorder.current.stream.getTracks().forEach((track) => track.stop());
    }
    setRecording(false);
    setFiles([]);
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(ROLE_KEY);
    setSession(null);
    setRole(null);
    setVerifiedToken(null);
    setAccessError(null);
    setError("");
    setMessages([]);
    setConversationId("");
    setChatLoading(false);
    setFiles([]);
    setProducts([]);
    setCatalogLoaded(false);
    setCatalogError("");
  }, []);

  const handleRequestError = useCallback((failure: unknown) => {
    if (!(failure instanceof ApiError)) return;
    const kind = accessErrorForStatus(failure.status);
    if (!kind) return;
    if (kind === "session_expired") logout();
    setAccessError(kind);
  }, [logout]);

  useEffect(() => {
    if (!session) return;
    const controller = new AbortController();
    api<{ role?: unknown; username?: unknown }>("/auth/me", session.token, { signal: controller.signal })
      .then((identity) => {
        if (controller.signal.aborted) return;
        const trustedRole = isWorkspaceRole(identity.role) ? identity.role : null;
        setRole(trustedRole);
        setVerifiedToken(session.token);
        if (typeof identity.username === "string") setUsername(identity.username);
        if (trustedRole) localStorage.setItem(ROLE_KEY, trustedRole);
        else localStorage.removeItem(ROLE_KEY);
      })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return;
        if (failure instanceof ApiError && accessErrorForStatus(failure.status)) handleRequestError(failure);
        else setAccessError("unavailable");
      });
    return () => controller.abort();
  }, [session, handleRequestError]);
  useEffect(() => () => {
    const activeRecorder = recorder.current;
    if (activeRecorder?.state === "recording") {
      activeRecorder.onstop = null;
      activeRecorder.stop();
    }
    audioStream.current?.getTracks().forEach((track) => track.stop());
  }, []);

  useEffect(() => {
    if (!session) return;
    const remaining = session.expiresAt - Date.now();
    const timer = window.setTimeout(() => {
      logout();
      setAccessError("session_expired");
    }, Math.max(remaining, 0));
    return () => window.clearTimeout(timer);
  }, [session, logout]);

  useEffect(() => {
    if (!session || !role || activeNav !== "Chat Assistant" || conversationId) return;
    let active = true;
    const accessToken = session.token;

    async function loadExistingConversation() {
      setChatLoading(true);
      try {
        const conversations = await api<Conversation[]>("/conversations", accessToken);
        for (const conversation of conversations) {
          const history = await api<StoredMessage[]>(
            `/conversations/${encodeURIComponent(conversation.id)}/messages`,
            accessToken,
          );
          if (!active) return;
          if (history.length === 0 || conversation.status === "finished") continue;

          setConversationId(conversation.id);
          setMessages(history.map(({ id, role: messageRole, content, metadata }) => ({
            id,
            role: messageRole,
            content,
            ...metadata,
          })));
          break;
        }
      } catch (e) {
        if (active) {
          handleRequestError(e);
          setError(e instanceof Error ? e.message : "Could not load your conversation.");
        }
      } finally {
        if (active) setChatLoading(false);
      }
    }

    void loadExistingConversation();
    return () => {
      active = false;
    };
  }, [session, role, activeNav, conversationId, handleRequestError]);

  useEffect(() => {
    if (!session || !role) return;
    let active = true;
    api<Product[]>("/catalogue/products", session.token)
      .then((catalogue) => {
        if (active) {
          setProducts(catalogue);
          setCatalogError("");
          setCatalogLoaded(true);
        }
      })
      .catch((e: unknown) => {
        if (active) {
          handleRequestError(e);
          setCatalogError(
            e instanceof Error ? e.message : "Product catalogue is unavailable.",
          );
          setCatalogLoaded(true);
        }
      })
    return () => {
      active = false;
    };
  }, [session, role, handleRequestError]);

  async function signIn(event: React.FormEvent) {
    event.preventDefault();
    setLoginError("");
    setBusy(true);
    try {
      // The demo credentials are prefilled; the backend remains responsible for issuing the JWT.
      const result = await api<{ access_token: string }>("/auth/login", undefined, {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      const nextSession = {
        token: result.access_token,
        expiresAt: Date.now() + SESSION_LENGTH,
      };
      localStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
      localStorage.removeItem(ROLE_KEY);
      setProducts([]);
      setCatalogLoaded(false);
      setCatalogError("");
      setConversationId("");
      setMessages([]);
      setChatLoading(false);
      setFiles([]);
      setSession(nextSession);
      setRole(null);
      setVerifiedToken(null);
      setAccessError(null);
    } catch (e) {
      setLoginError(e instanceof Error ? e.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  function openChat() {
    setActiveNav("Chat Assistant");
    setError("");
  }

  async function signInAgain() {
    const token = session?.token;
    // Stop active requests and clear protected state before awaiting the server.
    logout();
    try {
      if (token) await api<void>("/auth/logout", token, { method: "POST" });
    } catch {
      setLoginError("Signed out on this device. Server session revocation could not be confirmed; retry when connected.");
    }
  }

  function chooseRole(nextRole: Role) {
    setSelectedRole(nextRole);
    if (nextRole === "customer") {
      setUsername("customer@jenga.com");
      setPassword("customer123");
    } else {
      setUsername("engineer@jenga.com");
      setPassword("engineer123");
    }
  }

  function addFiles(selected: FileList | File[]) {
    const incoming = Array.from(selected);
    const accepted: ChatAttachment[] = [];
    let validationError = "";
    for (const file of incoming) {
      const kind = attachmentKind(file);
      if (!kind) {
        validationError ||= `${file.name}: unsupported format. Use an image, PDF, DOCX, TXT, Markdown, CSV, or supported audio file.`;
        continue;
      }
      if (file.size > MAX_ATTACHMENT_BYTES) {
        validationError ||= `${file.name}: files must be 8 MiB or smaller.`;
        continue;
      }
      accepted.push({ key: crypto.randomUUID(), file, kind });
    }
    const remaining = Math.max(MAX_CHAT_ATTACHMENTS - files.length, 0);
    if (accepted.length > remaining) {
      validationError ||= "A chat message can include up to two attachments.";
    }
    setFiles((current) => [
      ...current,
      ...accepted.slice(0, Math.max(MAX_CHAT_ATTACHMENTS - current.length, 0)),
    ]);
    if (accepted.length > 0) setAllowExternalProcessing(false);
    setError(validationError);
  }

  async function removeAttachment(attachment: ChatAttachment) {
    if (attachment.mediaId && session) {
      try {
        await api<void>(`/media/${encodeURIComponent(attachment.mediaId)}`, session.token, {
          method: "DELETE",
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not remove the uploaded attachment.");
        return;
      }
    }
    setFiles((current) => current.filter((item) => item.key !== attachment.key));
    setAllowExternalProcessing(false);
  }

  async function toggleRecording() {
    if (busy) return;
    if (recording) {
      recorder.current?.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("This browser does not support microphone recording.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStream.current = stream;
      const preferredType = ["audio/webm", "audio/mp4", "audio/wav"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      const mediaRecorder = new MediaRecorder(
        stream,
        preferredType ? { mimeType: preferredType } : undefined,
      );
      recorder.current = mediaRecorder;
      audioChunks.current = [];
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size) audioChunks.current.push(event.data);
      };
      mediaRecorder.onstop = () => {
        window.clearTimeout(stopTimer);
        setRecording(false);
        const contentType = mediaRecorder.mimeType || "audio/webm";
        const audio = new File(
          [new Blob(audioChunks.current, { type: contentType })],
          `voice-message-${Date.now()}.${contentType === "audio/mp4" ? "m4a" : "webm"}`,
          { type: contentType },
        );
        addFiles([audio]);
        stream.getTracks().forEach((track) => track.stop());
        audioStream.current = null;
        recorder.current = null;
        setRecording(false);
      };
      mediaRecorder.start();
      const stopTimer = window.setTimeout(() => {
        if (mediaRecorder.state === "recording") mediaRecorder.stop();
      }, 60_000);
      setError("");
      setRecording(true);
    } catch (e) {
      setError(e instanceof Error ? `Microphone unavailable: ${e.message}` : "Microphone access was unavailable.");
    }
  }

  async function sendMessage(event?: React.FormEvent) {
    event?.preventDefault();
    if (!session || !role || busy || recording || chatLoading || (!prompt.trim() && files.length === 0)) return;
    if (files.some((item) => item.kind === "document") && !allowExternalProcessing) {
      setError("Confirm you are allowed to send these attachments to the configured AI service.");
      return;
    }
    const text = prompt.trim();
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text || "Photo / spoken question",
      attachments: files.map(({ file }) => file.name),
    };

    setMessages((current) => [...current, userMessage]);
    setError("");
    setBusy(true);

    const controller = new AbortController();
    requestController.current = controller;
    try {
      let activeConversationId = conversationId;
      if (!activeConversationId) {
        const conversation = await api<Conversation>("/conversations/current", session.token, {
          method: "POST",
          body: JSON.stringify({}),
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        activeConversationId = conversation.id;
        const history = await api<StoredMessage[]>(
          `/conversations/${encodeURIComponent(activeConversationId)}/messages`,
          session.token,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        setConversationId(activeConversationId);
        setMessages([
          ...history.map(({ id, role: messageRole, content, metadata }) => ({
            id,
            role: messageRole,
            content,
            ...metadata,
          })),
          userMessage,
        ]);
      }

      const result = await api<{
        answer: string;
        conversation_id?: string;
        citations?: Citation[];
        warnings?: string[];
        confidence?: string;
        tool_executed?: string;
        structured_results?: {
          comparison?: ComparisonResult;
          transcription?: { text: string } | null;
          identification?: { candidates: { model_number: string }[] } | null;
        };
      }>("/chat/query", session.token, {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          query: text || undefined,
          conversation_id: activeConversationId,
          media_ids: await Promise.all(files.map(async (attachment) => {
            if (attachment.mediaId) return attachment.mediaId;
            const form = new FormData();
            form.append("file", attachment.kind === "audio" && !allowExternalProcessing ? await audioToWav(attachment.file) : attachment.file);
            if (controller.signal.aborted) throw new DOMException("Aborted", "AbortError");
            const uploaded = await api<UploadedMedia>(
              `/media?kind=${attachment.kind}`,
              session.token,
              { method: "POST", body: form, signal: controller.signal },
            );
            setFiles((current) => current.map((item) =>
              item.key === attachment.key ? { ...item, mediaId: uploaded.id } : item,
            ));
            return uploaded.id;
          })),
          allow_external_processing: allowExternalProcessing,
        }),
      });

      if (controller.signal.aborted) return;
      if (result.conversation_id) setConversationId(result.conversation_id);
      setFiles([]);
      setAllowExternalProcessing(false);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: result.answer,
          citations: result.citations ?? [],
          warnings: result.warnings ?? [],
          confidence: result.confidence,
          tool_executed: result.tool_executed,
          comparison: result.structured_results?.comparison,
          media_summary: [
            result.structured_results?.transcription && `Heard: ${result.structured_results.transcription.text || "No speech transcribed"}`,
            result.structured_results?.identification && `Photo candidates: ${result.structured_results.identification.candidates.map((candidate) => candidate.model_number).join(", ") || "None identified"}`,
          ].filter(Boolean).join(" · "),
        },
      ]);
      setFiles([]);
      setPrompt("");

    } catch (e) {
      if (controller.signal.aborted) return;
      handleRequestError(e);
      setMessages((current) => current.filter((message) => message.id !== userMessage.id));
      setPrompt(text);
      setError(e instanceof Error ? e.message : "Message could not be sent.");
    } finally {
      if (requestController.current === controller) {
        requestController.current = null;
        setBusy(false);
      }
    }

  }

  const pageDetails: Record<string, { title: string; description: string }> = {
    "Chat Assistant": { title: "Chat Assistant", description: "Ask questions by text or voice, and analyze product photos and documents." },
    "Browse Products": { title: "Browse Products", description: "Explore equipment and find the right solution for your project." },
    Documents: { title: "Documents", description: "Source documents are not connected to the application yet." },
    "Compare Solutions": { title: "Compare Solutions", description: "Compare equipment options side by side before making a decision." },
    "Upload Media": { title: "Upload Media", description: "Add photos, documents, or voice notes directly to your account chat." },
    History: { title: "History", description: "Review your recent questions, comparisons, and saved recommendations." },
    Settings: { title: "Settings", description: "Manage your workspace preferences and assistant experience." },
  };
  const engineerOnlyPages = new Set<string>();
  const canAccessPage = (page: string) => role === "engineer" || !engineerOnlyPages.has(page);

  if (accessError) {
    return (
      <ErrorPage
        kind={accessError}
        onSignIn={signInAgain}
        onReturn={() => {
          if (accessError === "unavailable") window.location.reload();
          else if (!session || verifiedToken !== session.token) void signInAgain();
          else {
            setAccessError(null);
            setActiveNav("Dashboard");
          }
        }}
      />
    );
  }

  if (!session) {
    return (
      <main className="auth-page">
        <section className="auth-hero">
          <div className="brand-lockup">
            <span className="brand-mark">⚙</span>
            <span>Jenga Consultants<br /><b>Product Copilot</b></span>
          </div>
          <div className="auth-copy">
            <p className="eyebrow">INDUSTRIAL INTELLIGENCE, SIMPLIFIED</p>
            <h1>Your AI-Powered<br /><strong>Equipment Assistant</strong></h1>
            <p>Find the right industrial equipment, get expert answers, and access trusted documentation.</p>
            <div className="auth-benefits">
              <span><b>⚡</b>Instant<br />Answers</span>
              <span><b>✓</b>Trusted<br />Sources</span>
              <span><b>▥</b>Smarter<br />Decisions</span>
            </div>
          </div>
          <div className="hero-machine" aria-hidden="true">⚙</div>
        </section>
        <form
          onSubmit={signIn}
          className="auth-card"
        >
          <div className="auth-card-heading">
            <span className="lock-icon"><ShieldCheck size={24} /></span>
            <h2>Welcome Back</h2>
            <p>Sign in to access your AI assistant</p>
          </div>
          <label className="auth-field">
            <span><Users size={15} /> {selectedRole === "customer" ? "Customer account" : "Engineer account"}</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
          </label>
          <label className="auth-field">
            <span><ShieldCheck size={15} /> Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          <p className="role-label">Account type:</p>
          <div className="role-switcher">
            <button type="button" className={selectedRole === "engineer" ? "selected" : ""} onClick={() => chooseRole("engineer")}><HardHat size={16} /> Engineer</button>
            <button type="button" className={selectedRole === "customer" ? "selected" : ""} onClick={() => chooseRole("customer")}><Users size={16} /> Customer</button>
          </div>
          {loginError && <p className="login-error">{loginError}</p>}
          <button disabled={busy} className="auth-submit">{busy ? "Signing in…" : <>Sign In <ArrowUp size={16} /></>}</button>
          <div className="auth-divider"><span>or</span></div>
          <p className="auth-version">Jenga Consultants Product Copilot v1.0</p>
        </form>
      </main>
    );
  }

  if (verifiedToken !== session.token) {
    return (
      <main className="identity-check" role="status" aria-live="polite">
        <h1>Checking your workspace…</h1>
        <p>Confirming your account and access with the server.</p>
      </main>
    );
  }

  if (!role) return <ErrorPage kind="role_required" onSignIn={signInAgain} />;

  if (!canAccessPage(activeNav)) {
    return <ErrorPage kind="forbidden" onReturn={() => setActiveNav("Dashboard")} onSignIn={signInAgain} />;
  }

  return (
    <main className="dashboard-shell">
      <aside className="dashboard-sidebar">
        <div className="sidebar-brand"><span className="brand-mark">⚙</span><span>Jenga Consultants<br /><b>Product Copilot</b></span></div>
        <nav className="dashboard-nav">
          <button className={activeNav === "Dashboard" ? "active" : ""} onClick={() => setActiveNav("Dashboard")}><LayoutDashboard size={16} /> Dashboard</button>
          <button className={activeNav === "Chat Assistant" ? "active" : ""} onClick={openChat}><Bot size={16} /> Chat Assistant</button>
          <button className={activeNav === "Browse Products" ? "active" : ""} onClick={() => setActiveNav("Browse Products")}><Package size={16} /> Browse Products</button>
          <button className={activeNav === "Documents" ? "active" : ""} onClick={() => setActiveNav("Documents")}><FileArchive size={16} /> Documents</button>
          {<button className={activeNav === "Compare Solutions" ? "active" : ""} onClick={() => setActiveNav("Compare Solutions")}><Scale size={16} /> Compare Solutions</button>}
          {<button className={activeNav === "Upload Media" ? "active" : ""} onClick={() => setActiveNav("Upload Media")}><Upload size={16} /> Upload Media</button>}
          <button className={activeNav === "History" ? "active" : ""} onClick={() => setActiveNav("History")}><History size={16} /> History</button>
          <button className={activeNav === "Settings" ? "active" : ""} onClick={() => setActiveNav("Settings")}><Settings size={16} /> Settings</button>
        </nav>
        <button className="sidebar-signout" onClick={signInAgain}><LogOut size={16} /> Sign Out</button>
        <div className="online-status status-unknown"><span aria-hidden="true">○</span><b>Status unknown</b><small>Connection not checked</small></div>
      </aside>
      <section className="dashboard-main">
        <header className="dashboard-header">
          <div className="dashboard-title"><LayoutDashboard size={18} /><div><b>{activeNav}</b><small>Your AI equipment assistant at work</small></div></div>
          <div className="account-chip">
            <span className="account-avatar">👷</span>
            <div className="account-details">
              <b>{username.split("@")[0]}</b>
              <small>{role === "engineer" ? "Engineer" : "Customer"}</small>
            </div>
            </div>
        </header>
        <div className={`dashboard-content ${activeNav !== "Dashboard" ? "subpage-active" : ""}`}>
          {canAccessPage(activeNav) && activeNav !== "Dashboard" && (
            <section className={`page-panel ${activeNav === "Chat Assistant" ? "chat-page-panel" : ""}`}>
              <div className="page-panel-heading">
                <div>
                  <p className="page-kicker">JENGA WORKSPACE</p>
                  <h1>{pageDetails[activeNav].title}</h1>
                  <p>{pageDetails[activeNav].description}</p>
                </div>
                <span className="page-panel-icon"><Bot size={24} /></span>
              </div>
              {activeNav === "Chat Assistant" && (
                <div className="account-chat dashboard-card">
                  <div className="account-chat-heading">
                    <span className="bot-avatar"><Bot size={18} /></span>
                    <div><h2>Jenga Product Copilot</h2><p className="panel-muted">Your private, account-bound conversation</p></div>
                    <span className="chat-account-role">{role}</span>
                  </div>
                  <div className="chat-thread" aria-live="polite">
                    {chatLoading && <p className="panel-muted">Loading your conversation…</p>}
                    {!chatLoading && messages.length === 0 && (
                      <div className="chat-empty-state">
                        <Bot size={24} />
                        <b>Start a conversation</b>
                        <span>Ask about products, specifications, or pricing. Your chat will appear here after you send your first message.</span>
                      </div>
                    )}
                    <ChatMessages messages={messages} busy={busy} />
                  </div>
                  <form onSubmit={sendMessage} className="dashboard-composer account-chat-composer">
                    <input
                      ref={fileInput}
                      className="chat-file-input"
                      type="file"
                      multiple
                      accept="image/jpeg,image/png,image/webp,.pdf,.docx,.txt,.md,.csv,audio/wav,audio/mpeg,audio/webm,audio/mp4"
                      onChange={(event) => {
                        if (event.currentTarget.files) addFiles(event.currentTarget.files);
                        event.currentTarget.value = "";
                      }}
                    />
                    <input
                      ref={cameraInput}
                      className="chat-file-input"
                      type="file"
                      accept="image/*"
                      capture="environment"
                      onChange={(event) => {
                        if (event.currentTarget.files) addFiles(event.currentTarget.files);
                        event.currentTarget.value = "";
                      }}
                    />
                    {files.length > 0 && (
                      <div className="chat-attachment-list" aria-label="Attachments to send">
                        {files.map(({ key, file, kind, mediaId }) => (
                          <span className="chat-attachment-chip" key={key}>
                            {kind === "image" ? <Camera size={14} /> : kind === "audio" ? <Mic size={14} /> : <FileText size={14} />}
                            <span className="attachment-name">{file.name}</span>
                            <small>{mediaId ? "Uploaded" : "Ready to upload"}</small>
                            <button
                              type="button"
                              disabled={busy}
                              aria-label={`Remove ${file.name}`}
                              onClick={() => void removeAttachment({ key, file, kind, mediaId })}
                            >
                              <X size={14} />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                    <textarea
                      value={prompt}
                      onChange={(event) => setPrompt(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && !event.shiftKey) {
                          event.preventDefault();
                          void sendMessage();
                        }
                      }}
                      placeholder="Ask about equipment, specifications, or pricing…"
                      rows={3}
                      aria-label="Message Jenga Product Copilot"
                    />
                    {error && <p className="composer-error" role="alert">{error}</p>}
                    <div className="chat-attachment-tools">
                      <button type="button" disabled={busy || files.length >= MAX_CHAT_ATTACHMENTS} onClick={() => fileInput.current?.click()}>
                        <Paperclip size={15} /> Attach file
                      </button>
                      <button type="button" disabled={busy || files.length >= MAX_CHAT_ATTACHMENTS} onClick={() => cameraInput.current?.click()}>
                        <Camera size={15} /> Take photo
                      </button>
                      <button type="button" disabled={busy || (files.length >= MAX_CHAT_ATTACHMENTS && !recording)} onClick={() => void toggleRecording()} className={recording ? "recording" : ""}>
                        {recording ? <Square size={14} /> : <Mic size={15} />}
                        {recording ? "Stop recording" : "Voice note"}
                      </button>
                      <small>Images, PDF, DOCX, TXT, MD, CSV, or voice · 8 MiB each · up to 2 files</small>
                    </div>
                    {files.length > 0 && (
                      <label className="attachment-consent">
                        <input
                          type="checkbox"
                          checked={allowExternalProcessing}
                          onChange={(event) => setAllowExternalProcessing(event.currentTarget.checked)}
                        />
                        <span>
                          Optional hosted analysis: I am authorized to send these files to the configured external AI service. Do not send private or restricted
                          information unless its use with that service has been approved.
                        </span>
                      </label>
                    )}
                    <div className="composer-actions">
                      <span>Account-scoped chat. Photo and voice use local processing by default; hosted analysis requires operator approval and your consent.</span>
                      <button
                        disabled={busy || chatLoading || (!prompt.trim() && files.length === 0)}
                        className="send-button"
                        aria-label="Send message"
                      >
                        <ArrowUp size={16} />
                      </button>
                    </div>
                  </form>
                </div>
              )}
              {activeNav === "Browse Products" && (
                <>
                  {!catalogLoaded && <p className="panel-muted">Loading product catalogue…</p>}
                  {catalogError && <p className="login-error" role="alert">{catalogError}</p>}
                  {catalogLoaded && !catalogError && products.length === 0 && (
                    <p className="panel-muted">No products are currently available.</p>
                  )}
                  {catalogLoaded && !catalogError && products.length > 0 && (
                    <>
                      <div className="catalog-grid">
                        {products.slice(productPage * 4, productPage * 4 + 4).map((product) => (
                          <article className="catalog-card" key={product.id}>
                            <img
                              className="product-image"
                              src={productImage(product.category)}
                              alt={`${product.category} equipment illustration`}
                            />
                            <div>
                              <small className="product-category">{product.category}</small>
                              <h2>{product.name}</h2>
                              <p className="product-record-id">Catalogue record #{product.id}</p>
                              <p className="panel-muted">Model: {product.model_number}</p>
                              <strong className="catalog-price">{formatPrice(product.price_ksh)}</strong>
                              <p className="product-specifications">{product.specifications}</p>
                              <p className="product-image-note">Illustrative category image</p>
                            </div>
                          </article>
                        ))}
                      </div>
                      {products.length > 4 && (
                        <div className="catalog-pagination">
                          <button disabled={productPage === 0} onClick={() => setProductPage((page) => page - 1)}>Previous</button>
                          <span>Page {productPage + 1} of {Math.ceil(products.length / 4)}</span>
                          <button disabled={(productPage + 1) * 4 >= products.length} onClick={() => setProductPage((page) => page + 1)}>Next</button>
                        </div>
                      )}
                    </>
                  )}
                </>
              )}
              {activeNav === "Documents" && <div className="dashboard-card"><p className="panel-muted">Document listing is unavailable because source documents are not connected to this page.</p></div>}
              {activeNav === "Compare Solutions" && <div className="dashboard-card"><p className="panel-muted">No products are selected. Product comparison is not connected to this screen yet.</p></div>}
              {activeNav === "Upload Media" && <div className="upload-panel dashboard-card"><Upload size={30} /><h2>Upload equipment media</h2><p>Choose one nameplate photo and one audio question, up to 60 seconds. Speech requires a configured local runtime.</p><button className="primary-small" onClick={() => fileInput.current?.click()}>Choose files</button></div>}
              {activeNav === "History" && <div className="history-list dashboard-card"><h2><History size={16} /> Recent activity</h2><p className="panel-muted">Your recent assistant activity will appear here after your first question.</p></div>}
              {activeNav === "Settings" && <div className="settings-list dashboard-card"><h2><Settings size={16} /> Workspace settings</h2><label><span>Workspace notifications</span><input type="checkbox" defaultChecked /></label><label><span>Show source citations</span><input type="checkbox" defaultChecked /></label><label><span>Active role <small>Locked for this session</small></span><strong className="locked-role">{role === "engineer" ? "Engineer" : "Customer"}</strong></label></div>}
            </section>
          )}
          <section className="welcome-banner">
            <div><h1>Hi {username.split("@")[0]}! 👋</h1><p>Ask me about our industrial equipment,<br />get recommendations, or find technical specs.</p><button onClick={openChat}>Continue your chat <ArrowUp size={14} /></button></div>
            <div className="welcome-checks"><span>Synthetic demo catalogue</span><span>Source document retrieval unavailable</span></div>
          </section>
          <div className="dashboard-grid dashboard-products-only">
            <section className="dashboard-card recommendations-card">
              <div className="recommendation-heading">
                <div><p className="recommendation-kicker">CURRENT BACKEND CATALOGUE</p><h2>Available Products</h2></div>
                <button type="button" onClick={() => setActiveNav("Browse Products")}>View All <ChevronRight size={13} /></button>
              </div>
              <p className="recommendation-intro">Products and prices are loaded from the application catalogue.</p>
              <div className="recommendation-list dashboard-products-grid">
                {products.slice(0, 3).map((product) => (
                  <div className="recommendation" key={product.id}>
                    <img className="dashboard-product-image" src={productImage(product.category)} alt={`${product.category} equipment illustration`} />
                    <div className="dashboard-product-details">
                      <small className="product-category">{product.category}</small>
                      <b>{product.name}</b>
                      <small>Catalogue record #{product.id} · Model {product.model_number}</small>
                      <strong>{formatPrice(product.price_ksh)}</strong>
                      <p>{product.specifications}</p>
                    </div>
                  </div>
                ))}
                {catalogLoaded && products.length === 0 && (
                  <p className="panel-muted">{catalogError || "No catalogue products are available."}</p>
                )}
              </div>
            </section>
          </div>
          <div className="metrics-row">
            <div className="metric-card"><b>{catalogLoaded && !catalogError ? products.length : "Unavailable"}</b><small>Catalogue products{catalogError ? ` · ${catalogError}` : " · live API count"}</small></div>
            <div className="metric-card"><b>Not measured</b><small>Verified source documents</small></div>
            <div className="metric-card"><b>Not available</b><small>Benchmark results</small></div>
          </div>
        </div>
      </section>
    </main>
  );
}
