/**
 * Centralized URL builders for every backend endpoint.
 *
 * Hooks and components import these instead of hard-coding route strings,
 * so the frontend can point at FastAPI without touching call-sites.
 */

import { parseApiBaseUrl } from "./schemas/runtime.ts";

// ---------------------------------------------------------------------------
// Base
// ---------------------------------------------------------------------------

const configuredBaseUrl = parseApiBaseUrl(
  typeof process !== "undefined" ? process.env.NEXT_PUBLIC_API_BASE_URL : undefined
);

/** Override to point the frontend at a different origin (e.g. FastAPI). */
let _baseUrl = configuredBaseUrl;

export function setBaseUrl(url: string) {
  _baseUrl = parseApiBaseUrl(url);
}

export function getBaseUrl() {
  return _baseUrl;
}

function api(path: string) {
  if (_baseUrl) {
    return `${_baseUrl}${path}`;
  }

  return path;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function qs(params: Record<string, string | number | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

function enc(segment: string) {
  return encodeURIComponent(segment);
}

type ParentSessionOptions = {
  parentSessionId?: string;
};

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export function projects() {
  return api("/projects");
}

// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------

export function conversations(opts?: { project?: string; days?: number }) {
  return api(`/conversations${qs({ project: opts?.project, days: opts?.days })}`);
}

export function conversation(projectPath: string, sessionId: string, opts?: ParentSessionOptions) {
  return api(
    `/conversations/${enc(projectPath)}/${sessionId}${qs({
      parent_session_id: opts?.parentSessionId,
    })}`
  );
}

export function conversationByRef(conversationRef: string) {
  return api(`/conversations/by-ref/${enc(conversationRef)}`);
}

export function conversationDag(
  projectPath: string,
  sessionId: string,
  opts?: ParentSessionOptions
) {
  return api(
    `/conversations/${enc(projectPath)}/${sessionId}/dag${qs({
      parent_session_id: opts?.parentSessionId,
    })}`
  );
}

export function conversationEvaluations(
  projectPath: string,
  sessionId: string,
  opts?: ParentSessionOptions
) {
  return api(
    `/conversations/${enc(projectPath)}/${sessionId}/evaluations${qs({
      parent_session_id: opts?.parentSessionId,
    })}`
  );
}

export function conversationDags(opts?: {
  project?: string;
  days?: number;
  provider?: string;
}) {
  const provider = opts?.provider === "all" ? undefined : opts?.provider;
  return api(`/conversation-dags${qs({ project: opts?.project, days: opts?.days, provider })}`);
}

// ---------------------------------------------------------------------------
// Subagents
// ---------------------------------------------------------------------------

export function subagent(projectPath: string, sessionId: string, agentId: string) {
  return api(`/conversations/${enc(projectPath)}/${sessionId}/subagents/${agentId}`);
}

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

export function tasks(sessionId: string, opts?: ParentSessionOptions) {
  return api(`/tasks/${sessionId}${qs({ parent_session_id: opts?.parentSessionId })}`);
}

// ---------------------------------------------------------------------------
// Plans
// ---------------------------------------------------------------------------

export function plans() {
  return api("/plans");
}

export function plan(slug: string) {
  return api(`/plans/${slug}`);
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export function analytics(opts?: { days?: number; provider?: string }) {
  const provider = opts?.provider === "all" ? undefined : opts?.provider;
  return api(`/analytics${qs({ days: opts?.days, provider })}`);
}

// ---------------------------------------------------------------------------
// Databases
// ---------------------------------------------------------------------------

export function databaseStatus() {
  return api("/databases/status");
}

export function databaseRefresh() {
  return api("/databases/refresh");
}

// ---------------------------------------------------------------------------
// Evaluation prompts
// ---------------------------------------------------------------------------

export function evaluationPrompts() {
  return api("/evaluation-prompts");
}

export function evaluationPrompt(promptId: string) {
  return api(`/evaluation-prompts/${promptId}`);
}

// ---------------------------------------------------------------------------
// Orchestration
// ---------------------------------------------------------------------------

export function orchestrationOats() {
  return api("/orchestration/oats");
}

export function orchestrationRuntime(runId: string) {
  return api(`/orchestration/runtime/${enc(runId)}`);
}

export function orchestrationOatsRefresh(runId: string) {
  return api(`/orchestration/oats/${enc(runId)}/refresh`);
}

export function orchestrationOatsResume(runId: string) {
  return api(`/orchestration/oats/${enc(runId)}/resume`);
}

export function orchestrationOatsPause(runId: string) {
  return api(`/orchestration/oats/${enc(runId)}/pause`);
}

export function orchestrationOatsCancelTask(runId: string, taskId: string) {
  return api(`/orchestration/oats/${enc(runId)}/tasks/${enc(taskId)}/cancel`);
}

export function orchestrationOatsForceRetryTask(runId: string, taskId: string) {
  return api(`/orchestration/oats/${enc(runId)}/tasks/${enc(taskId)}/force-retry`);
}

export function orchestrationOatsRerouteTask(runId: string, taskId: string) {
  return api(`/orchestration/oats/${enc(runId)}/tasks/${enc(taskId)}/reroute`);
}

export function orchestrationOatsInsertTask(runId: string) {
  return api(`/orchestration/oats/${enc(runId)}/tasks`);
}

export function operatorBootstrap() {
  return api("/operator/bootstrap");
}

// ---------------------------------------------------------------------------
// Workers
// ---------------------------------------------------------------------------

export function workers(opts?: { provider?: string }) {
  return api(`/workers${qs({ provider: opts?.provider })}`);
}

export function workerProviders() {
  return api("/workers/providers");
}

export function worker(workerId: string) {
  return api(`/workers/${enc(workerId)}`);
}

export function workerDrain(workerId: string) {
  return api(`/workers/${enc(workerId)}/drain`);
}

export function workerResetSession(workerId: string) {
  return api(`/workers/${enc(workerId)}/reset-session`);
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export function authCredentials() {
  return api("/auth/credentials");
}

export function authCredential(credentialId: string) {
  return api(`/auth/credentials/${enc(credentialId)}`);
}

export function authCredentialRefresh(credentialId: string) {
  return api(`/auth/credentials/${enc(credentialId)}/refresh`);
}

export function authCredentialClaudeCliConnect() {
  return api("/auth/credentials/claude-cli/connect");
}

export function authCredentialOauthInitiate() {
  return api("/auth/credentials/oauth/initiate");
}

// ---------------------------------------------------------------------------
// Dispatch
// ---------------------------------------------------------------------------

export function dispatchQueue() {
  return api("/dispatch/queue");
}

export function dispatchHistory(opts?: { limit?: number }) {
  return api(`/dispatch/history${qs({ limit: opts?.limit })}`);
}

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------

export function history(opts?: { limit?: number }) {
  return api(`/history${qs({ limit: opts?.limit })}`);
}

// ---------------------------------------------------------------------------
// Subscription settings
// ---------------------------------------------------------------------------

export function subscriptionSettings() {
  return api("/subscription-settings");
}
