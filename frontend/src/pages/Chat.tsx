import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
// removed unused Input import; using a textarea instead
import { Send, Bot, User, ChevronUp } from "lucide-react";
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <Link to="/">
          <Button variant="outline" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Dashboard
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-semibold">AI Tutor</h1>
          <p className="text-sm text-muted-foreground">
            Ask questions about your course content
          </p>
        </div>
      </div>

      {/* Chat Interface */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Chat Messages */}
        <div className="lg:col-span-3">
          <Card
            className="w-full flex flex-col"
            style={{
              height: "calc(100vh - 140px)",
              maxHeight: "1440px",
              minHeight: "420px",
            }}
          >
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Bot className="h-5 w-5 text-primary" />
                <span>Chat with AI Tutor</span>
              </CardTitle>
            </CardHeader>
            {/* min-h-0 is required so the flex child can overflow and become scrollable */}
            <CardContent className="flex-1 flex flex-col min-h-0 relative">
              {/* Messages */}
              <div
                ref={messagesRef}
                className="flex-1 overflow-y-auto space-y-4 mb-4 px-2 py-1 min-h-0"
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

                          {/* timestamp and sources inline */}
                          <div className="flex items-center justify-between text-xs opacity-70 mt-1">
                            <span>
                              {message.timestamp.toLocaleTimeString()}
                            </span>
                            <span className="flex items-center space-x-2">
                              {message.sources &&
                                message.sources.length > 0 && (
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

              {/* Follow-ups: pill when closed; glassmorphic shadcn-styled dropdown when open */}
              {followUps.length > 0 && (
                <div className="mb-3 w-full flex justify-center">
                  <div className="w-full max-w-3xl">
                    {/* pill (hidden while open) */}
                    {!followUpsOpen && (
                      <div className="flex justify-center">
                        <button
                          onClick={() => setFollowUpsOpen(true)}
                          className="mx-auto flex items-center gap-2 px-4 py-2 rounded-full bg-white/20 backdrop-blur-sm border border-slate-200/20 shadow-sm hover:shadow-md transition"
                        >
                          <span className="text-sm font-medium">
                            Suggested follow-ups
                          </span>
                          <ChevronUp className="h-4 w-4" />
                        </button>
                      </div>
                    )}

                    {/* dropdown panel (shadcn style) */}
                    {followUpsOpen && (
                      <div className="mt-2 -translate-y-2 w-full max-h-[48vh] overflow-auto p-4 flex flex-col gap-3 rounded-2xl bg-white/10 backdrop-blur-md border border-slate-200/10 shadow-2xl">
                        <div className="flex items-center justify-between">
                          <div className="text-sm font-semibold">
                            Suggested follow-ups
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Click a suggestion to populate the input
                          </div>
                        </div>

                        <div className="flex flex-col gap-2">
                          {followUps.map((q, i) => (
                            <Button
                              key={i}
                              variant="ghost"
                              onClick={() => {
                                setInputValue(q);
                                setFollowUpsOpen(false);
                              }}
                              className="w-full justify-start px-3 py-2 rounded-lg text-sm 
                                hover:bg-gray-100 whitespace-normal break-words 
                                overflow-hidden text-left transition-colors"
                            >
                              {q}
                            </Button>
                          ))}
                        </div>

                        {/* bottom-centered down arrow to close */}
                        <div className="flex justify-center">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setFollowUpsOpen(false)}
                            className="rounded-full w-9 h-9 flex items-center justify-center"
                          >
                            <ChevronUp className="h-4 w-4 rotate-180" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Input */}
              <div className="flex space-x-2">
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
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
              >
                Generate Summary
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
              >
                Extract Key Points
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
              >
                Create Quiz
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Course Context</CardTitle>
            </CardHeader>
            <CardContent>
              <label className="block text-sm mb-2">Query course</label>
              <select
                className="w-full border p-2 rounded"
                value={selectedCourseId ?? ""}
                onChange={(e) =>
                  setSelectedCourseId(
                    e.target.value ? parseInt(e.target.value) : null
                  )
                }
              >
                <option value="">(Search all courses)</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>

              {/* follow-up buttons are rendered inside the chat area (see input area) */}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
