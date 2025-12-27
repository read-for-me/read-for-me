"use client";

import { SourcePanel } from "@/components/source-panel";
import { InsightCard } from "@/components/insight-card";
import { AudioPlayerCard } from "@/components/audio-player-card";
import type { ProcessingStatus, ErrorInfo, StreamingState, AudioStatus, ScriptStreamingState } from "@/app/page";
import type { CrawlResponse, SummarizeResponse, GenerateScriptResponse, SynthesizeResponse } from "@/lib/api";

interface ContentPanelProps {
  status: ProcessingStatus;
  error: ErrorInfo | null;
  crawlData: CrawlResponse | null;
  summaryData: SummarizeResponse | null;
  streaming?: StreamingState;
  audioStatus: AudioStatus;
  audioError: string | null;
  scriptData: GenerateScriptResponse | null;
  scriptStreaming?: ScriptStreamingState;
  /** TTS 합성 결과 */
  synthesizeData?: SynthesizeResponse | null;
  /** 오디오 파일 전체 URL */
  audioUrl?: string | null;
}

export function ContentPanel({
  status,
  error,
  crawlData,
  summaryData,
  streaming,
  audioStatus,
  audioError,
  scriptData,
  scriptStreaming,
  synthesizeData,
  audioUrl,
}: ContentPanelProps) {
  // idle 상태에서는 아무것도 표시하지 않음
  if (status === "idle") {
    return null;
  }

  return (
    <section className="w-full py-8 px-4 md:px-6">
      <div className="content-narrow">
        {/* 원문 정보 섹션 */}
        <SourcePanel
          isLoading={status === "crawling"}
          data={crawlData}
          error={error?.stage === "crawl" ? error.message : undefined}
        />

        {/* 구분선 (데이터가 있을 때만) */}
        {crawlData && <div className="section-divider" />}

        {/* AI 3줄 요약 섹션 */}
        <InsightCard
          isLoading={status === "crawling"}
          isProcessing={status === "processing" && streaming?.isStreaming}
          data={summaryData}
          error={error?.stage === "summarize" ? error.message : undefined}
          streaming={streaming}
        />

        {/* 구분선 (요약 데이터가 있거나 스트리밍 중일 때) */}
        {(summaryData || streaming?.isStreaming || streaming?.content) && (
          <div className="section-divider" />
        )}

        {/* 오디오 리포팅 섹션 */}
        <AudioPlayerCard
          audioStatus={audioStatus}
          audioError={audioError}
          scriptData={scriptData}
          scriptStreaming={scriptStreaming}
          synthesizeData={synthesizeData}
          audioUrl={audioUrl}
        />
      </div>
    </section>
  );
}
