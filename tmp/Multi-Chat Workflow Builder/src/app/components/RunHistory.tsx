import { WorkflowRun } from "../types";
import { Clock, Trash2, Play, Lightbulb, Import } from "lucide-react";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import { Separator } from "./ui/separator";

interface RunHistoryProps {
  runs: WorkflowRun[];
  onLoadRun: (run: WorkflowRun) => void;
  onDeleteRun: (id: string) => void;
  onImportIdea?: (content: string, runName: string) => void;
}

export function RunHistory({ runs, onLoadRun, onDeleteRun, onImportIdea }: RunHistoryProps) {
  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  // Get interesting ideas from old chats (last assistant messages)
  const getIdeasFromRuns = () => {
    const ideas: Array<{ content: string; runName: string; chatName: string; timestamp: number }> = [];
    
    runs.forEach(run => {
      run.chats.forEach(chat => {
        const lastAssistantMessage = [...chat.messages]
          .reverse()
          .find(msg => msg.role === 'assistant');
        
        if (lastAssistantMessage && lastAssistantMessage.content.length > 20) {
          ideas.push({
            content: lastAssistantMessage.content,
            runName: run.name,
            chatName: chat.name,
            timestamp: lastAssistantMessage.timestamp,
          });
        }
      });
    });

    // Sort by timestamp, most recent first, and take top 5
    return ideas.sort((a, b) => b.timestamp - a.timestamp).slice(0, 5);
  };

  const ideas = getIdeasFromRuns();

  return (
    <div className="w-64 border-r bg-muted/10 flex flex-col h-full">
      <div className="p-4 border-b">
        <h2 className="font-semibold flex items-center gap-2">
          <Clock className="size-4" />
          Run History
        </h2>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-2">
          {runs.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8 px-4">
              No runs yet. Create a workflow and it will be saved here.
            </p>
          ) : (
            runs.map((run) => (
              <div
                key={run.id}
                className="p-3 rounded-lg border bg-background hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{run.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {formatTimestamp(run.timestamp)}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {run.chats.length} chat{run.chats.length !== 1 ? 's' : ''}
                    </div>
                  </div>
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs flex-1"
                    onClick={() => onLoadRun(run)}
                  >
                    <Play className="size-3 mr-1" />
                    Load
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={() => onDeleteRun(run.id)}
                  >
                    <Trash2 className="size-3" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      {/* Ideas Import Section */}
      {ideas.length > 0 && (
        <>
          <Separator />
          <div className="border-t bg-muted/20">
            <div className="p-3 border-b bg-muted/30">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Lightbulb className="size-4 text-yellow-500" />
                Ideas from Old Chats
              </h3>
            </div>
            <ScrollArea className="max-h-[200px]">
              <div className="p-2 space-y-2">
                {ideas.map((idea, idx) => (
                  <div
                    key={idx}
                    className="p-2 rounded-lg border bg-background text-xs"
                  >
                    <div className="font-medium text-muted-foreground mb-1">
                      {idea.runName} • {idea.chatName}
                    </div>
                    <div className="line-clamp-2 mb-2 text-foreground">
                      {idea.content}
                    </div>
                    {onImportIdea && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-6 text-xs w-full"
                        onClick={() => onImportIdea(idea.content, `${idea.runName} - ${idea.chatName}`)}
                      >
                        <Import className="size-3 mr-1" />
                        Import
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        </>
      )}
    </div>
  );
}