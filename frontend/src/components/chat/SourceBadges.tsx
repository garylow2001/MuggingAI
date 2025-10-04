import React from "react";
import { RAGResponseMessage } from "@/types/chat";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";

interface SourceBadgesProps {
  sources: RAGResponseMessage["sources"];
}

export const SourceBadges: React.FC<SourceBadgesProps> = ({ sources }) => {
  if (!sources || sources.length === 0) {
    return (
      <span className="inline-flex items-center text-[10px] bg-muted/60 px-2 py-0.5 rounded-full border">
        <span className="truncate max-w-[10rem]">No sources available</span>
      </span>
    );
  }

  return (
    <>
      {sources.map((source, idx) => (
        <TooltipProvider key={idx}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex items-center text-[10px] bg-muted/60 px-2 py-0.5 rounded-full border cursor-default">
                <span className="mr-1">📄</span>
                <span className="truncate max-w-[10rem]">
                  {source.course} {source.file} (p. {source.page})
                </span>
              </span>
            </TooltipTrigger>
            <TooltipContent side="top" className="text-xs">
              <p>
                <strong>Course:</strong> {source.course}
              </p>
              <p>
                <strong>File:</strong> {source.file}
              </p>
              <p>
                <strong>Page:</strong> {source.page}
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ))}
    </>
  );
};
