/**
 * Centralized URL builders for every backend endpoint.
 *
 * Hooks and components import these instead of hard-coding route strings,
 * so the frontend can point at FastAPI without touching call-sites.
 */

// ---------------------------------------------------------------------------
// Base
// ---------------------------------------------------------------------------

const configuredBaseUrl =
  typeof process !== "undefined" ? process.env.NEXT_PUBLIC_API_BASE_URL ?? "" : "";

/** Override to point the frontend at a different origin (e.g. FastAPI). */
let _baseUrl = configuredBaseUrl.replace(/\/+$/, "");

export function setBaseUrl(url: string) {
  _baseUrl = url.replace(/\/+$/, "");
}

export function getBaseUrl() {
  return _baseUrl;
}

function api(path: string) {
  if (_baseUrl) {
    return `${_baseUrl}${path}`;
  }

  if (typeof window === "undefined") {
    return path;
  }

  const { protocol, hostname } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return `${protocol}//${hostname}:30000${path}`;
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

export function conversation(projectPath: string, sessionId: string) {
  return api(`/conversations/${enc(projectPath)}/${sessionId}`);
}

export function conversationDag(projectPath: string, sessionId: string) {
  return api(`/conversations/${enc(projectPath)}/${sessionId}/dag`);
}

export function conversationEvaluations(projectPath: string, sessionId: string) {
  return api(`/conversations/${enc(projectPath)}/${sessionId}/evaluations`);
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

export function tasks(sessionId: string) {
  return api(`/tasks/${sessionId}`);
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

export function orchestrationOatsRefresh(runId: string) {
  return api(`/orchestration/oats/${enc(runId)}/refresh`);
}

export function orchestrationOatsResume(runId: string) {
  return api(`/orchestration/oats/${enc(runId)}/resume`);
}

export function orchestrationPrefectDeployments() {
  return api("/orchestration/prefect/deployments");
}

export function orchestrationPrefectDeployment(deploymentId: string) {
  return api(`/orchestration/prefect/deployments/${enc(deploymentId)}`);
}

export function orchestrationPrefectFlowRuns() {
  return api("/orchestration/prefect/flow-runs");
}

export function orchestrationPrefectFlowRun(flowRunId: string) {
  return api(`/orchestration/prefect/flow-runs/${enc(flowRunId)}`);
}

export function orchestrationPrefectWorkers() {
  return api("/orchestration/prefect/workers");
}

export function orchestrationPrefectWorkPools() {
  return api("/orchestration/prefect/work-pools");
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
