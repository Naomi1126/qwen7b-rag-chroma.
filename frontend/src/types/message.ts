export type Message = {
  id: string;
  content: string;
  isBot: boolean;
  timestamp: string;
  userId?: string;
};
