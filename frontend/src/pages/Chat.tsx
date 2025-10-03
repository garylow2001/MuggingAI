import React, { useState, useEffect } from "react";
// removed unused Input import; using a textarea instead
import { Send, Bot, User } from "lucide-react";
import {
  PromptInput,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputToolbar,
  PromptInputTools,
} from "@/components/ui/prompt-input";
import { MultiSelect } from "@/components/ui/multi-select";
import { SuggestedFollowUps } from "@/components/SuggestedFollowUps";
import { api } from "@/lib/api";

interface Message {
  id: string;
  content: string;
  role: "user" | "assistant";
  timestamp: Date;
  // optional list of source chapter titles to show inline with the timestamp
  sources?: string[];
}

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      content:
        "Hello! I'm your AI tutor. I can help you understand your course materials, answer questions, and generate summaries. What would you like to know?",
      role: "assistant",
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [courses, setCourses] = useState<{ id: number; name: string }[]>([]);
  const [selectedCourseIds, setSelectedCourseIds] = useState<number[]>([]);
  const [followUps, setFollowUps] = useState<string[]>([]);
  const [followUpsOpen, setFollowUpsOpen] = useState(false);
  const messagesRef = React.useRef<HTMLDivElement | null>(null);
  const inputRef = React.useRef<HTMLTextAreaElement | null>(null);

  // auto-scroll to bottom when messages update or while loading
  useEffect(() => {
    const el = messagesRef.current;
    if (!el) return;
    // smooth scroll to bottom
    try {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    } catch (e) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, isLoading]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const cs = await api.getCourses();
        if (!mounted) return;
        setCourses(cs.map((c: any) => ({ id: c.id, name: c.name })));
      } catch (e) {
        // ignore
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || selectedCourseIds.length === 0) return;
    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      role: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);
    setFollowUps([]);
    setFollowUpsOpen(false);

    try {
      const data = await api.ragQuery({
        query: inputValue.trim(),
        course_ids: selectedCourseIds,
      });

      // Build assistant message with deduplicated sources attached
      let sources: string[] | undefined = undefined;
      if (
        data.sources &&
        Array.isArray(data.sources) &&
        data.sources.length > 0
      ) {
        const chapterSet = new Set<string>(
          data.sources.map((s: any) =>
            String(s.chapter || s.chapter_title || "Unknown")
          )
        );
        sources = Array.from(chapterSet);
      }

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: data.answer || data.error || "No answer returned",
        role: "assistant",
        timestamp: new Date(),
        sources,
      };

      setMessages((prev) => [...prev, aiMessage]);

      if (data.follow_up_questions && Array.isArray(data.follow_up_questions)) {
        setFollowUps(data.follow_up_questions);
        setFollowUpsOpen(false);
      }
    } catch (e: any) {
      const errMsg: Message = {
        id: (Date.now() + 3).toString(),
        content: `Error: ${e?.message || String(e)}`,
        role: "assistant",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  // auto-resize textarea when the inputValue changes
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    const max = 176; // px, roughly 11 lines
    const next = Math.min(el.scrollHeight, max);
    el.style.height = `${next}px`;
  }, [inputValue]);

  return (
    <div className="flex flex-col h-full w-full bg-background">
      <div className="flex flex-col h-full">
        <div
          ref={messagesRef}
          className="flex-1 overflow-y-auto space-y-4 px-4 py-6"
        >
          {/* ...existing message rendering code... */}
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] rounded-2xl p-3 shadow-sm transition ${
                  message.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                <div className="flex items-start space-x-2">
                  {message.role === "assistant" && (
                    <Bot className="h-4 w-4 mt-0.5 text-primary" />
                  )}
                  {message.role === "user" && (
                    <User className="h-4 w-4 mt-0.5" />
                  )}
                  <div className="w-full">
                    <p className="text-sm whitespace-pre-wrap">
                      {message.content}
                    </p>
                    <div className="flex items-center justify-between text-xs opacity-70 mt-1">
                      <span>{message.timestamp.toLocaleTimeString()}</span>
                      <span className="flex items-center space-x-2">
                        {message.sources && message.sources.length > 0 && (
                          <>
                            {message.sources.map((s, idx) => (
                              <span
                                key={idx}
                                className="inline-flex items-center text-[10px] bg-muted/60 px-2 py-0.5 rounded-full border"
                              >
                                <span className="mr-1">📄</span>
                                <span className="truncate max-w-[10rem]">
                                  {s}
                                </span>
                              </span>
                            ))}
                          </>
                        )}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
          {isLoading && (
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
          )}
        </div>

        {/* Suggested follow-ups */}
        <SuggestedFollowUps
          followUps={followUps}
          open={followUpsOpen}
          setOpen={setFollowUpsOpen}
          setInputValue={setInputValue}
        />

        {/* Refactored input using prompt-input.tsx API */}
        <div className="px-4 mb-4 w-full">
          <PromptInput
            onSubmit={(e: React.FormEvent<HTMLFormElement>) => {
              e.preventDefault();
              handleSendMessage();
            }}
          >
            <PromptInputTextarea
              ref={inputRef}
              value={inputValue}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                setInputValue(e.target.value)
              }
              placeholder="Ask a question about your course content..."
              disabled={isLoading}
            />
            <PromptInputToolbar>
              <PromptInputTools>
                <MultiSelect
                  options={courses.map((course) => ({
                    label: course.name,
                    value: String(course.id),
                  }))}
                  value={selectedCourseIds.map(String)}
                  onValueChange={(vals: string[]) =>
                    setSelectedCourseIds(vals.map(Number))
                  }
                  placeholder="Course content to query from"
                  maxCount={3}
                  searchable={true}
                  className="min-w-[180px]"
                />
              </PromptInputTools>
              <PromptInputSubmit
                disabled={
                  !inputValue.trim() ||
                  isLoading ||
                  selectedCourseIds.length === 0
                }
                status={isLoading ? "streaming" : "ready"}
              >
                <Send className="h-5 w-5" />
              </PromptInputSubmit>
            </PromptInputToolbar>
          </PromptInput>
        </div>
      </div>
    </div>
  );
}
