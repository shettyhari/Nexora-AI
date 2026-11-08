export const STORAGE_KEYS = {
  TOKEN: "nexora_access_token",
  REFRESH_TOKEN: "nexora_refresh_token",
  THEME: "nexora_theme",
  ONBOARDED: "nexora_onboarded"
};

export const DEFAULT_SUGGESTIONS = [
  {
    icon: "Code",
    title: "Draft an Async FastAPI Service",
    prompt: "Design a high-throughput async Python service using FastAPI, Pydantic v2, and PostgreSQL connection pooling."
  },
  {
    icon: "Atom",
    title: "Explain Quantum Entanglement",
    prompt: "Provide an intuitive yet rigorous explanation of quantum entanglement and Bell's inequality for a computer scientist."
  },
  {
    icon: "Cpu",
    title: "Deep Neural Attention Architecture",
    prompt: "Derive and analyze the mathematical formulation of scaled dot-product attention in Transformer models."
  },
  {
    icon: "ShieldAlert",
    title: "Zero-Trust Security Blueprint",
    prompt: "Create a defense-in-depth zero-trust security checklist for multi-tenant SaaS cloud applications."
  }
];

export const KEYBOARD_SHORTCUTS = [
  { key: "Enter", description: "Send message" },
  { key: "Shift + Enter", description: "New line in composer" },
  { key: "Ctrl / ⌘ + K", description: "Search conversation history" },
  { key: "Ctrl / ⌘ + Shift + O", description: "Start new conversation" },
  { key: "Ctrl / ⌘ + /", description: "Toggle keyboard shortcuts dialog" },
  { key: "Escape", description: "Close modals / cancel editing" }
];

