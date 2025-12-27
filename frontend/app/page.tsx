"use client";

import { useState, useCallback, useRef } from "react";
import { Header } from "@/components/header";
import { ContentPanel } from "@/components/content-panel";
import { WelcomeInput } from "@/components/welcome-input";
import {
  crawlUrl,
  summarizeStreamWithCallbacks,
  generateScriptStreamWithCallbacks,
  synthesizeAudio,
  getAudioUrl,
  extractArticleId,
  type CrawlResponse,
  type SummarizeResponse,
  type GenerateScriptResponse,
  type SynthesizeResponse,
} from "@/lib/api";

/** 처리 상태 타입 */
export type ProcessingStatus = "idle" | "crawling" | "processing" | "done" | "error";

/** 오디오 처리 상태 */
export type AudioStatus = "idle" | "scripting" | "synthesizing" | "done" | "ready" | "error";

/** 에러 정보 타입 */
export interface ErrorInfo {
  stage: "crawl" | "summarize" | "script";
  message: string;
}

/** 스트리밍 상태 (요약) */
export interface StreamingState {
  isStreaming: boolean;
  thinking: string;                    // 전체 thinking (완료 후용)
  content: string;
  currentThinkingTitle: string;        // 현재 블록 title
  currentThinkingContent: string;      // 현재 블록 content
}

/** 스크립트 스트리밍 상태 */
export interface ScriptStreamingState {
  isStreaming: boolean;
  thinking: string;                    // 전체 thinking
  content: string;                     // 전체 content (파싱용)
  currentThinkingTitle: string;        // 현재 thinking 블록 title
  currentThinkingContent: string;      // 현재 thinking 블록 content
}

/**
 * 최신 think 블록을 파싱하여 title과 content를 분리합니다.
 * Think 블록 형식: **Title**\n\n세부 내용...
 */
function parseLatestThinkBlock(thinkingText: string): { title: string; content: string } {
  if (!thinkingText) return { title: "", content: "" };
  
  // \n\n**로 블록 분리 후 마지막 블록 파싱
  const blocks = thinkingText.split(/\n\n(?=\*\*)/);
  const lastBlock = blocks[blocks.length - 1] || "";
  
  const titleMatch = lastBlock.match(/^\*\*(.+?)\*\*/);
  const title = titleMatch ? titleMatch[1] : "";
  const content = lastBlock.replace(/^\*\*.+?\*\*\n*/, "").trim();
  
  return { title, content };
}

export default function HomePage() {
  // 처리 상태
  const [status, setStatus] = useState<ProcessingStatus>("idle");
  const [error, setError] = useState<ErrorInfo | null>(null);

  // 데이터 상태
  const [crawlData, setCrawlData] = useState<CrawlResponse | null>(null);
  const [summaryData, setSummaryData] = useState<SummarizeResponse | null>(null);
  const [scriptData, setScriptData] = useState<GenerateScriptResponse | null>(null);

  // 오디오 처리 상태 (요약과 별도로 관리)
  const [audioStatus, setAudioStatus] = useState<AudioStatus>("idle");
  const [audioError, setAudioError] = useState<string | null>(null);

  // TTS 합성 상태
  const [synthesizeData, setSynthesizeData] = useState<SynthesizeResponse | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  // 스트리밍 상태 (요약)
  const [streaming, setStreaming] = useState<StreamingState>({
    isStreaming: false,
    thinking: "",
    content: "",
    currentThinkingTitle: "",
    currentThinkingContent: "",
  });

  // 스크립트 스트리밍 상태
  const [scriptStreaming, setScriptStreaming] = useState<ScriptStreamingState>({
    isStreaming: false,
    thinking: "",
    content: "",
    currentThinkingTitle: "",
    currentThinkingContent: "",
  });

  // AbortController refs (요청 취소용)
  const abortControllerRef = useRef<AbortController | null>(null);
  const scriptAbortControllerRef = useRef<AbortController | null>(null);

  /**
   * URL 제출 핸들러
   * 크롤링 → (스트리밍 요약 | 스크립트 생성) 병렬 처리
   */
  const handleSubmit = useCallback(async (url: string) => {
    // 이전 요청 취소
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (scriptAbortControllerRef.current) {
      scriptAbortControllerRef.current.abort();
    }

    // 상태 초기화
    setStatus("crawling");
    setError(null);
    setCrawlData(null);
    setSummaryData(null);
    setScriptData(null);
    setAudioStatus("idle");
    setAudioError(null);
    setSynthesizeData(null);
    setAudioUrl(null);
    setStreaming({
      isStreaming: false,
      thinking: "",
      content: "",
      currentThinkingTitle: "",
      currentThinkingContent: "",
    });
    setScriptStreaming({
      isStreaming: false,
      thinking: "",
      content: "",
      currentThinkingTitle: "",
      currentThinkingContent: "",
    });

    try {
      // Step 1: 크롤링
      console.log("[Pipeline] 크롤링 시작:", url);
      const crawled = await crawlUrl(url);
      setCrawlData(crawled);
      console.log("[Pipeline] 크롤링 완료:", crawled.title);

      // Step 2: 병렬 처리 - 요약 스트리밍 + 스크립트 생성
      setStatus("processing");
      setStreaming((prev) => ({ ...prev, isStreaming: true }));
      setAudioStatus("scripting");
      console.log("[Pipeline] 병렬 처리 시작: 요약 + 스크립트 생성");

      const articleId = extractArticleId(url, crawled.platform);

      // 요약 완료 여부 추적
      let summaryDone = false;
      let scriptDone = false;

      const checkAllDone = () => {
        if (summaryDone && scriptDone) {
          setStatus("done");
          console.log("[Pipeline] 모든 처리 완료");
        }
      };

      // Track 1: 스트리밍 요약
      abortControllerRef.current = summarizeStreamWithCallbacks(
        {
          content: crawled.cleaned_content,
          original_content: crawled.original_content || undefined,
          url: crawled.url,
          article_id: articleId,
        },
        {
          onThinking: (text) => {
            setStreaming((prev) => {
              const newThinking = prev.thinking + text;
              const { title, content } = parseLatestThinkBlock(newThinking);
              return {
                ...prev,
                thinking: newThinking,
                currentThinkingTitle: title,
                currentThinkingContent: content,
              };
            });
          },
          onContent: (text) => {
            setStreaming((prev) => ({
              ...prev,
              content: prev.content + text,
            }));
          },
          onDone: (result) => {
            setSummaryData(result);
            setStreaming((prev) => ({ ...prev, isStreaming: false }));
            summaryDone = true;
            console.log("[Pipeline] 스트리밍 요약 완료:", result.main_topic);
            checkAllDone();
          },
          onError: (errorMsg) => {
            console.error("[Pipeline] 스트리밍 요약 에러:", errorMsg);
            setError({ stage: "summarize", message: errorMsg });
            setStreaming((prev) => ({ ...prev, isStreaming: false }));
            summaryDone = true;
            checkAllDone();
          },
        }
      );

      // Track 2: 스크립트 스트리밍 생성 (병렬)
      setScriptStreaming((prev) => ({ ...prev, isStreaming: true }));
      scriptAbortControllerRef.current = generateScriptStreamWithCallbacks(
        {
          content: crawled.cleaned_content,
          original_content: crawled.original_content || undefined,
          url: crawled.url,
          article_id: articleId,
        },
        {
          onThinking: (text) => {
            setScriptStreaming((prev) => {
              const newThinking = prev.thinking + text;
              const { title, content } = parseLatestThinkBlock(newThinking);
              return {
                ...prev,
                thinking: newThinking,
                currentThinkingTitle: title,
                currentThinkingContent: content,
              };
            });
          },
          onContent: (text) => {
            setScriptStreaming((prev) => ({
              ...prev,
              content: prev.content + text,
            }));
          },
          onDone: async (result) => {
            setScriptData(result);
            setScriptStreaming((prev) => ({ ...prev, isStreaming: false }));
            setAudioStatus("done");
            scriptDone = true;
            console.log("[Pipeline] 스크립트 스트리밍 완료:", result.script.title);
            checkAllDone();

            // TTS 합성 시작
            console.log("[Pipeline] TTS 합성 시작:", result.article_id);
            setAudioStatus("synthesizing");

            try {
              const ttsResult = await synthesizeAudio({
                article_id: result.article_id,
                user_id: result.user_id,
              });
              setSynthesizeData(ttsResult);
              setAudioUrl(getAudioUrl(result.article_id, result.user_id));
              setAudioStatus("ready");
              console.log("[Pipeline] TTS 합성 완료:", ttsResult.duration_seconds, "초");
            } catch (ttsErr) {
              console.error("[Pipeline] TTS 합성 에러:", ttsErr);
              setAudioError(
                ttsErr instanceof Error ? ttsErr.message : "TTS 합성에 실패했습니다."
              );
              setAudioStatus("error");
            }
          },
          onError: (errorMsg) => {
            console.error("[Pipeline] 스크립트 스트리밍 에러:", errorMsg);
            setAudioError(errorMsg);
            setScriptStreaming((prev) => ({ ...prev, isStreaming: false }));
            setAudioStatus("error");
            scriptDone = true;
            checkAllDone();
          },
        }
      );

    } catch (err) {
      console.error("[Pipeline] 에러:", err);
      const message = err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다.";
      setError({ stage: "crawl", message });
      setStatus("error");
    }
  }, []);

  // idle 상태인지 확인 (중앙 입력창 vs 헤더 입력창)
  const isIdle = status === "idle";

  return (
    <div className="min-h-screen flex flex-col">
      <Header 
        onSubmit={handleSubmit}
        isLoading={status === "crawling" || status === "processing"}
        showInput={!isIdle}
      />
      <main className="flex-1 flex flex-col">
        {isIdle ? (
          /* 초기 상태: 중앙에 입력창 표시 */
          <WelcomeInput 
            onSubmit={handleSubmit}
            isLoading={false}
          />
        ) : (
          /* 처리 중/완료 상태: 콘텐츠 표시 */
          <ContentPanel
            status={status}
            error={error}
            crawlData={crawlData}
            summaryData={summaryData}
            streaming={streaming}
            audioStatus={audioStatus}
            audioError={audioError}
            scriptData={scriptData}
            scriptStreaming={scriptStreaming}
            synthesizeData={synthesizeData}
            audioUrl={audioUrl}
          />
        )}
      </main>
    </div>
  );
}
