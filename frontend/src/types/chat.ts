import { RagQuerySource } from "@/lib/api";

export interface Message {
  id: string;
  content: string;
  role: "user" | "assistant";
  timestamp: Date;
}

export interface HumanMessage extends Message {
  role: "user";
}

export interface BotMessage extends Message {
  role: "assistant";
  messageType?: string;
}

export interface RAGResponseMessage extends BotMessage {
  messageType: "rag";
  sources: RagQuerySource[];
}

export type ChatMessage = HumanMessage | BotMessage | RAGResponseMessage;
