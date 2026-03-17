export interface Agent {
  id: string;
  name: string;
  description?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface ChatNode {
  id: string;
  name: string;
  agentId: string;
  messages: ChatMessage[];
  inputFrom: string[]; // Array of chat IDs that route to this chat
  outputTo: string | null; // Chat ID to route to, or null
  loopMaxIterations?: number; // Max iterations for loops (optional)
}

export interface WorkflowRun {
  id: string;
  name: string;
  timestamp: number;
  chats: ChatNode[];
}

export interface SavedWorkflow {
  id: string;
  name: string;
  description?: string;
  chats: Omit<ChatNode, 'messages'>[];
}

export const DEFAULT_AGENTS: Agent[] = [
  { id: 'claude-sonnet', name: 'Claude Sonnet' },
  { id: 'claude-opus', name: 'Claude Opus' },
  { id: 'claude-haiku', name: 'Claude Haiku' },
  { id: 'codex-5.4-medium', name: 'Codex 5.4 Medium' },
  { id: 'codex-5.4-large', name: 'Codex 5.4 Large' },
  { id: 'gpt-4', name: 'GPT-4' },
  { id: 'gpt-4-turbo', name: 'GPT-4 Turbo' },
];