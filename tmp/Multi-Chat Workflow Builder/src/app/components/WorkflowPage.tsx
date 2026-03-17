import { useState, useEffect } from "react";
import { ChatNode, Agent, WorkflowRun } from "../types";
import { getAgents, getCurrentWorkflow, saveCurrentWorkflow, getRunHistory, saveRun, deleteRun } from "../store";
import { ChatPanel } from "./ChatPanel";
import { WorkflowDiagram } from "./WorkflowDiagram";
import { RunHistory } from "./RunHistory";
import { Button } from "./ui/button";
import { Plus, Save } from "lucide-react";
import { Input } from "./ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "./ui/dialog";
import { toast } from "sonner";

export function WorkflowPage() {
  const [chats, setChats] = useState<ChatNode[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [runName, setRunName] = useState("");
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [pendingImport, setPendingImport] = useState<{ content: string; source: string } | null>(null);
  const [selectedChatForImport, setSelectedChatForImport] = useState<string>("");

  useEffect(() => {
    setAgents(getAgents());
    setChats(getCurrentWorkflow());
    setRuns(getRunHistory());
  }, []);

  useEffect(() => {
    saveCurrentWorkflow(chats);
  }, [chats]);

  const addChat = () => {
    const newChat: ChatNode = {
      id: Date.now().toString(),
      name: `Chat ${chats.length + 1}`,
      agentId: agents[0]?.id || 'claude-sonnet',
      messages: [],
      inputFrom: [],
      outputTo: null,
    };
    setChats([...chats, newChat]);
  };

  const updateChat = (updatedChat: ChatNode) => {
    setChats(chats.map(chat => chat.id === updatedChat.id ? updatedChat : chat));
  };

  const deleteChat = (chatId: string) => {
    setChats(chats.filter(chat => chat.id !== chatId));
  };

  const handleSaveRun = () => {
    if (!runName.trim()) {
      toast.error("Please enter a run name");
      return;
    }

    const run: WorkflowRun = {
      id: Date.now().toString(),
      name: runName,
      timestamp: Date.now(),
      chats: chats,
    };

    saveRun(run);
    setRuns(getRunHistory());
    setSaveDialogOpen(false);
    setRunName("");
    toast.success("Workflow run saved!");
  };

  const loadRun = (run: WorkflowRun) => {
    setChats(run.chats);
    toast.success(`Loaded run: ${run.name}`);
  };

  const handleDeleteRun = (id: string) => {
    deleteRun(id);
    setRuns(getRunHistory());
    toast.success("Run deleted");
  };

  const handleImportIdea = (content: string, source: string) => {
    setPendingImport({ content, source });
    setImportDialogOpen(true);
  };

  const confirmImport = () => {
    if (!selectedChatForImport || !pendingImport) {
      toast.error("Please select a chat to import to");
      return;
    }

    const targetChat = chats.find(c => c.id === selectedChatForImport);
    if (!targetChat) return;

    const importMessage = {
      id: Date.now().toString(),
      role: 'user' as const,
      content: `[Imported from ${pendingImport.source}]\n\n${pendingImport.content}`,
      timestamp: Date.now(),
    };

    updateChat({
      ...targetChat,
      messages: [...targetChat.messages, importMessage],
    });

    setImportDialogOpen(false);
    setPendingImport(null);
    setSelectedChatForImport("");
    toast.success("Idea imported successfully!");
  };

  return (
    <div className="h-full flex">
      <RunHistory 
        runs={runs} 
        onLoadRun={loadRun} 
        onDeleteRun={handleDeleteRun}
        onImportIdea={handleImportIdea}
      />
      
      <div className="flex-1 flex flex-col">
        <div className="h-[280px] border-b">
          <WorkflowDiagram chats={chats} onUpdateChat={updateChat} />
        </div>

        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="border-b p-3 flex items-center justify-between bg-muted/10">
            <h2 className="font-semibold">Chat Workflow</h2>
            <div className="flex gap-2">
              <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" size="sm">
                    <Save className="size-4 mr-2" />
                    Save Run
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Save Workflow Run</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 pt-4">
                    <Input
                      value={runName}
                      onChange={(e) => setRunName(e.target.value)}
                      placeholder="Enter run name..."
                      onKeyDown={(e) => e.key === 'Enter' && handleSaveRun()}
                    />
                    <Button onClick={handleSaveRun} className="w-full">
                      Save
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
              <Button onClick={addChat} size="sm">
                <Plus className="size-4 mr-2" />
                Add Chat
              </Button>
            </div>
          </div>

          <div className="flex-1 overflow-x-auto overflow-y-hidden">
            <div className="h-full flex gap-4 p-4 min-w-min">
              {chats.length === 0 ? (
                <div className="flex-1 flex items-center justify-center">
                  <div className="text-center">
                    <p className="text-muted-foreground mb-4">
                      No chats yet. Click "Add Chat" to get started!
                    </p>
                    <Button onClick={addChat}>
                      <Plus className="size-4 mr-2" />
                      Add Your First Chat
                    </Button>
                  </div>
                </div>
              ) : (
                chats.map((chat) => (
                  <ChatPanel
                    key={chat.id}
                    chat={chat}
                    agents={agents}
                    availableChats={chats}
                    onUpdateChat={updateChat}
                    onDeleteChat={deleteChat}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Import Idea Dialog */}
      <Dialog open={importDialogOpen} onOpenChange={setImportDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Import Idea to Chat</DialogTitle>
            <DialogDescription>
              Select which chat to import this idea into
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            {pendingImport && (
              <div className="p-3 rounded-lg bg-muted text-sm">
                <div className="font-medium text-muted-foreground mb-2">
                  From: {pendingImport.source}
                </div>
                <div className="line-clamp-3">
                  {pendingImport.content}
                </div>
              </div>
            )}
            <div>
              <label className="text-sm font-medium mb-2 block">Select Target Chat:</label>
              <select
                value={selectedChatForImport}
                onChange={(e) => setSelectedChatForImport(e.target.value)}
                className="w-full p-2 rounded-md border bg-background"
              >
                <option value="">Choose a chat...</option>
                {chats.map(chat => (
                  <option key={chat.id} value={chat.id}>
                    {chat.name} (#{chat.id.slice(0, 6)})
                  </option>
                ))}
              </select>
            </div>
            <Button 
              onClick={confirmImport} 
              className="w-full"
              disabled={!selectedChatForImport}
            >
              Import to Selected Chat
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}