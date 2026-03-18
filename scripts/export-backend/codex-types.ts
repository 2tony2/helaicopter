// Raw JSONL event types from ~/.codex/sessions/ conversation files

/** Top-level wrapper for every line in a Codex session JSONL */
export interface CodexRawLine {
  timestamp: string; // ISO 8601
  type: "session_meta" | "response_item" | "event_msg" | "turn_context";
  payload: CodexPayload;
}

// --- Payloads ---

export type CodexPayload =
  | CodexSessionMeta
  | CodexResponseItem
  | CodexEventMsg
  | CodexTurnContext;

export interface CodexSessionMeta {
  type?: undefined; // no payload.type on session_meta
  id: string;
  timestamp: string;
  cwd: string;
  originator: string; // "codex_cli_rs" | "Codex Desktop"
  cli_version: string;
  source:
    | string
    | {
        subagent?: {
          thread_spawn?: {
            parent_thread_id?: string;
            depth?: number;
            agent_nickname?: string;
            agent_role?: string;
          };
        };
      };
  model_provider: string; // "openai"
  base_instructions?: { text: string };
  agent_nickname?: string;
  agent_role?: string;
}

// response_item payloads
export type CodexResponseItem =
  | CodexMessageItem
  | CodexFunctionCallItem
  | CodexFunctionCallOutputItem
  | CodexCustomToolCallItem
  | CodexCustomToolCallOutputItem
  | CodexWebSearchCallItem
  | CodexReasoningItem;

export interface CodexMessageItem {
  type: "message";
  role: "user" | "assistant" | "developer";
  content: CodexContentBlock[];
  phase?: "commentary" | "final";
}

export interface CodexContentBlock {
  type: "input_text" | "output_text";
  text: string;
}

export interface CodexFunctionCallItem {
  type: "function_call";
  name: string; // "exec_command"
  arguments: string; // JSON string
  call_id: string;
}

export interface CodexFunctionCallOutputItem {
  type: "function_call_output";
  call_id: string;
  output: string;
}

export interface CodexCustomToolCallItem {
  type: "custom_tool_call";
  status: string;
  call_id: string;
  name: string; // "apply_patch"
  input: string;
}

export interface CodexCustomToolCallOutputItem {
  type: "custom_tool_call_output";
  call_id: string;
  output: string;
}

export interface CodexWebSearchCallItem {
  type: "web_search_call";
  status: string;
  action?: {
    type?: string;
    query?: string;
    queries?: string[];
  };
}

export interface CodexReasoningItem {
  type: "reasoning";
  summary: Array<{ type: string; text: string }>;
  content: string | null;
  encrypted_content?: string;
}

// event_msg payloads
export type CodexEventMsg =
  | CodexTokenCountMsg
  | CodexAgentMessageMsg
  | CodexAgentReasoningMsg
  | CodexTaskStartedMsg
  | CodexTaskCompleteMsg
  | CodexUserMessageMsg;

export interface CodexTokenCountMsg {
  type: "token_count";
  info: {
    total_token_usage: CodexTokenUsage;
    last_token_usage: CodexTokenUsage;
    model_context_window: number;
  } | null;
  rate_limits?: unknown;
}

export interface CodexTokenUsage {
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  reasoning_output_tokens: number;
  total_tokens: number;
}

export interface CodexAgentMessageMsg {
  type: "agent_message";
  message: string;
  phase?: "commentary" | "final";
}

export interface CodexAgentReasoningMsg {
  type: "agent_reasoning";
  text: string;
}

export interface CodexTaskStartedMsg {
  type: "task_started";
  turn_id: string;
  model_context_window: number;
  collaboration_mode_kind?: string;
}

export interface CodexTaskCompleteMsg {
  type: "task_complete";
}

export interface CodexUserMessageMsg {
  type: "user_message";
}

// turn_context — placeholder, we skip these
export interface CodexTurnContext {
  type?: undefined;
  model?: string;
  [key: string]: unknown;
}
