import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();

  const navItems = [
    { path: "/", label: "Dashboard", icon: "🏠" },
    { path: "/chat", label: "AI Tutor", icon: "🤖" },
  ];

  return (
    <div className="app h-screen w-screen flex bg-background">
      <div className="main flex-1 flex flex-col">
        {/* Topbar */}
        <header className="topbar h-16 border-b bg-card flex-shrink-0 flex items-center px-6">
          <h1 className="text-2xl font-bold text-primary">🧠 MindCrush</h1>
          <nav className="hidden md:flex space-x-4 ml-8">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  location.pathname === item.path
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                }`}
              >
                <span className="mr-2">{item.icon}</span>
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center space-x-2 ml-auto">
            <Button variant="outline" size="sm">
              Settings
            </Button>
          </div>
        </header>

        {/* Main section */}
        <div className="chat-container flex-1 overflow-y-auto px-0 md:px-6 py-4">
          {children}
        </div>
      </div>
    </div>
  );
}
