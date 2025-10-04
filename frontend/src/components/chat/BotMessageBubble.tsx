import React from "react";
import { Bot } from "lucide-react";
import { BotMessage, RAGResponseMessage } from "@/types/chat";
import { SourceBadges } from "./SourceBadges";

interface BotMessageBubbleProps {
  message: BotMessage | RAGResponseMessage;
}

export const BotMessageBubble: React.FC<BotMessageBubbleProps> = ({
  message,
}) => {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-2xl p-3 shadow-sm transition bg-muted">
        <div className="flex items-start space-x-2">
          <Bot className="h-4 w-4 mt-0.5 text-primary" />
          <div className="w-full">
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
            <div className="flex items-center justify-between text-xs opacity-70 mt-1">
              <span>{message.timestamp.toLocaleTimeString()}</span>
              {message.messageType === "rag" && (
                <span className="flex items-center space-x-2">
                  <SourceBadges
                    sources={(message as RAGResponseMessage).sources}
                  />
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
