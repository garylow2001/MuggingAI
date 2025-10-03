import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
// removed unused Input import; using a textarea instead
import { Send, Bot, User } from "lucide-react";
// ...existing code...
import { SuggestedFollowUps } from "@/components/SuggestedFollowUps";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
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
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
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
        if (cs.length === 1) setSelectedCourseId(cs[0].id);
      } catch (e) {
        // ignore
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;
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
      // Call RAG API
      const params = new URLSearchParams();
      params.append("query", inputValue.trim());
      if (selectedCourseId)
        params.append("course_id", String(selectedCourseId));

      const res = await fetch(
        `http://localhost:8000/api/rag/query?${params.toString()}`
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "RAG request failed");
      }
      const data = await res.json();

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
        // store suggestions but do not auto-open the dropdown; user can open the pill
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

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
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

        {/* Input */}
        <div className="flex space-x-2 px-4 pb-6">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Ask a question about your course content..."
            disabled={isLoading}
            aria-label="Message"
            className="flex-1 min-h-[44px] max-h-44 resize-none overflow-auto rounded-md border bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <Button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading}
            size="sm"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
