"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Play,
  Pause,
  FileText,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Download,
  Headphones,
  Loader2,
  Volume2,
} from "lucide-react";
import type { AudioStatus, ScriptStreamingState } from "@/app/page";
import type { GenerateScriptResponse, SynthesizeResponse } from "@/lib/api";

interface AudioPlayerCardProps {
  audioStatus: AudioStatus;
  audioError: string | null;
  scriptData: GenerateScriptResponse | null;
  scriptStreaming?: ScriptStreamingState;
  /** TTS 합성 결과 */
  synthesizeData?: SynthesizeResponse | null;
  /** 오디오 파일 전체 URL */
  audioUrl?: string | null;
}

/**
 * Thinking 텍스트에서 escaped newlines를 실제 줄바꿈으로 변환하고 정리합니다.
 */
function cleanThinkingText(text: string): string {
  if (!text) return "";

  let cleaned = text.replace(/\\n\\n/g, "\n\n");
  cleaned = cleaned.replace(/\\n/g, "\n");
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n");

  return cleaned.trim();
}

/**
 * 스트리밍 content에서 제목 파싱
 */
function parseStreamingTitle(content: string): string | null {
  if (!content) return null;
  const titleMatch = content.match(/\[제목\]\s*\n(.+?)(?:\n\n|\n\[|$)/s);
  return titleMatch ? titleMatch[1].trim() : null;
}

/**
 * 스트리밍 content에서 문단 파싱
 */
function parseStreamingParagraphs(content: string): string[] {
  if (!content) return [];

  const scriptMatch = content.match(/\[스크립트\]\s*\n([\s\S]*?)$/);
  if (!scriptMatch) return [];

  const scriptText = scriptMatch[1];
  return scriptText
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
}

export function AudioPlayerCard({
  audioStatus,
  audioError,
  scriptData,
  scriptStreaming,
  synthesizeData,
  audioUrl,
}: AudioPlayerCardProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isThinkingOpen, setIsThinkingOpen] = useState(false);
  const [isScriptOpen, setIsScriptOpen] = useState(false);

  // Audio element ref
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const isScripting = audioStatus === "scripting";
  const isSynthesizing = audioStatus === "synthesizing";
  const isAudioReady = audioStatus === "ready" && audioUrl !== null;
  const isScriptDone = audioStatus === "done" && scriptData !== null;
  const hasError = audioStatus === "error";

  // 오디오 이벤트 핸들러
  const handleTimeUpdate = useCallback(() => {
    if (audioRef.current) {
      const current = audioRef.current.currentTime;
      const total = audioRef.current.duration || 1;
      setCurrentTime(current);
      setProgress((current / total) * 100);
    }
  }, []);

  const handleLoadedMetadata = useCallback(() => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  }, []);

  const handleEnded = useCallback(() => {
    setIsPlaying(false);
    setProgress(0);
    setCurrentTime(0);
  }, []);

  // 오디오 URL 변경 시 audio 요소 업데이트
  useEffect(() => {
    if (audioUrl && audioRef.current) {
      audioRef.current.src = audioUrl;
      audioRef.current.load();
    }
  }, [audioUrl]);

  // 재생/일시정지 토글
  const togglePlay = useCallback(() => {
    if (!audioRef.current) return;

    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  }, [isPlaying]);

  // 프로그레스 바 클릭으로 탐색
  const handleSeek = useCallback((value: number[]) => {
    if (!audioRef.current) return;

    const newProgress = value[0];
    const newTime = (newProgress / 100) * audioRef.current.duration;
    audioRef.current.currentTime = newTime;
    setProgress(newProgress);
    setCurrentTime(newTime);
  }, []);

  // 다운로드 핸들러
  const handleDownload = useCallback(() => {
    if (!audioUrl) return;

    const link = document.createElement("a");
    link.href = audioUrl;
    link.download = `${scriptData?.article_id || "audio"}.mp3`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [audioUrl, scriptData?.article_id]);

  // 스트리밍 상태
  const isStreaming = scriptStreaming?.isStreaming ?? false;
  const hasThinking = Boolean(scriptStreaming?.thinking);
  const hasStreamingContent = Boolean(scriptStreaming?.content);

  // 현재 thinking 블록 정보 (cleaned)
  const currentThinkingTitle = cleanThinkingText(
    scriptStreaming?.currentThinkingTitle || ""
  );
  const currentThinkingContent = cleanThinkingText(
    scriptStreaming?.currentThinkingContent || ""
  );
  const fullThinkingContent = cleanThinkingText(
    scriptStreaming?.thinking || ""
  );

  // 스트리밍 content 파싱
  const streamingTitle = parseStreamingTitle(scriptStreaming?.content || "");
  const streamingParagraphs = parseStreamingParagraphs(
    scriptStreaming?.content || ""
  );

  // idle 상태에서는 표시하지 않음
  if (audioStatus === "idle" && !isStreaming && !hasStreamingContent) {
    return null;
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="minimal-section">
      {/* 섹션 타이틀 */}
      <h3 className="section-header">
        <Headphones className="h-5 w-5 text-primary" />
        Audio reporting
      </h3>

      {/* Thinking 섹션 */}
      {(isStreaming || hasThinking) && scriptStreaming?.thinking && (
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
              {isStreaming
                ? currentThinkingTitle || "AI가 분석 중..."
                : "Thoughts"}
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
                  {isStreaming ? currentThinkingContent : fullThinkingContent}
                </ReactMarkdown>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* 스크립트 생성 중 (스트리밍 없이) */}
      {isScripting && !hasStreamingContent && !hasThinking && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <FileText className="h-4 w-4 animate-pulse" />
            <span>리포팅 대본 작성 중...</span>
          </div>
          <Skeleton className="h-2 w-full" />
          <Skeleton className="h-2 w-3/4" />
        </div>
      )}

      {/* 스트리밍 중 스크립트 UI */}
      {(isStreaming || (isScripting && hasStreamingContent)) && (
        <Collapsible
          open={isScriptOpen}
          onOpenChange={setIsScriptOpen}
          className="mt-4"
        >
          <CollapsibleTrigger className="minimal-trigger text-sm">
            {isStreaming ? (
              <Loader2 className="h-4 w-4 text-primary animate-spin" />
            ) : (
              <FileText className="h-4 w-4 text-primary" />
            )}
            <span
              className={`flex-1 truncate ${isStreaming ? "shimmer-text" : ""}`}
            >
              {streamingTitle ||
                streamingParagraphs[streamingParagraphs.length - 1] ||
                "스크립트 생성 중..."}
            </span>
            {isScriptOpen ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-3 space-y-3">
              {streamingParagraphs.length > 0 ? (
                streamingParagraphs.map((paragraph, index) => (
                  <div
                    key={index}
                    className="text-sm typography-reading animate-in fade-in slide-in-from-bottom-2"
                    style={{ animationDelay: `${index * 50}ms` }}
                  >
                    <ReactMarkdown>{paragraph}</ReactMarkdown>
                  </div>
                ))
              ) : isStreaming ? (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-full" />
                </div>
              ) : null}
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* 에러 상태 */}
      {hasError && (
        <div className="mt-4 flex items-start gap-3 p-4 rounded-lg bg-destructive/5 border border-destructive/20">
          <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium text-destructive">스크립트 생성 실패</h4>
            <p className="text-sm text-muted-foreground mt-1">
              {audioError || "스크립트 생성 중 오류가 발생했습니다."}
            </p>
          </div>
        </div>
      )}

      {/* TTS 합성 중 */}
      {isSynthesizing && scriptData && !isStreaming && (
        <div className="mt-4 space-y-4">
          {/* 스크립트 내용 (Collapsible) */}
          <Collapsible open={isScriptOpen} onOpenChange={setIsScriptOpen}>
            <CollapsibleTrigger className="minimal-trigger text-sm">
              <FileText className="h-4 w-4 text-primary" />
              <span className="flex-1 truncate font-medium text-foreground">
                {scriptData.script.title}
              </span>
              {isScriptOpen ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="mt-3 space-y-3 pl-6">
                {scriptData.script.paragraphs.map((paragraph, index) => (
                  <div
                    key={index}
                    className="text-sm typography-reading animate-in fade-in slide-in-from-bottom-2"
                    style={{ animationDelay: `${index * 30}ms` }}
                  >
                    <ReactMarkdown>{paragraph}</ReactMarkdown>
                  </div>
                ))}
                <div className="text-xs text-muted-foreground flex items-center gap-3 pt-2">
                  <span>{scriptData.script.total_characters}자</span>
                  <span className="text-muted-foreground/50">·</span>
                  <span>{scriptData.script.paragraphs.length}개 문단</span>
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* TTS 합성 중 상태 */}
          <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/30 border border-muted/50">
            <Loader2 className="h-5 w-5 text-primary animate-spin" />
            <div className="flex-1">
              <p className="text-sm font-medium">음성 합성 중...</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                OpenAI TTS로 오디오를 생성하고 있습니다
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 스크립트만 완료, TTS 대기 중 */}
      {isScriptDone && scriptData && !isStreaming && (
        <div className="mt-4 space-y-4">
          {/* 스크립트 내용 (Collapsible) */}
          <Collapsible open={isScriptOpen} onOpenChange={setIsScriptOpen}>
            <CollapsibleTrigger className="minimal-trigger text-sm">
              <FileText className="h-4 w-4 text-primary" />
              <span className="flex-1 truncate font-medium text-foreground">
                {scriptData.script.title}
              </span>
              {isScriptOpen ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="mt-3 space-y-3 pl-6">
                {scriptData.script.paragraphs.map((paragraph, index) => (
                  <div
                    key={index}
                    className="text-sm typography-reading animate-in fade-in slide-in-from-bottom-2"
                    style={{ animationDelay: `${index * 30}ms` }}
                  >
                    <ReactMarkdown>{paragraph}</ReactMarkdown>
                  </div>
                ))}
                <div className="text-xs text-muted-foreground flex items-center gap-3 pt-2">
                  <span>{scriptData.script.total_characters}자</span>
                  <span className="text-muted-foreground/50">·</span>
                  <span>{scriptData.script.paragraphs.length}개 문단</span>
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* 미니멀 오디오 플레이어 (비활성화) */}
          <div className="audio-player-minimal">
            <Button
              size="icon"
              variant="outline"
              className="h-10 w-10 rounded-full shrink-0"
              disabled
              title="TTS 합성 대기 중"
            >
              <Play className="h-4 w-4 ml-0.5" />
            </Button>

            <div className="flex-1 space-y-1">
              <Slider
                value={[0]}
                max={100}
                step={1}
                disabled
                className="cursor-not-allowed"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{formatTime(0)}</span>
                <span>
                  {formatTime(scriptData.script.estimated_duration_sec)}
                </span>
              </div>
            </div>

            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 shrink-0"
              disabled
              title="TTS 합성 대기 중"
            >
              <Download className="h-4 w-4" />
            </Button>
          </div>

          <p className="text-xs text-center text-muted-foreground">
            ✅ 대본 생성 완료 · 🔊 TTS 음성 합성 대기 중...
          </p>
        </div>
      )}

      {/* 오디오 준비 완료 - 실제 플레이어 */}
      {isAudioReady && scriptData && audioUrl && !isStreaming && (
        <div className="mt-4 space-y-4">
          {/* Hidden audio element */}
          <audio
            ref={audioRef}
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onEnded={handleEnded}
            preload="metadata"
          />

          {/* 스크립트 내용 (Collapsible) */}
          <Collapsible open={isScriptOpen} onOpenChange={setIsScriptOpen}>
            <CollapsibleTrigger className="minimal-trigger text-sm">
              <FileText className="h-4 w-4 text-primary" />
              <span className="flex-1 truncate font-medium text-foreground">
                {scriptData.script.title}
              </span>
              {isScriptOpen ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="mt-3 space-y-3 pl-6">
                {scriptData.script.paragraphs.map((paragraph, index) => (
                  <div
                    key={index}
                    className="text-sm typography-reading animate-in fade-in slide-in-from-bottom-2"
                    style={{ animationDelay: `${index * 30}ms` }}
                  >
                    <ReactMarkdown>{paragraph}</ReactMarkdown>
                  </div>
                ))}
                <div className="text-xs text-muted-foreground flex items-center gap-3 pt-2">
                  <span>{scriptData.script.total_characters}자</span>
                  <span className="text-muted-foreground/50">·</span>
                  <span>{scriptData.script.paragraphs.length}개 문단</span>
                  {synthesizeData && (
                    <>
                      <span className="text-muted-foreground/50">·</span>
                      <span>
                        {(synthesizeData.file_size_bytes / 1024).toFixed(1)}KB
                      </span>
                    </>
                  )}
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {/* 실제 오디오 플레이어 */}
          <div className="audio-player-minimal">
            {/* 재생/일시정지 버튼 */}
            <Button
              size="icon"
              variant="outline"
              className="h-10 w-10 rounded-full shrink-0"
              onClick={togglePlay}
              title={isPlaying ? "일시정지" : "재생"}
            >
              {isPlaying ? (
                <Pause className="h-4 w-4" />
              ) : (
                <Play className="h-4 w-4 ml-0.5" />
              )}
            </Button>

            {/* 프로그레스 바 */}
            <div className="flex-1 space-y-1">
              <Slider
                value={[progress]}
                max={100}
                step={0.1}
                onValueChange={handleSeek}
                className="cursor-pointer"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{formatTime(currentTime)}</span>
                <span>
                  {formatTime(
                    duration || synthesizeData?.duration_seconds || 0
                  )}
                </span>
              </div>
            </div>

            {/* 다운로드 버튼 */}
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 shrink-0"
              onClick={handleDownload}
              title="다운로드"
            >
              <Download className="h-4 w-4" />
            </Button>
          </div>

          {/* 오디오 준비 완료 안내 */}
          <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <Volume2 className="h-3.5 w-3.5 text-green-500" />
            <span>오디오 준비 완료</span>
            {synthesizeData && (
              <>
                <span className="text-muted-foreground/50">·</span>
                <span>{synthesizeData.duration_seconds.toFixed(1)}초</span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
