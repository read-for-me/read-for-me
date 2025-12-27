"use client";

import { useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ExternalLink, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";
import type { CrawlResponse } from "@/lib/api";

interface SourcePanelProps {
  isLoading?: boolean;
  data: CrawlResponse | null;
  error?: string;
}

/** 플랫폼별 이름 */
const platformConfig: Record<string, { name: string }> = {
  geeknews: { name: "GeekNews" },
  medium: { name: "Medium" },
};

export function SourcePanel({ isLoading = false, data, error }: SourcePanelProps) {
  const [isContentOpen, setIsContentOpen] = useState(false);

  // 로딩 중이 아니고 데이터도 없으면 표시하지 않음
  if (!isLoading && !data && !error) {
    return null;
  }

  // 에러 상태
  if (error) {
    return (
      <div className="minimal-section">
        <div className="flex items-start gap-3 p-4 rounded-lg bg-destructive/5 border border-destructive/20">
          <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium text-destructive">크롤링 실패</h4>
            <p className="text-sm text-muted-foreground mt-1">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  const platform = data ? platformConfig[data.platform] || { name: data.platform } : null;

  return (
    <div className="minimal-section">
      {isLoading ? (
        /* 로딩 상태 */
        <div className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      ) : data ? (
        <>
          {/* 메타 정보 라인 */}
          <div className="meta-line">
            <span className="font-medium">{platform?.name}</span>
            {data.metadata?.published_at && (
              <>
                <span className="text-muted-foreground/50">·</span>
                <span>{new Date(data.metadata.published_at).toLocaleDateString("ko-KR")}</span>
              </>
            )}
            <span className="text-muted-foreground/50">·</span>
            <span>약 {data.cleaned_content?.length?.toLocaleString() || 0}자</span>
          </div>

          {/* 제목 */}
          <h2 className="minimal-title mt-2">{data.title}</h2>

          {/* 접기/펼치기 - 원문 내용 */}
          <Collapsible
            open={isContentOpen}
            onOpenChange={setIsContentOpen}
            className="mt-4"
          >
            <CollapsibleTrigger className="minimal-trigger text-sm">
              {isContentOpen ? (
                <>
                  <ChevronUp className="h-4 w-4" />
                  원문 접기
                </>
              ) : (
                <>
                  <ChevronDown className="h-4 w-4" />
                  원문 미리보기
                </>
              )}
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="mt-3 space-y-4">
                {/* 원문 설명 */}
                <p className="typography-reading text-muted-foreground">
                  {(data.metadata?.og_description || data.preview_text || data.cleaned_content?.slice(0, 400))}...
                </p>

                {/* 원문 보기 링크 */}
                <a
                  href={data.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                >
                  원문 전체 보기
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            </CollapsibleContent>
          </Collapsible>
        </>
      ) : null}
    </div>
  );
}
