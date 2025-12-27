"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Loader2,
} from "lucide-react";
import type { SummarizeResponse } from "@/lib/api";
import type { StreamingState } from "@/app/page";

interface InsightCardProps {
  isLoading?: boolean;
  isProcessing?: boolean;
  data: SummarizeResponse | null;
  error?: string;
  streaming?: StreamingState;
}

/**
 * Thinking 텍스트에서 escaped newlines를 실제 줄바꿈으로 변환하고 정리합니다.
 */
function cleanThinkingText(text: string): string {
  if (!text) return "";

  // 문자열로 들어온 \n\n을 실제 줄바꿈으로 변환
  let cleaned = text.replace(/\\n\\n/g, "\n\n");
  cleaned = cleaned.replace(/\\n/g, "\n");

  // 연속된 빈 줄을 하나로 정리
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n");

  return cleaned.trim();
}

/**
 * 스트리밍 content에서 bullet points를 실시간 파싱
 */
function parseStreamingBulletPoints(content: string): string[] {
  if (!content) return [];

  // [요약] 섹션 이후의 bullet points 추출
  const summaryMatch = content.match(/\[요약\]\s*\n([\s\S]*?)$/);
  const summaryText = summaryMatch ? summaryMatch[1] : content;

  const lines = summaryText.split("\n");
  const bulletPoints: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (
      trimmed.startsWith("•") ||
      trimmed.startsWith("-") ||
      trimmed.startsWith("*")
    ) {
      const point = trimmed.replace(/^[•\-\*]\s*/, "").trim();
      if (point) {
        bulletPoints.push(point);
      }
    }
  }

  return bulletPoints;
}

/**
 * 스트리밍 content에서 main_topic 파싱
 */
function parseStreamingMainTopic(content: string): string | null {
  if (!content) return null;

  const topicMatch = content.match(/\[주제\]\s*\n(.+?)(?:\n\n|\n\[|$)/s);
  return topicMatch ? topicMatch[1].trim() : null;
}

export function InsightCard({
  isLoading = false,
  isProcessing = false,
  data,
  error,
  streaming,
}: InsightCardProps) {
  // Streaming 중에는 기본적으로 닫힌 상태 (title만 표시), 완료 후에는 열린 상태
  const [isThinkingOpen, setIsThinkingOpen] = useState(false);

  // 스트리밍 중인지 확인
  const isStreaming = streaming?.isStreaming ?? false;
  const hasThinking = Boolean(streaming?.thinking);
  const hasStreamingContent = Boolean(streaming?.content);

  // 현재 thinking 블록 정보 (cleaned)
  const currentTitle = cleanThinkingText(streaming?.currentThinkingTitle || "");
  const currentContent = cleanThinkingText(
    streaming?.currentThinkingContent || ""
  );
  const fullThinkingContent = cleanThinkingText(streaming?.thinking || "");

  // 스트리밍 중일 때 실시간 파싱
  const streamingBulletPoints =
    isStreaming || (!data && hasStreamingContent)
      ? parseStreamingBulletPoints(streaming?.content || "")
      : [];
  const streamingMainTopic =
    isStreaming || (!data && hasStreamingContent)
      ? parseStreamingMainTopic(streaming?.content || "")
      : null;

  // 아무 상태도 아니면 표시하지 않음
  if (
    !isLoading &&
    !isProcessing &&
    !data &&
    !error &&
    !isStreaming &&
    !hasStreamingContent
  ) {
    return null;
  }

  // 에러 상태
  if (error) {
    return (
      <div className="minimal-section">
        <div className="flex items-start gap-3 p-4 rounded-lg bg-destructive/5 border border-destructive/20">
          <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium text-destructive">요약 실패</h4>
            <p className="text-sm text-muted-foreground mt-1">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="minimal-section">
      {/* 섹션 타이틀 */}
      <h3 className="section-header">
        <Sparkles className="h-5 w-5 text-primary" />
        Bullet points
      </h3>

      {/* Thinking 섹션 (스트리밍 중일 때만 표시) */}
      {(isStreaming || hasThinking) && streaming?.thinking && (
        <Collapsible
          open={isThinkingOpen}
          onOpenChange={setIsThinkingOpen}
          className="mt-4"
        >
          <CollapsibleTrigger className="minimal-trigger text-sm">
            {isStreaming ? (
              <Loader2 className="h-4 w-4 text-violet-500 animate-spin" />
            ) : (
              <span className="h-4 w-4 rounded-full bg-violet-500/20 flex items-center justify-center">
                <span className="h-1.5 w-1.5 rounded-full bg-violet-500" />
              </span>
            )}
            <span
              className={`flex-1 truncate ${isStreaming ? "shimmer-text" : ""}`}
            >
              {isStreaming ? currentTitle || "AI가 분석 중..." : "Thoughts"}
            </span>
            {isThinkingOpen ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-2 p-3 rounded-lg bg-muted/30 border border-muted/50">
              <div className="text-sm text-muted-foreground leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none">
                <ReactMarkdown>
                  {isStreaming ? currentContent : fullThinkingContent}
                </ReactMarkdown>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* 로딩 상태 (크롤링 중) */}
      {isLoading && !isStreaming ? (
        <div className="space-y-3 mt-4">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-4/5" />
        </div>
      ) : data ? (
        /* 완료된 데이터 표시 */
        <div className="mt-4 space-y-4">
          {/* 주요 주제 */}
          <p className="text-sm font-medium text-primary">{data.main_topic}</p>

          {/* 요약 포인트 - 미니멀 bullet 스타일 */}
          <ul className="bullet-list">
            {data.bullet_points.map((point, index) => (
              <li
                key={index}
                className="bullet-item animate-in fade-in slide-in-from-bottom-2"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <span className="bullet-marker" />
                <span className="typography-reading">{point}</span>
              </li>
            ))}
          </ul>

          {/* 메타 정보 */}
          <div className="text-xs text-muted-foreground flex items-center gap-3">
            <span>{data.model}</span>
            <span className="text-muted-foreground/50">·</span>
            <span>{(data.processing_time_ms / 1000).toFixed(1)}초</span>
          </div>
        </div>
      ) : isStreaming || hasStreamingContent ? (
        /* 스트리밍 중일 때 */
        <div className="mt-4 space-y-4">
          {/* 주요 주제 (실시간 표시) */}
          {streamingMainTopic && (
            <p className="text-sm font-medium text-primary">
              {streamingMainTopic}
            </p>
          )}

          {/* 요약 포인트 (실시간 표시) */}
          {streamingBulletPoints.length > 0 ? (
            <ul className="bullet-list">
              {streamingBulletPoints.map((point, index) => (
                <li
                  key={index}
                  className="bullet-item animate-in fade-in slide-in-from-bottom-2"
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <span className="bullet-marker" />
                  <span className="typography-reading">{point}</span>
                </li>
              ))}
            </ul>
          ) : isStreaming && !streamingMainTopic ? (
            /* 스트리밍 시작했지만 아직 파싱할 내용이 없을 때 */
            <div className="space-y-3">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-full" />
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
