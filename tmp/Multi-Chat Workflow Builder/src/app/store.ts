import { Agent, ChatNode, WorkflowRun, SavedWorkflow, DEFAULT_AGENTS } from './types';

const STORAGE_KEYS = {
  AGENTS: 'cli-chat-agents',
  WORKFLOWS: 'cli-chat-workflows',
  RUNS: 'cli-chat-runs',
  CURRENT_WORKFLOW: 'cli-chat-current',
};

// Agent Management
export const getAgents = (): Agent[] => {
  const stored = localStorage.getItem(STORAGE_KEYS.AGENTS);
  if (stored) {
    return JSON.parse(stored);
  }
  return DEFAULT_AGENTS;
};

export const saveAgents = (agents: Agent[]) => {
  localStorage.setItem(STORAGE_KEYS.AGENTS, JSON.stringify(agents));
};

// Workflow Management
export const getSavedWorkflows = (): SavedWorkflow[] => {
  const stored = localStorage.getItem(STORAGE_KEYS.WORKFLOWS);
  return stored ? JSON.parse(stored) : [];
};

export const saveWorkflow = (workflow: SavedWorkflow) => {
  const workflows = getSavedWorkflows();
  const index = workflows.findIndex(w => w.id === workflow.id);
  if (index >= 0) {
    workflows[index] = workflow;
  } else {
    workflows.push(workflow);
  }
  localStorage.setItem(STORAGE_KEYS.WORKFLOWS, JSON.stringify(workflows));
};

export const deleteWorkflow = (id: string) => {
  const workflows = getSavedWorkflows().filter(w => w.id !== id);
  localStorage.setItem(STORAGE_KEYS.WORKFLOWS, JSON.stringify(workflows));
};

// Run History Management
export const getRunHistory = (): WorkflowRun[] => {
  const stored = localStorage.getItem(STORAGE_KEYS.RUNS);
  return stored ? JSON.parse(stored) : [];
};

export const saveRun = (run: WorkflowRun) => {
  const runs = getRunHistory();
  runs.unshift(run);
  // Keep only last 50 runs
  const trimmed = runs.slice(0, 50);
  localStorage.setItem(STORAGE_KEYS.RUNS, JSON.stringify(trimmed));
};

export const deleteRun = (id: string) => {
  const runs = getRunHistory().filter(r => r.id !== id);
  localStorage.setItem(STORAGE_KEYS.RUNS, JSON.stringify(runs));
};

// Current Workflow State
export const getCurrentWorkflow = (): ChatNode[] => {
  const stored = localStorage.getItem(STORAGE_KEYS.CURRENT_WORKFLOW);
  return stored ? JSON.parse(stored) : [];
};

export const saveCurrentWorkflow = (chats: ChatNode[]) => {
  localStorage.setItem(STORAGE_KEYS.CURRENT_WORKFLOW, JSON.stringify(chats));
};
