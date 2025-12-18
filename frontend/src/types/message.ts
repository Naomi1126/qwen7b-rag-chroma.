export interface Message {
  id: string;
  content: string;
  isBot: boolean;
  timestamp: string;
  conversationId?: string;
}