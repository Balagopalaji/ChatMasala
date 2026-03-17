import { ChatNode } from '../types';
import { ArrowRight, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { Input } from './ui/input';
import { Button } from './ui/button';

interface WorkflowDiagramProps {
  chats: ChatNode[];
  onUpdateChat?: (chat: ChatNode) => void;
}

export function WorkflowDiagram({ chats, onUpdateChat }: WorkflowDiagramProps) {
  const [dragSourceId, setDragSourceId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  // Detect loops: if a chat's outputTo points to an earlier chat in the sequence
  const getLoopInfo = (chat: ChatNode, index: number) => {
    if (!chat.outputTo) return null;
    const targetIndex = chats.findIndex(c => c.id === chat.outputTo);
    if (targetIndex !== -1 && targetIndex <= index) {
      return { targetIndex, isLoop: true };
    }
    return null;
  };

  // Get all chats involved in a loop
  const getLoopRange = (chat: ChatNode, index: number) => {
    const loopInfo = getLoopInfo(chat, index);
    if (!loopInfo) return null;
    return {
      startIndex: loopInfo.targetIndex,
      endIndex: index,
    };
  };

  // Check if current index is part of any loop
  const isInLoop = (currentIndex: number) => {
    for (let i = 0; i < chats.length; i++) {
      const loopRange = getLoopRange(chats[i], i);
      if (loopRange && currentIndex >= loopRange.startIndex && currentIndex <= loopRange.endIndex) {
        return loopRange;
      }
    }
    return null;
  };

  const handleDragStart = (chatId: string, e: React.DragEvent) => {
    setDragSourceId(chatId);
    e.dataTransfer.effectAllowed = 'link';
  };

  const handleDragOver = (chatId: string, e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'link';
    setDragOverId(chatId);
  };

  const handleDragLeave = () => {
    setDragOverId(null);
  };

  const handleDrop = (targetChatId: string, e: React.DragEvent) => {
    e.preventDefault();
    if (!dragSourceId || dragSourceId === targetChatId || !onUpdateChat) return;

    const sourceChat = chats.find(c => c.id === dragSourceId);
    if (!sourceChat) return;

    // Update the source chat to output to the target
    onUpdateChat({
      ...sourceChat,
      outputTo: targetChatId,
    });

    setDragSourceId(null);
    setDragOverId(null);
  };

  const handleDragEnd = () => {
    setDragSourceId(null);
    setDragOverId(null);
  };

  const updateLoopIterations = (chatId: string, iterations: number) => {
    if (!onUpdateChat) return;
    const chat = chats.find(c => c.id === chatId);
    if (!chat) return;
    
    onUpdateChat({
      ...chat,
      loopMaxIterations: iterations > 0 ? iterations : undefined,
    });
  };

  return (
    <div className="w-full h-full bg-muted/20 overflow-x-auto">
      <div className="h-full flex items-center justify-center p-8 min-w-max">
        {chats.length === 0 ? (
          <p className="text-muted-foreground">No chats in workflow yet</p>
        ) : (
          <div className="flex items-center gap-4 relative">
            {chats.map((chat, index) => {
              const loopInfo = getLoopInfo(chat, index);
              const loopRange = getLoopRange(chat, index);
              const hasForwardConnection = chat.outputTo && chats.find(c => c.id === chat.outputTo) && !loopInfo;
              const isDragSource = dragSourceId === chat.id;
              const isDragOver = dragOverId === chat.id;
              
              return (
                <div key={chat.id} className="flex items-center gap-4">
                  <div className="relative group">
                    {/* Loop visual wrapper - only on the last chat in loop */}
                    {loopRange && (
                      <div 
                        className="absolute -inset-4 border-2 border-dashed border-orange-500 rounded-xl bg-orange-500/5 pointer-events-none"
                        style={{
                          width: `calc(${(loopRange.endIndex - loopRange.startIndex + 1) * 200 + (loopRange.endIndex - loopRange.startIndex) * 32}px)`,
                          left: `calc(-${(index - loopRange.startIndex) * 200 + (index - loopRange.startIndex) * 32}px - 16px)`,
                        }}
                      >
                        <div className="absolute -top-8 left-4 bg-orange-500 text-white px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-2">
                          <RefreshCw className="size-3" />
                          Loop Max: {chat.loopMaxIterations || '∞'}
                        </div>
                      </div>
                    )}

                    <div 
                      className={`px-6 py-4 rounded-lg border-2 bg-background shadow-lg min-w-[160px] hover:shadow-xl transition-all cursor-grab active:cursor-grabbing ${
                        isDragSource ? 'border-blue-500 shadow-blue-500/50' : 
                        isDragOver ? 'border-green-500 shadow-green-500/50 scale-105' : 
                        'border-primary'
                      }`}
                      draggable
                      onDragStart={(e) => handleDragStart(chat.id, e)}
                      onDragOver={(e) => handleDragOver(chat.id, e)}
                      onDragLeave={handleDragLeave}
                      onDrop={(e) => handleDrop(chat.id, e)}
                      onDragEnd={handleDragEnd}
                    >
                      <div className="font-semibold text-sm mb-1">{chat.name || `Chat ${index + 1}`}</div>
                      <div className="text-xs text-muted-foreground">Agent: {chat.agentId}</div>
                      <div className="text-xs text-muted-foreground mt-1">
                        ID: #{chat.id.slice(0, 6)}
                      </div>
                      {isDragSource && (
                        <div className="text-xs text-blue-500 font-medium mt-2">
                          Drop on target →
                        </div>
                      )}
                    </div>
                    <div className="absolute -top-2 -right-2 bg-primary text-primary-foreground rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold">
                      {index + 1}
                    </div>
                    
                    {/* Loop iteration control */}
                    {loopInfo && onUpdateChat && (
                      <div className="absolute -bottom-20 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 min-w-[140px]">
                        <div className="text-xs text-orange-500 font-medium whitespace-nowrap">
                          loops to #{chats[loopInfo.targetIndex].id.slice(0, 6)}
                        </div>
                        <div className="flex items-center gap-1 bg-background border-2 border-orange-500 rounded-md p-1">
                          <Input
                            type="number"
                            min="1"
                            max="100"
                            value={chat.loopMaxIterations || ''}
                            onChange={(e) => updateLoopIterations(chat.id, parseInt(e.target.value) || 0)}
                            placeholder="∞"
                            className="h-6 w-16 text-xs text-center"
                          />
                          <span className="text-xs text-muted-foreground whitespace-nowrap">max</span>
                        </div>
                      </div>
                    )}
                  </div>
                  {hasForwardConnection && (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <ArrowRight className="size-6 animate-pulse" />
                      <span className="text-xs">
                        routes to #{chat.outputTo!.slice(0, 6)}
                      </span>
                    </div>
                  )}
                  {!chat.outputTo && index < chats.length - 1 && (
                    <div className="w-8" />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}