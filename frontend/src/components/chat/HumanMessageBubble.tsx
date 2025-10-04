import React from "react";
import { User } from "lucide-react";
import { HumanMessage } from "@/types/chat";

interface HumanMessageBubbleProps {
  message: HumanMessage;
}

export const HumanMessageBubble: React.FC<HumanMessageBubbleProps> = ({
  message,
}) => {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-2xl p-3 shadow-sm transition bg-primary text-primary-foreground">
        <div className="flex items-start space-x-2">
          <User className="h-4 w-4 mt-0.5" />
          <div className="w-full">
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
            <div className="flex items-center justify-between text-xs opacity-70 mt-1">
              <span>{message.timestamp.toLocaleTimeString()}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
