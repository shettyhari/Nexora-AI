export interface Attachment {
  id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  storage_path: string;
  mime_type: string;
  created_at: string;
}

export interface Feedback {
  id: string;
  message_id: string;
  user_id: string;
  rating: "like" | "dislike";
  comment?: string;
  created_at: string;
}

export interface CitationItem {
  id?: number;
  source_id?: number;
  title?: string;
  source_title?: string;
  url?: string;
  chunk_index?: number;
  snippet?: string;
  content_snippet?: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  reasoning_content?: string | null;
  model?: string | null;
  actual_provider?: string | null;
  fallback_used?: boolean;
  fallback_from_model?: string | null;
  routing_reason?: string | null;
  citations?: CitationItem[] | null;
  tokens_used: number;
  is_edited: boolean;
  error?: string | null;
  created_at: string;
  updated_at: string;
  attachments?: Attachment[];
  feedback?: Feedback[];
}

export interface ConversationSummary {
  id: string;
  title: string;
  is_pinned: boolean;
  is_archived: boolean;
  model_id: string;
  project_id?: string | null;
  reasoning_mode: boolean;
  web_search_enabled: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview?: string | null;
}

export interface ConversationDetail extends ConversationSummary {
  system_prompt?: string | null;
  messages: Message[];
}

export interface ModelConfig {
  id: string;
  model_key: string;
  display_name: string;
  provider: string;
  model_name: string;
  context_window: number;
  max_tokens: number;
  supports_vision: boolean;
  supports_reasoning: boolean;
  is_enabled: boolean;
  is_default: boolean;
  is_proprietary?: boolean;
  min_plan_tier?: string;
  plan_permitted?: boolean;
  pricing?: {
    input_per_million: number;
    output_per_million: number;
  };
  description?: string;
  badge?: string;
}

export interface StreamEvent {
  type: "start" | "token" | "reasoning" | "search_status" | "usage" | "routing" | "done" | "error";
  content?: string;
  message_id?: string;
  conversation_id?: string;
  resolved_model?: string;
  actual_provider?: string;
  fallback_used?: boolean;
  fallback_from_model?: string;
  routing_reason?: string;
  citations?: CitationItem[];
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cost_usd?: number;
  };
}

export interface AgentStepInfo {
  step_number: number;
  agent_type: string;
  status: "pending" | "running" | "completed" | "failed" | "waiting_approval";
  description: string;
  output?: string;
  tool_results?: any[];
  error?: string;
  execution_time_ms?: number;
}

export interface AgentWorkflowInfo {
  workflow_id: string;
  goal: string;
  status: "pending" | "running" | "completed" | "failed";
  plan: Array<{ step_number: number; agent_type: string; description: string; required_tools: string[] }>;
  step_results: AgentStepInfo[];
  final_response?: string;
  total_execution_time_ms?: number;
}

export interface VideoSceneMarker {
  timestamp_seconds: number;
  timestamp_formatted: string;
  label: string;
  description: string;
}

export interface ExtractedTableInfo {
  table_index: number;
  headers: string[];
  rows: string[][];
  markdown: string;
}
