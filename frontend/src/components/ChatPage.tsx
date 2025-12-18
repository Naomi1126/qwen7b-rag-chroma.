import { useState } from "react";
import { useAuth, useQuery, useMutation } from "@animaapp/playground-react-sdk";
import { Sidebar } from "./chat/Sidebar";
import { ChatArea } from "./chat/ChatArea";
import { ChatInput } from "./chat/ChatInput";
import type { Message } from "@/types/message";
import type { Conversation } from "@/types/conversation";

export function ChatPage() {
  const { user, logout } = useAuth();
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);

  const { data: conversations, isPending: isLoadingConversations } = useQuery('Conversation', {
    where: { userId: { eq: user?.id } },
    orderBy: { updatedAt: 'desc' }
  });

  const { data: messages, isPending: isLoadingMessages } = useQuery('Message', 
    selectedConversationId 
      ? { where: { conversationId: { eq: selectedConversationId } }, orderBy: { timestamp: 'asc' } }
      : undefined
  );

  const { create: createMessage, isPending: isSendingMessage } = useMutation('Message');
  const { create: createConversation } = useMutation('Conversation');

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;

    let conversationId = selectedConversationId;

    if (!conversationId) {
      const newConversation = await createConversation({
        title: content.substring(0, 50),
        userId: user!.id,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      });
      conversationId = newConversation.id;
      setSelectedConversationId(conversationId);
    }

    await createMessage({
      content,
      isBot: false,
      timestamp: new Date().toISOString(),
      userId: user!.id,
      conversationId
    });

    setTimeout(async () => {
      const botResponses = [
        "Entiendo tu consulta. ¿Podrías proporcionar más detalles?",
        "Estoy procesando tu solicitud. Un momento por favor.",
        "Gracias por tu mensaje. Te ayudaré con eso.",
        "He recibido tu información. ¿Hay algo más en lo que pueda asistirte?",
        "Perfecto. Déjame verificar esa información para ti."
      ];
      
      const randomResponse = botResponses[Math.floor(Math.random() * botResponses.length)];
      
      await createMessage({
        content: randomResponse,
        isBot: true,
        timestamp: new Date().toISOString(),
        conversationId
      });
    }, 1000);
  };

  const handleNewConversation = () => {
    setSelectedConversationId(null);
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch (err) {
      console.error("Logout failed:", err);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-1 flex">
      <Sidebar
        conversations={conversations || []}
        selectedConversationId={selectedConversationId}
        onSelectConversation={setSelectedConversationId}
        onNewConversation={handleNewConversation}
        onLogout={handleLogout}
        userName={user?.name || "Usuario"}
        isLoading={isLoadingConversations}
      />
      
      <main className="flex-1 flex flex-col">
        <ChatArea
          messages={messages || []}
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
