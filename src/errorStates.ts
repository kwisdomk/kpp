export type ErrorKind = "not_found" | "forbidden" | "role_required" | "session_expired" | "unavailable";

export const errorStates = {
  not_found: {
    code: "404", label: "PAGE NOT FOUND", title: "This page is off the plans.",
    description: "We couldn't find this page. The link may be incomplete, or the page may have moved.",
    encouragement: "A wrong turn doesn't end the project. Let's get you back to work.",
    status: "page_not_found", next: "return_to_workspace", action: "Return to workspace",
    actionType: "workspace",
  },
  forbidden: {
    code: "403", label: "ACCESS DENIED", title: "This area needs permission.",
    description: "Your account doesn't have permission to open this area. Return to your workspace, or contact your team lead about access.",
    encouragement: "There's still plenty you can build in your own workspace.",
    status: "access_denied", next: "use_authorized_workspace", action: "Return to workspace",
    actionType: "workspace",
  },
  role_required: {
    code: "ROLE", label: "WORKSPACE NOT ASSIGNED", title: "Your account needs a workspace.",
    description: "We couldn't find a supported role on your account. Sign in again. If this continues, ask your team lead to check your account assignment.",
    encouragement: "The right access starts with the right account.",
    status: "role_unavailable", next: "sign_in_again", action: "Sign in again",
    actionType: "signin",
  },
  session_expired: {
    code: "401", label: "SIGN-IN REQUIRED", title: "Let's reconnect your session.",
    description: "Your session has expired or is no longer valid. Sign in again to continue. Your previous request won't be sent automatically.",
    encouragement: "A quick sign-in, then back to the work ahead.",
    status: "session_unavailable", next: "sign_in_again", action: "Sign in again",
    actionType: "signin",
  },
  unavailable: {
    code: "PAUSE", label: "CONNECTION INTERRUPTED", title: "We couldn't check your account.",
    description: "The service couldn't verify your session. Check your connection and try again before opening your workspace.",
    encouragement: "We'll reopen your workspace once your account can be verified.",
    status: "identity_check_unavailable", next: "retry_connection", action: "Try again",
    actionType: "retry",
  },
} as const;

export function errorForPath(pathname: string): ErrorKind | null {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (["/", "/login", "/chat"].includes(path)) return null;
  if (["/403", "/access-denied"].includes(path)) return "forbidden";
  if (path === "/role-required") return "role_required";
  if (path === "/session-expired") return "session_expired";
  return "not_found";
}

export function accessErrorForStatus(status: number): ErrorKind | null {
  if (status === 401) return "session_expired";
  if (status === 403) return "forbidden";
  return null;
}

export function isWorkspaceRole(role: unknown): role is "engineer" | "customer" {
  return role === "engineer" || role === "customer";
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}
