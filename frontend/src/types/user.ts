export interface Profile {
  id: string;
  display_name?: string | null;
  avatar_url?: string | null;
  bio?: string | null;
  timezone: string;
  language: string;
}

export interface UserPreference {
  id: string;
  theme: "dark" | "light" | "system";
  default_model: string;
  stream_responses: boolean;
  enter_to_send: boolean;
  custom_instructions?: string | null;
  reasoning_mode_default: boolean;
  web_search_default: boolean;
}

export interface User {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  is_verified: boolean;
  role: string;
  created_at: string;
  profile?: Profile | null;
  preferences?: UserPreference | null;
}
