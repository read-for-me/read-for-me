/**
 * API Client Utilities
 *
 * 백엔드 API 호출을 위한 유틸리티 함수들입니다.
 * Phase 4에서 TanStack Query로 마이그레이션 예정입니다.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// 기본 사용자 ID (프로토타입용, 추후 로그인 시스템 도입 시 교체)
export const DEFAULT_USER_ID = "default";

// ============================================================================
// Types
// ============================================================================

/** 크롤링 요청 */
export interface CrawlRequest {
  url: string;
  user_id?: string;
}

/** 아티클 메타데이터 (백엔드 ArticleMetadata와 일치) */
export interface ArticleMetadata {
  og_title?: string;
  og_description?: string;
  og_image?: string;
  og_url?: string;
  author?: string;
  published_at?: string;
  original_url?: string;
  points?: string;
  comment_count?: number;
  read_time?: string;
  claps?: string;
  tags?: string[];
  topic_id?: string;
  subtitle?: string;
}

/** 크롤링 응답 (백엔드 CleanedArticle과 일치) */
export interface CrawlResponse {
  title: string;
  cleaned_content: string;
  preview_text: string;
  url: string;
  platform: string;
  crawled_at: string;
  metadata: ArticleMetadata;
  original_content: string;
}

/** 요약 요청 */
export interface SummarizeRequest {
  content: string;
  original_content?: string;
  url?: string;
  article_id?: string;
  user_id?: string;
}

/** 요약 응답 */
export interface SummarizeResponse {
  bullet_points: string[];
  main_topic: string;
  model: string;
  processing_time_ms: number;
  article_id: string;
  saved_path: string | null;
}

/** 스트리밍 이벤트 타입 */
export type StreamEventType = "thinking" | "content" | "done" | "error";

/** 스트리밍 이벤트 (요약) */
export interface StreamEvent {
  type: StreamEventType;
  data: string | SummarizeResponse | { error: string };
}

/** 스크립트 스트리밍 이벤트 */
export interface ScriptStreamEvent {
  type: StreamEventType;
  data: string | GenerateScriptResponse | { error: string };
}

/** API 에러 응답 */
export interface ApiError {
  detail: string | ApiErrorDetail;
}

/** 상세 에러 응답 (크롤링 API용) */
export interface ApiErrorDetail {
  error_code: string;
  message: string;
  detail?: string;
}

/** URL 지원 여부 응답 */
export interface UrlSupportResponse {
  url: string;
  is_supported: boolean;
  platform: string | null;
  is_specialized: boolean;
  domain: string;
  error_code: string | null;
  error_message: string | null;
}

/** 뉴스 스크립트 (백엔드 NewsScript와 일치) */
export interface NewsScript {
  paragraphs: string[];
  title: string;
  estimated_duration_sec: number;
  total_characters: number;
}

/** 스크립트 생성 요청 */
export interface GenerateScriptRequest {
  content: string;
  original_content?: string;
  url?: string;
  article_id?: string;
  user_id?: string;
}

/** 스크립트 생성 응답 */
export interface GenerateScriptResponse {
  user_id: string;
  article_id: string;
  script: NewsScript;
  model: string;
  processing_time_ms: number;
  saved_path: string | null;
}

/** TTS 합성 요청 */
export interface SynthesizeRequest {
  article_id: string;
  user_id?: string;
}

/** TTS 합성 응답 */
export interface SynthesizeResponse {
  audio_url: string;
  duration_seconds: number;
  file_size_bytes: number;
  user_id: string;
  article_id: string;
  processing_time_ms: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * URL 지원 여부를 확인합니다.
 *
 * @param url - 확인할 URL
 * @returns 지원 여부 및 플랫폼 정보
 */
export async function checkUrlSupport(url: string): Promise<UrlSupportResponse> {
  const response = await fetch(
    `${API_BASE}/api/v1/crawl/check-support?url=${encodeURIComponent(url)}`
  );

  if (!response.ok) {
    // 서버 에러 시 기본 응답 반환
    return {
      url,
      is_supported: false,
      platform: null,
      is_specialized: false,
      domain: "",
      error_code: "NETWORK_ERROR",
      error_message: "서버에 연결할 수 없습니다.",
    };
  }

  return response.json();
}

/**
 * URL을 크롤링하여 정제된 아티클을 반환합니다.
 *
 * @param url - 크롤링할 URL
 * @param userId - 사용자 ID (선택, 기본값: "default")
 */
export async function crawlUrl(
  url: string,
  userId: string = DEFAULT_USER_ID
): Promise<CrawlResponse> {
  const response = await fetch(`${API_BASE}/api/v1/crawl`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, user_id: userId }),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    // 상세 에러 응답 처리
    if (typeof error.detail === "object" && error.detail !== null) {
      const errorDetail = error.detail as ApiErrorDetail;
      throw new Error(errorDetail.message || "크롤링에 실패했습니다.");
    }
    throw new Error(
      (typeof error.detail === "string" ? error.detail : null) ||
        "크롤링에 실패했습니다."
    );
  }

  return response.json();
}

/**
 * 콘텐츠를 요약합니다.
 *
 * @param request - 요약 요청 (content, url, article_id, user_id)
 */
export async function summarizeContent(
  request: SummarizeRequest
): Promise<SummarizeResponse> {
  // user_id 기본값 설정
  const requestWithUserId = {
    ...request,
    user_id: request.user_id || DEFAULT_USER_ID,
  };

  const response = await fetch(`${API_BASE}/api/v1/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestWithUserId),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || "요약에 실패했습니다.");
  }

  return response.json();
}

/**
 * 콘텐츠를 뉴스 스크립트로 변환합니다.
 *
 * @param request - 스크립트 생성 요청 (content, url, article_id, user_id)
 */
export async function generateScript(
  request: GenerateScriptRequest
): Promise<GenerateScriptResponse> {
  // user_id 기본값 설정
  const requestWithUserId = {
    ...request,
    user_id: request.user_id || DEFAULT_USER_ID,
  };

  const response = await fetch(`${API_BASE}/api/v1/audio/script`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestWithUserId),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || "스크립트 생성에 실패했습니다.");
  }

  return response.json();
}

/**
 * 스크립트를 TTS로 음성 합성합니다.
 *
 * @param request - TTS 합성 요청 (article_id, user_id)
 */
export async function synthesizeAudio(
  request: SynthesizeRequest
): Promise<SynthesizeResponse> {
  const requestWithUserId = {
    ...request,
    user_id: request.user_id || DEFAULT_USER_ID,
  };

  const response = await fetch(`${API_BASE}/api/v1/audio/synthesize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestWithUserId),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || "TTS 합성에 실패했습니다.");
  }

  return response.json();
}

/**
 * 오디오 파일의 전체 URL을 반환합니다.
 *
 * @param articleId - 아티클 ID
 * @param userId - 사용자 ID (선택, 기본값: "default")
 */
export function getAudioUrl(
  articleId: string,
  userId: string = DEFAULT_USER_ID
): string {
  return `${API_BASE}/api/v1/audio/${articleId}.mp3?user_id=${userId}`;
}

/**
 * URL에서 article_id를 추출합니다.
 * 백엔드의 _extract_article_id 로직과 유사하게 구현합니다.
 */
export function extractArticleId(url: string, platform: string): string {
  try {
    const parsed = new URL(url);

    if (platform === "geeknews") {
      const topicId = parsed.searchParams.get("id");
      if (topicId) {
        return `topic_${topicId}`;
      }
    } else if (platform === "medium") {
      const pathParts = parsed.pathname.split("/").filter(Boolean);
      if (pathParts.length > 0) {
        const slug = pathParts[pathParts.length - 1];
        // 마지막 해시 부분 제거
        const slugClean = slug.replace(/-[a-f0-9]{10,}$/, "");
        if (slugClean) {
          return slugClean.slice(0, 50);
        }
      }
    }
  } catch {
    // URL 파싱 실패 시 무시
  }

  // 기본값: URL 해시
  return `article_${Math.abs(hashCode(url)) % 100000000}`;
}

/** 간단한 해시 함수 */
function hashCode(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash;
  }
  return hash;
}

// ============================================================================
// Streaming API (SSE)
// ============================================================================

/**
 * SSE 스트리밍으로 콘텐츠를 요약합니다.
 *
 * @param request - 요약 요청
 * @yields StreamEvent - 스트리밍 이벤트
 *
 * 이벤트 타입:
 * - thinking: AI 추론 과정 텍스트
 * - content: 요약 텍스트 청크
 * - done: 최종 결과 (SummarizeResponse)
 * - error: 에러 발생
 */
export async function* summarizeStream(
  request: SummarizeRequest
): AsyncGenerator<StreamEvent> {
  const requestWithUserId = {
    ...request,
    user_id: request.user_id || DEFAULT_USER_ID,
  };

  const response = await fetch(`${API_BASE}/api/v1/summarize/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestWithUserId),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    yield {
      type: "error",
      data: { error: error.detail || "요약에 실패했습니다." },
    };
    return;
  }

  if (!response.body) {
    yield {
      type: "error",
      data: { error: "스트리밍 응답을 받을 수 없습니다." },
    };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // SSE 이벤트 파싱 (이벤트는 '\n\n'으로 구분)
      const events = buffer.split("\n\n");
      // 마지막 요소는 불완전할 수 있으므로 버퍼에 유지
      buffer = events.pop() || "";

      for (const eventText of events) {
        if (!eventText.trim()) continue;

        const lines = eventText.split("\n");
        let eventType: StreamEventType = "content";
        let eventData = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7) as StreamEventType;
          } else if (line.startsWith("data: ")) {
            eventData = line.slice(6);
          }
        }

        if (!eventData) continue;

        try {
          const parsed = JSON.parse(eventData);

          if (eventType === "thinking" || eventType === "content") {
            yield {
              type: eventType,
              data: parsed.text || "",
            };
          } else if (eventType === "done") {
            yield {
              type: "done",
              data: parsed as SummarizeResponse,
            };
          } else if (eventType === "error") {
            yield {
              type: "error",
              data: { error: parsed.error || "알 수 없는 오류" },
            };
          }
        } catch {
          console.warn("[SSE] JSON 파싱 실패:", eventData);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * 스트리밍 요약 콜백 인터페이스
 * 각 이벤트 타입에 대한 콜백을 정의합니다.
 */
export interface SummarizeStreamCallbacks {
  onThinking?: (text: string) => void;
  onContent?: (text: string) => void;
  onDone?: (result: SummarizeResponse) => void;
  onError?: (error: string) => void;
}

/**
 * 콜백 기반 스트리밍 요약 함수
 *
 * @param request - 요약 요청
 * @param callbacks - 이벤트 콜백
 * @returns AbortController (취소용)
 */
export function summarizeStreamWithCallbacks(
  request: SummarizeRequest,
  callbacks: SummarizeStreamCallbacks
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const stream = summarizeStream(request);

      for await (const event of stream) {
        if (controller.signal.aborted) break;

        switch (event.type) {
          case "thinking":
            callbacks.onThinking?.(event.data as string);
            break;
          case "content":
            callbacks.onContent?.(event.data as string);
            break;
          case "done":
            callbacks.onDone?.(event.data as SummarizeResponse);
            break;
          case "error":
            callbacks.onError?.((event.data as { error: string }).error);
            break;
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "스트리밍 오류";
      callbacks.onError?.(message);
    }
  })();

  return controller;
}

// ============================================================================
// Script Streaming API (SSE)
// ============================================================================

/**
 * SSE 스트리밍으로 뉴스 스크립트를 생성합니다.
 *
 * @param request - 스크립트 생성 요청
 * @yields ScriptStreamEvent - 스트리밍 이벤트
 *
 * 이벤트 타입:
 * - thinking: AI 추론 과정 텍스트
 * - content: 스크립트 텍스트 청크
 * - done: 최종 결과 (GenerateScriptResponse)
 * - error: 에러 발생
 */
export async function* generateScriptStream(
  request: GenerateScriptRequest
): AsyncGenerator<ScriptStreamEvent> {
  const requestWithUserId = {
    ...request,
    user_id: request.user_id || DEFAULT_USER_ID,
  };

  const response = await fetch(`${API_BASE}/api/v1/audio/script/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestWithUserId),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    yield {
      type: "error",
      data: { error: error.detail || "스크립트 생성에 실패했습니다." },
    };
    return;
  }

  if (!response.body) {
    yield {
      type: "error",
      data: { error: "스트리밍 응답을 받을 수 없습니다." },
    };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // SSE 이벤트 파싱 (이벤트는 '\n\n'으로 구분)
      const events = buffer.split("\n\n");
      // 마지막 요소는 불완전할 수 있으므로 버퍼에 유지
      buffer = events.pop() || "";

      for (const eventText of events) {
        if (!eventText.trim()) continue;

        const lines = eventText.split("\n");
        let eventType: StreamEventType = "content";
        let eventData = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7) as StreamEventType;
          } else if (line.startsWith("data: ")) {
            eventData = line.slice(6);
          }
        }

        if (!eventData) continue;

        try {
          const parsed = JSON.parse(eventData);

          if (eventType === "thinking" || eventType === "content") {
            yield {
              type: eventType,
              data: parsed.text || "",
            };
          } else if (eventType === "done") {
            yield {
              type: "done",
              data: parsed as GenerateScriptResponse,
            };
          } else if (eventType === "error") {
            yield {
              type: "error",
              data: { error: parsed.error || "알 수 없는 오류" },
            };
          }
        } catch {
          console.warn("[SSE Script] JSON 파싱 실패:", eventData);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * 스트리밍 스크립트 생성 콜백 인터페이스
 * 각 이벤트 타입에 대한 콜백을 정의합니다.
 */
export interface ScriptStreamCallbacks {
  onThinking?: (text: string) => void;
  onContent?: (text: string) => void;
  onDone?: (result: GenerateScriptResponse) => void;
  onError?: (error: string) => void;
}

/**
 * 콜백 기반 스트리밍 스크립트 생성 함수
 *
 * @param request - 스크립트 생성 요청
 * @param callbacks - 이벤트 콜백
 * @returns AbortController (취소용)
 */
export function generateScriptStreamWithCallbacks(
  request: GenerateScriptRequest,
  callbacks: ScriptStreamCallbacks
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const stream = generateScriptStream(request);

      for await (const event of stream) {
        if (controller.signal.aborted) break;

        switch (event.type) {
          case "thinking":
            callbacks.onThinking?.(event.data as string);
            break;
          case "content":
            callbacks.onContent?.(event.data as string);
            break;
          case "done":
            callbacks.onDone?.(event.data as GenerateScriptResponse);
            break;
          case "error":
            callbacks.onError?.((event.data as { error: string }).error);
            break;
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "스크립트 스트리밍 오류";
      callbacks.onError?.(message);
    }
  })();

  return controller;
}
