import { apiJson } from "./api-client.ts";

export type OperatorPrincipal = {
  user_id: string;
  role: string;
  tenant_id: string;
  branch_code: string | null;
  auth_method: string;
};

export type OperatorSessionRequest = {
  username: string;
  role: string;
  tenant_id: string;
  branch_code?: string;
};

export type OperatorSessionResponse = {
  principal: OperatorPrincipal;
};

export function createOperatorSession(payload: OperatorSessionRequest) {
  return apiJson<OperatorSessionResponse>("/api/auth/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function loadOperatorSession() {
  return apiJson<OperatorSessionResponse>("/api/auth/me", { cache: "no-store" });
}

export function logoutOperatorSession() {
  return apiJson<{ status: string }>("/api/auth/logout", { method: "POST" });
}
