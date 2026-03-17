import { useState, useEffect } from "react";
import { Agent, SavedWorkflow } from "../types";
import { getAgents, saveAgents, getSavedWorkflows, saveWorkflow, deleteWorkflow, getCurrentWorkflow } from "../store";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Plus, Trash2, Save, Download } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "./ui/dialog";
import { toast } from "sonner";

export function SettingsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [workflows, setWorkflows] = useState<SavedWorkflow[]>([]);
  const [newAgentName, setNewAgentName] = useState("");
  const [newAgentDesc, setNewAgentDesc] = useState("");
  const [newWorkflowName, setNewWorkflowName] = useState("");
  const [newWorkflowDesc, setNewWorkflowDesc] = useState("");
  const [agentDialogOpen, setAgentDialogOpen] = useState(false);
  const [workflowDialogOpen, setWorkflowDialogOpen] = useState(false);

  useEffect(() => {
    setAgents(getAgents());
    setWorkflows(getSavedWorkflows());
  }, []);

  const handleAddAgent = () => {
    if (!newAgentName.trim()) {
      toast.error("Please enter an agent name");
      return;
    }

    const newAgent: Agent = {
      id: `custom-${Date.now()}`,
      name: newAgentName,
      description: newAgentDesc || undefined,
    };

    const updatedAgents = [...agents, newAgent];
    setAgents(updatedAgents);
    saveAgents(updatedAgents);
    setNewAgentName("");
    setNewAgentDesc("");
    setAgentDialogOpen(false);
    toast.success("Custom agent created!");
  };

  const handleDeleteAgent = (id: string) => {
    const updatedAgents = agents.filter(a => a.id !== id);
    setAgents(updatedAgents);
    saveAgents(updatedAgents);
    toast.success("Agent deleted");
  };

  const handleSaveWorkflow = () => {
    if (!newWorkflowName.trim()) {
      toast.error("Please enter a workflow name");
      return;
    }

    const currentChats = getCurrentWorkflow();
    const workflow: SavedWorkflow = {
      id: Date.now().toString(),
      name: newWorkflowName,
      description: newWorkflowDesc || undefined,
      chats: currentChats.map(({ messages, ...chat }) => chat),
    };

    saveWorkflow(workflow);
    setWorkflows(getSavedWorkflows());
    setNewWorkflowName("");
    setNewWorkflowDesc("");
    setWorkflowDialogOpen(false);
    toast.success("Workflow template saved!");
  };

  const handleDeleteWorkflow = (id: string) => {
    deleteWorkflow(id);
    setWorkflows(getSavedWorkflows());
    toast.success("Workflow deleted");
  };

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold mb-2">Settings</h1>
          <p className="text-muted-foreground">
            Manage your custom agents and workflow templates
          </p>
        </div>

        <Tabs defaultValue="agents" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="agents">Custom Agents</TabsTrigger>
            <TabsTrigger value="workflows">Saved Workflows</TabsTrigger>
          </TabsList>

          <TabsContent value="agents" className="space-y-4">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Custom Agents</CardTitle>
                    <CardDescription>
                      Create custom agent configurations for specific tasks
                    </CardDescription>
                  </div>
                  <Dialog open={agentDialogOpen} onOpenChange={setAgentDialogOpen}>
                    <DialogTrigger asChild>
                      <Button>
                        <Plus className="size-4 mr-2" />
                        Add Agent
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create Custom Agent</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4 pt-4">
                        <div>
                          <label className="text-sm font-medium mb-2 block">Agent Name</label>
                          <Input
                            value={newAgentName}
                            onChange={(e) => setNewAgentName(e.target.value)}
                            placeholder="e.g., Code Review Expert"
                          />
                        </div>
                        <div>
                          <label className="text-sm font-medium mb-2 block">
                            Description (Optional)
                          </label>
                          <Textarea
                            value={newAgentDesc}
                            onChange={(e) => setNewAgentDesc(e.target.value)}
                            placeholder="Describe the agent's purpose and capabilities..."
                            rows={3}
                          />
                        </div>
                        <Button onClick={handleAddAgent} className="w-full">
                          Create Agent
                        </Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {agents.map((agent) => (
                    <div
                      key={agent.id}
                      className="flex items-start justify-between p-3 rounded-lg border bg-muted/20"
                    >
                      <div className="flex-1">
                        <div className="font-medium">{agent.name}</div>
                        {agent.description && (
                          <div className="text-sm text-muted-foreground mt-1">
                            {agent.description}
                          </div>
                        )}
                        <div className="text-xs text-muted-foreground mt-1">
                          ID: {agent.id}
                        </div>
                      </div>
                      {agent.id.startsWith('custom-') && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteAgent(agent.id)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="workflows" className="space-y-4">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Saved Workflow Templates</CardTitle>
                    <CardDescription>
                      Save and reuse workflow configurations
                    </CardDescription>
                  </div>
                  <Dialog open={workflowDialogOpen} onOpenChange={setWorkflowDialogOpen}>
                    <DialogTrigger asChild>
                      <Button>
                        <Save className="size-4 mr-2" />
                        Save Current Workflow
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Save Workflow Template</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4 pt-4">
                        <div>
                          <label className="text-sm font-medium mb-2 block">Workflow Name</label>
                          <Input
                            value={newWorkflowName}
                            onChange={(e) => setNewWorkflowName(e.target.value)}
                            placeholder="e.g., Code Analysis Pipeline"
                          />
                        </div>
                        <div>
                          <label className="text-sm font-medium mb-2 block">
                            Description (Optional)
                          </label>
                          <Textarea
                            value={newWorkflowDesc}
                            onChange={(e) => setNewWorkflowDesc(e.target.value)}
                            placeholder="Describe what this workflow does..."
                            rows={3}
                          />
                        </div>
                        <Button onClick={handleSaveWorkflow} className="w-full">
                          Save Template
                        </Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardHeader>
              <CardContent>
                {workflows.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-8">
                    No saved workflows yet. Create a workflow and save it as a template!
                  </p>
                ) : (
                  <div className="space-y-2">
                    {workflows.map((workflow) => (
                      <div
                        key={workflow.id}
                        className="flex items-start justify-between p-3 rounded-lg border bg-muted/20"
                      >
                        <div className="flex-1">
                          <div className="font-medium">{workflow.name}</div>
                          {workflow.description && (
                            <div className="text-sm text-muted-foreground mt-1">
                              {workflow.description}
                            </div>
                          )}
                          <div className="text-xs text-muted-foreground mt-1">
                            {workflow.chats.length} chat{workflow.chats.length !== 1 ? 's' : ''}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteWorkflow(workflow.id)}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
