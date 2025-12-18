import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Sidebar } from "./chat/Sidebar";
import { ChatArea } from "./chat/ChatArea";
import { ChatInput } from "./chat/ChatInput";
import { useToast } from "@/hooks/use-toast";
import type { Message } from "@/types/message";
import type { Conversation } from "@/types/conversation";

export function ChatPage() {
  const { user, token, logout } = useAuth();
  const { toast } = useToast();
  
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);

  // Cargar conversaciones (simulado por ahora - puedes implementar endpoint después)
  useEffect(() => {
    // Por ahora dejamos vacío el historial
    // En el futuro puedes implementar GET /api/conversations
    setConversations([]);
  }, [token]);

  const handleSendMessage = async (content: string) => {
    if (!content.trim() || !token) return;

    const userMessage: Message = {
      id: `msg-user-${Date.now()}`,
      content,
      isBot: false,
      timestamp: new Date().toISOString(),
      conversationId: selectedConversationId || undefined,
    };

    // Agregar mensaje del usuario inmediatamente
    setMessages((prev) => [...prev, userMessage]);
    setIsSendingMessage(true);

    try {
      // Llamada al backend RAG
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          query: content,
          top_k: 5,
          return_context: false,
          return_sources: false,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Error al enviar mensaje');
      }

      const data = await response.json();

      // Agregar respuesta del bot
      const botMessage: Message = {
        id: `msg-bot-${Date.now()}`,
        content: data.answer,
        isBot: true,
        timestamp: new Date().toISOString(),
        conversationId: selectedConversationId || undefined,
      };

      setMessages((prev) => [...prev, botMessage]);

      // Crear conversación si es la primera vez
      if (!selectedConversationId) {
        const newConversation: Conversation = {
          id: `conv-${Date.now()}`,
          title: content.substring(0, 50),
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        setConversations((prev) => [newConversation, ...prev]);
        setSelectedConversationId(newConversation.id);
      }

    } catch (error) {
      console.error('Error sending message:', error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "No se pudo enviar el mensaje",
        variant: "destructive",
      });

      // Mensaje de error del bot
      const errorMessage: Message = {
        id: `msg-error-${Date.now()}`,
        content: "Lo siento, hubo un error al procesar tu mensaje. Por favor intenta de nuevo.",
        isBot: true,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsSendingMessage(false);
    }
  };

  const handleNewConversation = () => {
    setSelectedConversationId(null);
    setMessages([]);
  };

  const handleSelectConversation = (id: string) => {
    setSelectedConversationId(id);
    // En el futuro: cargar mensajes de esa conversación desde el backend
    setMessages([]);
  };

  const handleLogout = async () => {
    try {
      logout();
      toast({
        title: "Sesión cerrada",
        description: "Has cerrado sesión exitosamente",
      });
    } catch (err) {
      console.error("Logout failed:", err);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-1 flex">
      <Sidebar
        conversations={conversations}
        selectedConversationId={selectedConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onLogout={handleLogout}
        userName={user?.name || user?.email || "Usuario"}
        isLoading={isLoadingConversations}
      />
      
      <main className="flex-1 flex flex-col">
        <ChatArea
          messages={messages}
          isLoading={isLoadingMessages}
        />
        
        <ChatInput
          onSendMessage={handleSendMessage}
          disabled={isSendingMessage}
        />
      </main>
    </div>
  );
}