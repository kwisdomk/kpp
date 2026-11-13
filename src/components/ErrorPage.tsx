import { useEffect, useRef } from "react";
import { ArrowLeft, ArrowRight, KeyRound, Layers, ShieldAlert, TerminalSquare } from "lucide-react";
import { errorStates } from "../errorStates";
import type { ErrorKind } from "../errorStates";
import "./ErrorPage.css";

type ErrorPageProps = {
  kind: ErrorKind;
  onReturn?: () => void;
  onSignIn?: () => void;
};

export default function ErrorPage({ kind, onReturn, onSignIn }: ErrorPageProps) {
  const state = errorStates[kind];
  const heading = useRef<HTMLHeadingElement>(null);
  const Icon = kind === "forbidden" || kind === "role_required"
    ? ShieldAlert : kind === "session_expired" ? KeyRound : TerminalSquare;

  useEffect(() => {
    const previousTitle = document.title;
    document.title = `${state.label} · Jenga Product Copilot`;
    heading.current?.focus();
    return () => { document.title = previousTitle; };
  }, [state.label]);

  const action = state.actionType === "signin" ? onSignIn : onReturn;
  const href = state.actionType === "signin" ? "/login" : "/";

  return (
    <main className="recovery-page" aria-labelledby="recovery-heading">
      <header className="recovery-header">
        <a className="recovery-brand" href="/" aria-label="Jenga Consultants home">
          <span className="recovery-brand-icon"><Layers size={23} aria-hidden="true" /></span>
          <span>Jenga Consultants<small>Product Copilot</small></span>
        </a>
        <span className="recovery-header-label">WORKSPACE / RECOVERY</span>
      </header>

      <section className="recovery-content">
        <div className="recovery-icon" aria-hidden="true"><Icon size={40} strokeWidth={1.4} /></div>
        <p className="recovery-code" aria-hidden="true">{state.code}</p>
        <p className="recovery-label">{state.label}</p>
        <h1 id="recovery-heading" tabIndex={-1} ref={heading}>{state.title}</h1>
        <p className="recovery-description">{state.description}</p>

        <div className="recovery-terminal" role="note" aria-label="Workspace status">
          <div className="recovery-terminal-bar"><span aria-hidden="true">● ● ●</span><span>jenga / workspace</span></div>
          <dl>
            <div><dt>status</dt><dd>{state.status}</dd></div>
            <div><dt>next</dt><dd>{state.next}<span className="recovery-cursor" aria-hidden="true">_</span></dd></div>
          </dl>
        </div>

        <div className="recovery-actions">
          {action ? (
            <button type="button" className="recovery-primary" onClick={action}><ArrowLeft size={17} aria-hidden="true" />{state.action}</button>
          ) : (
            <a className="recovery-primary" href={href}><ArrowLeft size={17} aria-hidden="true" />{state.action}</a>
          )}
          {kind === "not_found" && <a className="recovery-secondary" href="/chat">Open assistant<ArrowRight size={16} aria-hidden="true" /></a>}
          {(kind === "forbidden" || kind === "unavailable") && onSignIn && (
            <button type="button" className="recovery-secondary" onClick={onSignIn}>Use another account<ArrowRight size={16} aria-hidden="true" /></button>
          )}
        </div>
        <p className="recovery-encouragement">{state.encouragement}</p>
      </section>

      <footer className="recovery-footer"><span>Built for the work ahead.</span><span>JENGA CONSULTANTS · DEMO</span></footer>
    </main>
  );
}
