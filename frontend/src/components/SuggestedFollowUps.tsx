import { Button } from "@/components/ui/button";
import { ChevronUp } from "lucide-react";

interface SuggestedFollowUpsProps {
  followUps: string[];
  open: boolean;
  setOpen: (open: boolean) => void;
  setInputValue: (value: string) => void;
}

export function SuggestedFollowUps({
  followUps,
  open,
  setOpen,
  setInputValue,
}: SuggestedFollowUpsProps) {
  if (!followUps.length) return null;
  return (
    <div className="mb-3 w-full flex justify-center">
      <div className="w-full max-w-3xl">
        {!open && (
          <div className="flex justify-center">
            <button
              onClick={() => setOpen(true)}
              className="mx-auto flex items-center gap-2 px-4 py-2 rounded-full bg-white/20 backdrop-blur-sm border border-slate-200/20 shadow-sm hover:shadow-md transition"
            >
              <span className="text-sm font-medium">Suggested follow-ups</span>
              <ChevronUp className="h-4 w-4" />
            </button>
          </div>
        )}
        {open && (
          <div className="-translate-y-2 w-full max-h-[48vh] overflow-auto pt-4 px-4 flex flex-col rounded-2xl bg-white/10 backdrop-blur-md border border-slate-200/10 shadow-2xl">
            <div className="flex flex-col">
              {followUps.map((q, i) => (
                <Button
                  key={i}
                  variant="ghost"
                  onClick={() => {
                    setInputValue(q);
                    setOpen(false);
                  }}
                  className="w-full h-fit justify-start px-3 py-2 rounded-lg text-sm hover:bg-gray-100 whitespace-normal break-words overflow-hidden text-left transition-colors"
                >
                  {q}
                </Button>
              ))}
            </div>
            <div className="flex justify-center">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setOpen(false)}
                className="rounded-full w-9 h-9"
              >
                <ChevronUp className="rotate-180" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
