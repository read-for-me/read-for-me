"use client";

import type React from "react";
import { useState, useEffect } from "react";
import { useTheme } from "next-themes";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArrowRight, Loader2, Sun, Moon } from "lucide-react";

interface HeaderProps {
  onSubmit?: (url: string) => void;
  isLoading?: boolean;
  showInput?: boolean;
  initialUrl?: string;
}

export function Header({ onSubmit, isLoading = false, showInput = true, initialUrl = "" }: HeaderProps) {
  const [url, setUrl] = useState(initialUrl);
  const [mounted, setMounted] = useState(false);
  const { theme, setTheme } = useTheme();

  // 클라이언트 마운트 확인 (hydration 이슈 방지)
  useEffect(() => {
    setMounted(true);
  }, []);

  // initialUrl이 변경되면 동기화
  useEffect(() => {
    if (initialUrl) {
      setUrl(initialUrl);
    }
  }, [initialUrl]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim() && !isLoading && onSubmit) {
      onSubmit(url.trim());
    }
  };

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="content-narrow px-4 md:px-6 py-3">
        <div className="flex items-center gap-4">
          {/* 로고 */}
          <div className="flex items-center gap-2 shrink-0">
            <h1 className="text-lg font-bold text-foreground">Read-For-Me</h1>
            <Badge variant="secondary" className="hidden sm:inline-flex text-xs">
              Beta
            </Badge>
          </div>

          {/* 컴팩트 입력창 - showInput이 true일 때만 표시 */}
          {showInput && (
            <form onSubmit={handleSubmit} className="flex-1 flex gap-2 animate-in fade-in slide-in-from-top-2 duration-300">
              <Input
                type="url"
                placeholder="URL을 입력하세요"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="flex-1 h-9 text-sm rounded-full px-4 bg-muted/50 border-0 focus-visible:ring-1"
                required
                disabled={isLoading}
              />
              <Button
                type="submit"
                size="sm"
                className="h-9 px-4 rounded-full shrink-0"
                disabled={isLoading || !url.trim()}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="h-4 w-4" />
                )}
              </Button>
            </form>
          )}

          {/* showInput이 false일 때 빈 공간 채우기 */}
          {!showInput && <div className="flex-1" />}

          {/* 다크모드 토글 */}
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 shrink-0"
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            {mounted && (
              theme === "dark" ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )
            )}
          </Button>

          {/* GitHub 링크 */}
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
          >
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path
                fillRule="evenodd"
                d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                clipRule="evenodd"
              />
            </svg>
          </a>
        </div>
      </div>
    </header>
  );
}
