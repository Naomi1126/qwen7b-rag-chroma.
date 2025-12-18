import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Bot, User } from "lucide-react";
import type { Message } from "@/types/message";

type ChatAreaProps = {
  messages: Message[];
  isLoading: boolean;
};

export function ChatArea({ messages, isLoading }: ChatAreaProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-gray-400">Cargando mensajes...</div>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <Bot className="w-16 h-16 mx-auto mb-4 text-accent" />
          <h2 className="text-2xl font-headline font-bold text-foreground mb-2">
            Bienvenido al Asistente Virtual
          </h2>
          <p className="text-gray-400">
            Inicia una conversación escribiendo tu consulta abajo.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1 p-6" ref={scrollRef}>
      <div className="max-w-4xl mx-auto space-y-6">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex gap-4 ${message.isBot ? "justify-start" : "justify-end"}`}
          >
            {message.isBot && (
              <div className="w-10 h-10 rounded-full bg-accent flex items-center justify-center flex-shrink-0">
                <Bot className="w-5 h-5 text-accent-foreground" />
              </div>
            )}
            
            <div
              className={`max-w-[70%] rounded-2xl px-5 py-3 ${
                message.isBot
                  ? "bg-card text-card-foreground"
                  : "bg-accent text-accent-foreground"
              }`}
            >
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {message.content}
              </p>
              <p className="text-xs opacity-60 mt-2">
                {new Date(message.timestamp).toLocaleTimeString('es-ES', {
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </p>
            </div>

            {!message.isBot && (
              <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
                <User className="w-5 h-5 text-muted-foreground" />
              </div>
            )}
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}