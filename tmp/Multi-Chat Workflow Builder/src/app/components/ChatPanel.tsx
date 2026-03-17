import { useState } from "react";
import { ChatNode, Agent } from "../types";
import { Send, X, Download } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { ScrollArea } from "./ui/scroll-area";
import { Card } from "./ui/card";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Checkbox } from "./ui/checkbox";

interface ChatPanelProps {
  chat: ChatNode;
  agents: Agent[];
  availableChats: ChatNode[];
  onUpdateChat: (chat: ChatNode) => void;
  onDeleteChat: (chatId: string) => void;
}

export function ChatPanel({ chat, agents, availableChats, onUpdateChat, onDeleteChat }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [selectedImports, setSelectedImports] = useState<string[]>([]);

  const handleSend = () => {
    if (!input.trim()) return;

    const newMessage = {
      id: Date.now().toString(),
      role: 'user' as const,
      content: input,
      timestamp: Date.now(),
    };

    // Simulate assistant response
    const assistantMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant' as const,
      content: `[${agents.find(a => a.id === chat.agentId)?.name || 'Agent'}] Received: "${input}"`,
      timestamp: Date.now() + 100,
    };

    onUpdateChat({
      ...chat,
      messages: [...chat.messages, newMessage, assistantMessage],
    });

    setInput("");
  };

  const handleAgentChange = (agentId: string) => {
    onUpdateChat({ ...chat, agentId });
  };

  const handleOutputChange = (outputTo: string) => {
    onUpdateChat({ ...chat, outputTo: outputTo === "none" ? null : outputTo });
  };

  const handleImportOutputs = () => {
    if (selectedImports.length === 0) return;

    let importedContent = "=== IMPORTED OUTPUTS ===\n\n";

    selectedImports.forEach(chatId => {
      const sourceChat = availableChats.find(c => c.id === chatId);
      if (!sourceChat) return;

      const lastAssistantMessage = [...sourceChat.messages]
        .reverse()
        .find(msg => msg.role === 'assistant');

      if (lastAssistantMessage) {
        importedContent += `From "${sourceChat.name}" (${sourceChat.agentId}):\n${lastAssistantMessage.content}\n\n`;
      }
    });

    importedContent += "=== END IMPORTS ===";

    const importMessage = {
      id: Date.now().toString(),
      role: 'user' as const,
      content: importedContent,
      timestamp: Date.now(),
    };

    onUpdateChat({
      ...chat,
      messages: [...chat.messages, importMessage],
    });

    setSelectedImports([]);
  };

  const toggleImportSelection = (chatId: string) => {
    setSelectedImports(prev =>
      prev.includes(chatId)
        ? prev.filter(id => id !== chatId)
        : [...prev, chatId]
    );
  };

  const otherChats = availableChats.filter(c => c.id !== chat.id);
  const chatsWithOutput = otherChats.filter(c => 
    c.messages.some(msg => msg.role === 'assistant')
  );

  return (
    <Card className="w-[400px] flex-shrink-0 flex flex-col h-full border-2">
      <div className="border-b p-3 flex items-center justify-between bg-muted/30">
        <Input
          value={chat.name}
          onChange={(e) => onUpdateChat({ ...chat, name: e.target.value })}
          className="h-8 max-w-[200px] bg-background"
          placeholder="Chat name"
        />
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDeleteChat(chat.id)}
        >
          <X className="size-4" />
        </Button>
      </div>

      <div className="border-b p-3 space-y-2 bg-muted/10">
        {/* Input Imports Section */}
        {chatsWithOutput.length > 0 && (
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Import Outputs From:</label>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className="w-full h-8 text-xs justify-start">
                  <Download className="size-3 mr-2" />
                  {selectedImports.length === 0
                    ? "Select chats to import..."
                    : `${selectedImports.length} selected`}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[300px] p-3" align="start">
                <div className="space-y-2">
                  <div className="text-xs font-semibold mb-2">Select chats to import outputs from:</div>
                  {chatsWithOutput.map(c => (
                    <div key={c.id} className="flex items-center space-x-2">
                      <Checkbox
                        id={`import-${c.id}`}
                        checked={selectedImports.includes(c.id)}
                        onCheckedChange={() => toggleImportSelection(c.id)}
                      />
                      <label
                        htmlFor={`import-${c.id}`}
                        className="text-xs cursor-pointer flex-1"
                      >
                        {c.name} (#{c.id.slice(0, 6)})
                      </label>
                    </div>
                  ))}
                  {selectedImports.length > 0 && (
                    <Button
                      onClick={handleImportOutputs}
                      size="sm"
                      className="w-full mt-2"
                    >
                      Import {selectedImports.length} output{selectedImports.length !== 1 ? 's' : ''}
                    </Button>
                  )}
                </div>
              </PopoverContent>
            </Popover>
          </div>
        )}

        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Output Routes To:</label>
          <Select value={chat.outputTo || "none"} onValueChange={handleOutputChange}>
            <SelectTrigger className="h-8 text-sm">
              <SelectValue placeholder="No routing" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">No routing</SelectItem>
              {otherChats.map(c => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name} (#{c.id.slice(0, 6)})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <ScrollArea className="flex-1 p-4">
        <div className="space-y-3">
          {chat.messages.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No messages yet. Start a conversation!
            </p>
          ) : (
            chat.messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      <div className="border-t p-3 space-y-3">
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Type a message..."
            className="h-9"
          />
          <Button onClick={handleSend} size="sm">
            <Send className="size-4" />
          </Button>
        </div>

        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Agent:</label>
          <Select value={chat.agentId} onValueChange={handleAgentChange}>
            <SelectTrigger className="h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {agents.map(agent => (
                <SelectItem key={agent.id} value={agent.id}>
                  {agent.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </Card>
  );
}