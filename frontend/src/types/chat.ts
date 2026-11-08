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

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  reasoning_content?: string | null;
  model?: string | null;
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
  description?: string;
  badge?: string;
}

export interface StreamEvent {
  type: "start" | "token" | "reasoning" | "search_status" | "usage" | "done" | "error";
  content?: string;
  message_id?: string;
  conversation_id?: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}
