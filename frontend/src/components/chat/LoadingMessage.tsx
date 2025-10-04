import React from "react";
import { Bot } from "lucide-react";

const LoadingMessage: React.FC = () => {
  return (
    <div className="flex justify-start">
      <div className="bg-muted rounded-lg p-3">
        <div className="flex items-center space-x-2">
          <Bot className="h-4 w-4 text-primary" />
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-primary rounded-full animate-bounce"></div>
            <div
              className="w-2 h-2 bg-primary rounded-full animate-bounce"
              style={{ animationDelay: "0.1s" }}
            ></div>
            <div
              className="w-2 h-2 bg-primary rounded-full animate-bounce"
              style={{ animationDelay: "0.2s" }}
            ></div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoadingMessage;
