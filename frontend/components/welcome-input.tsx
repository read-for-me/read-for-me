"use client";

import type React from "react";
import { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  ArrowRight,
  Loader2,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Sparkles,
} from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { checkUrlSupport, type UrlSupportResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

interface WelcomeInputProps {
  onSubmit: (url: string) => void;
  isLoading?: boolean;
}

/** 플랫폼 표시 이름 매핑 */
const PLATFORM_LABELS: Record<string, string> = {
  geeknews: "GeekNews",
  medium: "Medium",
  generic: "웹 페이지",
};

/** URL 유효성 검사 (클라이언트 사이드) */
function isValidUrlFormat(url: string): boolean {
  if (!url.trim()) return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function WelcomeInput({
  onSubmit,
  isLoading = false,
}: WelcomeInputProps) {
  const [url, setUrl] = useState("");
  const [validationState, setValidationState] = useState<
    "idle" | "validating" | "valid" | "invalid"
  >("idle");
  const [supportInfo, setSupportInfo] = useState<UrlSupportResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 디바운스된 URL 검증
  const validateUrl = useCallback(async (inputUrl: string) => {
    // 빈 입력이면 초기 상태로
    if (!inputUrl.trim()) {
      setValidationState("idle");
      setSupportInfo(null);
      setErrorMessage(null);
      return;
    }

    // 기본 URL 형식 검사 (클라이언트 사이드)
    if (!isValidUrlFormat(inputUrl)) {
      setValidationState("invalid");
      setSupportInfo(null);
      setErrorMessage("앗, 올바른 주소인지 확인해 주세요. URL 형식이 필요해요.");
      return;
    }

    // 서버 검증 시작
    setValidationState("validating");
    setErrorMessage(null);

    try {
      const result = await checkUrlSupport(inputUrl);
      setSupportInfo(result);

      if (result.is_supported) {
        setValidationState("valid");
        setErrorMessage(null);
      } else {
        setValidationState("invalid");
        setErrorMessage(result.error_message || "이 URL은 지원되지 않습니다.");
      }
    } catch {
      // 네트워크 에러 시에도 제출은 허용 (서버에서 최종 검증)
      setValidationState("idle");
      setSupportInfo(null);
      setErrorMessage(null);
    }
  }, []);

  // URL 변경 시 디바운스 검증
  useEffect(() => {
    // 이전 타이머 취소
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // 300ms 디바운스
    debounceTimerRef.current = setTimeout(() => {
      validateUrl(url);
    }, 300);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [url, validateUrl]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim() && !isLoading && validationState !== "invalid") {
      onSubmit(url.trim());
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUrl(e.target.value);
  };

  // 입력 필드 테두리 색상 결정
  const getInputClassName = () => {
    const baseClass =
      "h-14 text-base rounded-full px-6 pr-14 bg-muted/30 border focus-visible:ring-2";

    if (validationState === "invalid") {
      return cn(baseClass, "border-destructive focus-visible:ring-destructive/50");
    }
    if (validationState === "valid") {
      return cn(baseClass, "border-green-500 focus-visible:ring-green-500/50");
    }
    return cn(baseClass, "border-border/50 focus-visible:ring-primary/50");
  };

  // 제출 버튼 비활성화 조건
  const isSubmitDisabled =
    isLoading || !url.trim() || validationState === "invalid";

  return (
    <div className="flex-1 flex items-center justify-center px-4 md:px-6">
      <div className="w-full max-w-xl space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        {/* 타이틀 */}
        <div className="text-center space-y-3">
          <h2 className="text-2xl md:text-3xl font-bold text-foreground">
            바쁜 당신을 위한 뉴스 리포팅
          </h2>
          <p className="text-muted-foreground">
            URL만 넣으면 요약과 오디오를 생성합니다
          </p>
        </div>

        {/* 입력 폼 */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="relative">
            <Input
              type="url"
              placeholder="https://..."
              value={url}
              onChange={handleInputChange}
              className={getInputClassName()}
              required
              disabled={isLoading}
              aria-invalid={validationState === "invalid"}
              aria-describedby={errorMessage ? "url-error" : undefined}
            />
            <Button
              type="submit"
              size="icon"
              className="absolute right-2 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full"
              disabled={isSubmitDisabled}
            >
              {isLoading ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : validationState === "validating" ? (
                <Loader2 className="h-5 w-5 animate-spin opacity-50" />
              ) : (
                <ArrowRight className="h-5 w-5" />
              )}
            </Button>
          </div>

          {/* 에러 메시지 */}
          {errorMessage && validationState === "invalid" && (
            <div
              id="url-error"
              className="flex items-center gap-2 text-sm text-destructive animate-in fade-in slide-in-from-top-1 duration-200"
            >
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* 플랫폼 감지 결과 */}
          {supportInfo?.is_supported && validationState === "valid" && (
            <div className="flex items-center justify-center gap-2 animate-in fade-in slide-in-from-top-1 duration-200">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <span className="text-sm text-muted-foreground">
                {supportInfo.is_specialized ? (
                  <>
                    <Badge variant="secondary" className="mr-1">
                      {PLATFORM_LABELS[supportInfo.platform || ""] ||
                        supportInfo.platform}
                    </Badge>
                    로 감지됨
                  </>
                ) : (
                  <>
                    <Badge variant="outline" className="mr-1">
                      {PLATFORM_LABELS.generic}
                    </Badge>
                    로 처리됩니다
                  </>
                )}
              </span>
            </div>
          )}
        </form>

        {/* 지원 플랫폼 안내 Popover */}
        <div className="text-center">
          <Popover>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="inline-flex items-center gap-1 text-xs text-muted-foreground/70 hover:text-muted-foreground underline-offset-4 hover:underline transition-colors"
              >
                <HelpCircle className="h-3 w-3" />
                지원 플랫폼 안내
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-64 p-3" align="center">
              <div className="space-y-2.5 text-sm">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-3.5 w-3.5 text-primary shrink-0" />
                  <span className="font-medium">GeekNews 특히 잘 돼요</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
                  <span>뉴스·블로그·기술 미디어</span>
                </div>
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                  <span className="text-muted-foreground">
                    일부 언론사 제한될 수 있음
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <XCircle className="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" />
                  <span className="text-muted-foreground/70">
                    YouTube, SNS 미지원
                  </span>
                </div>
              </div>
            </PopoverContent>
          </Popover>
        </div>
      </div>
    </div>
  );
}
