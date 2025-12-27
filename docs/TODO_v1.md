# TODO 로드맵

> 이 문서는 앞으로 해야 할 작업들을 정리합니다.
> 완료된 작업은 `docs/DONE.md`를 참고하세요.

---

## 📋 목차

1. [현재 상태 요약](#현재-상태-요약)
2. [다음 액션 아이템](#다음-액션-아이템)
3. [Phase 3: AI 서비스 구현](#phase-3-ai-서비스-구현-병렬-처리)
4. [Phase 4: 프론트엔드 연동](#phase-4-프론트엔드-연동-tanstack-query)
5. [Phase 5: 마무리 및 배포](#phase-5-마무리-및-개선)
6. [Phase 6: LLM Ops](#phase-6-llm-ops-모니터링-및-평가)

---

## 현재 상태 요약

> 마지막 업데이트: 2025-12-25

### ✅ 완료된 Phase

| Phase   | 내용                                     | 완료일     |
| ------- | ---------------------------------------- | ---------- |
| Phase 1 | 프론트엔드 UI 껍데기 + 백엔드 셋업       | 2025-12-16 |
| Phase 2 | 크롤링 & ETL 아키텍처 (GeekNews, Medium) | 2025-12-21 |

### ✅ Phase 2 추가 완료 항목

- [x] **GeekNews 원본 외부 링크 크롤링** (2025-12-23)
  - [x] `trafilatura` 라이브러리 의존성 추가
  - [x] `GEEKNEWS_CRAWL_ORIGINAL` 환경변수 설정 (`config.py`, `.env`)
  - [x] `CrawledArticle`, `CleanedArticle`에 `original_content` 필드 추가
  - [x] `GeekNewsCrawler`에 `crawl_original` 파라미터 및 크롤링 로직 구현

### ✅ Phase 3-1 완료 항목

- [x] **요약 서비스 구현** (2025-12-23 완료)
  - [x] `langchain-google-genai` 의존성 추가
  - [x] `output_schemas/summary.py` SummaryResult 스키마 생성
  - [x] `prompts/v1/summary.md` 프롬프트 템플릿 생성
  - [x] `app/services/prompt_loader.py` 프롬프트 로더 구현
  - [x] `app/services/summary.py` SummaryService 구현 (LangChain + Vertex AI)
  - [x] `POST /api/v1/summarize` API 엔드포인트 추가
  - [x] **요약 결과 JSON 로컬 저장** (`backend/data/users/{user_id}/summary/`)
  - [x] **Frontend 연동** (InsightCard에 실제 데이터 표시)
    - `SummarizeRequest`에 `article_id` optional 필드 추가
    - `frontend/lib/api.ts` API 클라이언트 유틸리티 생성
    - `page.tsx`에서 useState + fetch로 상태 관리 (임시 조치)
    - `SourcePanel`, `InsightCard` 컴포넌트에 실제 데이터 연결
  - [x] **tenacity 재시도 로직** (2025-12-23 추가)
    - LLM API 호출 실패 시 최대 3회 재시도
    - 지수 백오프 대기 (2초, 4초, 8초...)
    - 재시도 전 로깅
  - [x] **사용자별 저장 경로 구조** (2025-12-23 추가)
    - 저장 경로: `data/users/{user_id}/{data_type}/`
    - `CrawlRequest`, `SummarizeRequest`에 `user_id` optional 필드 추가
    - 기본 사용자 ID: `default` (프로토타입용)
  - [x] **GeekNews original_content 요약 통합** (2025-12-23 추가)
    - `SummarizeRequest`에 `original_content` optional 필드 추가
    - `SummaryService._merge_content()`로 두 소스 병합
    - 프롬프트에서 "GeekNews 요약/코멘트"와 "원본 아티클" 구분 표시
    - 프론트엔드에서 `original_content` 함께 전달

> 상세 내용은 `docs/DONE.md` 참조

### ✅ Phase 3-2 완료 항목 (2025-12-23)

- [x] **뉴스 스크립트 생성 서비스 구현** (Step 1 완료)

  - [x] `backend/app/core/config.py` - AudioService 전용 환경변수 추가
    - `AUDIO_SCRIPT_MODEL`, `AUDIO_SCRIPT_THINKING_LEVEL`, `AUDIO_SCRIPT_THINKING_BUDGET`, `AUDIO_SCRIPT_INCLUDE_THOUGHTS`, `AUDIO_SCRIPT_TEMPERATURE`
  - [x] `backend/output_schemas/audio.py` - NewsScript Pydantic 모델 정의
    - `paragraphs: list[str]`, `title: str`, `estimated_duration_sec: int`, `total_characters: int`
  - [x] `backend/prompts/v1/news_script.md` - 뉴스 대본 생성 프롬프트
    - 3분 분량 (약 900~1,050자), 8~12개 문단, 남성 아나운서 톤
  - [x] `backend/app/services/audio.py` - AudioService 클래스 구현
    - `generate_script()` 메서드: 콘텐츠 → 뉴스 스크립트 변환
    - tenacity 재시도 로직 포함
  - [x] `backend/app/api/v1/audio.py` - `POST /api/v1/audio/script` 엔드포인트
  - [x] `backend/app/main.py` - audio 라우터 등록

- [x] **프론트엔드 병렬 처리 구현** (2025-12-23)

  - [x] `frontend/lib/api.ts` - `generateScript()` 함수 및 관련 타입 추가
  - [x] `frontend/app/page.tsx` - 크롤링 후 요약+스크립트 병렬 호출 (`Promise.all` 패턴)
  - [x] `frontend/components/content-panel.tsx` - 스크립트 상태 props 전달
  - [x] `frontend/components/intelligence-panel.tsx` - AudioPlayerCard에 상태 전달
  - [x] `frontend/components/audio-player-card.tsx` - 스크립트 상태별 UI 표시
    - 스크립트 생성 중: 로딩 스켈레톤
    - 스크립트 완료: 제목, 예상 시간, 글자 수, 문단 수 표시
    - TTS 미구현 안내 메시지

- [x] **TTS 음성 합성** (Step 2 완료 - 2025-12-25)

### ✅ Phase 3-3 완료 항목 (2025-12-24)

- [x] **뉴스 스크립트 SSE 스트리밍 구현**

  - [x] `backend/prompts/v1/news_script_stream.md` - 스트리밍용 Plain Text 프롬프트
  - [x] `backend/app/services/audio.py` - `llm_streaming`, `generate_script_stream()`, `parse_stream_result()` 추가
  - [x] `backend/app/api/v1/audio.py` - `POST /api/v1/audio/script/stream` SSE 엔드포인트
  - [x] `frontend/lib/api.ts` - `generateScriptStream()`, `generateScriptStreamWithCallbacks()` 추가
  - [x] `frontend/app/page.tsx` - `ScriptStreamingState` 상태, 스트리밍 호출로 변경
  - [x] `frontend/components/audio-player-card.tsx` - 스트리밍 UI (Thinking + Script Collapsible)

- [x] **NewsScript Validation 완화**

  - [x] `backend/output_schemas/audio.py` - 스트리밍 Plain Text 파싱 대응 (paragraphs 1~20개, 시간 30~600초, 글자수 100~5000자)

- [x] **Thinking 텍스트 클리닝**

  - [x] `cleanThinkingText()` 유틸리티 함수 추가 (escaped newlines 처리)
  - [x] `frontend/components/insight-card.tsx` - 클리닝 함수 적용
  - [x] `frontend/components/audio-player-card.tsx` - 클리닝 함수 적용

- [x] **완료 상태 전체 스크립트 표시**
  - [x] `frontend/components/audio-player-card.tsx` - Collapsible로 전체 paragraphs 표시, Markdown 렌더링
  - [x] OpenAI TTS API 연동 ✅ (2025-12-25)
  - [x] 오디오 파일 생성 및 저장 ✅ (2025-12-25)

### ✅ Phase 3-4 완료 항목 (2025-12-25)

- [x] **TTS 음성 합성 구현** (Step 2 완료)

  - [x] `backend/pyproject.toml` - `pydub>=0.25.1` 의존성 추가
  - [x] `backend/app/core/config.py` - OpenAI TTS 설정 추가 (OPENAI_API_KEY, TTS_MODEL, TTS_VOICE, TTS_SILENCE_PADDING_MS)
  - [x] `backend/app/services/audio.py` - TTS 메서드 구현
    - `_call_openai_tts()`: OpenAI TTS API 호출
    - `_merge_audio_chunks()`: pydub 기반 오디오 병합 + silence padding
    - `synthesize_speech()`: 문단별 병렬 합성 (`asyncio.gather`) + MP3 저장
  - [x] `backend/app/api/v1/audio.py` - 엔드포인트 추가
    - `POST /api/v1/audio/synthesize`: TTS 합성 요청
    - `GET /api/v1/audio/{article_id}.mp3`: 오디오 파일 서빙
  - [x] `frontend/lib/api.ts` - TTS API 클라이언트
    - `SynthesizeRequest`, `SynthesizeResponse` 타입
    - `synthesizeAudio()`, `getAudioUrl()` 함수
  - [x] `frontend/components/audio-player-card.tsx` - 실제 오디오 재생 기능
    - `<audio>` 요소 + useRef 기반 컨트롤
    - 재생/일시정지, 프로그레스 바 시킹, 시간 표시
    - 다운로드 버튼 (`<a download>`)
  - [x] `frontend/app/page.tsx` - TTS 파이프라인 통합
    - `AudioStatus`에 `synthesizing` 상태 추가
    - `audioUrl`, `audioDuration` 상태 관리
    - 스크립트 완료 후 `synthesizeAudio()` 호출

### 🚧 현재 미진행 항목

- **LLM Ops**: 모델 호출 추적, 비용 모니터링, 평가 시스템 미구축.

---

## 다음 액션 아이템

### 🔴 High Priority (Phase 3 계속)

1. ~~**요약 서비스 마무리**~~ ✅ 완료 (2025-12-23)

   - [x] SummaryService 구현 완료
   - [x] `POST /api/v1/summarize` 엔드포인트 완료
   - [x] **요약 결과 JSON 로컬 저장** (`backend/data/summary/`)
   - [x] **Frontend 연동** (InsightCard에 실제 요약 데이터 표시)
   - [x] **GeekNews original_content 요약 통합** ✅ 완료 (2025-12-23)
     - 백엔드 API에 `original_content` 필드 추가
     - `SummaryService._merge_content()`로 두 소스 병합
     - 프롬프트에서 "GeekNews 요약/코멘트"와 "원본 아티클" 구분 표시
     - 프론트엔드에서 `original_content` 함께 전달
   - [x] **Prompt 개조체 스타일 적용** ✅ 완료 (2025-12-23)
     - bullet_points 각 항목을 '문장'이 아닌 '개조체(음슴체)'로 작성하도록 프롬프트 수정
     - 변경 전: "AI 시대 소프트웨어 시장은 단순한 IT 지출을 넘어 노동 대체와 실제 업무 수행 중심으로 확장되고 있습니다."
     - 변경 후: "AI 시대 소프트웨어 시장은 단순 IT 지출을 넘어 노동 대체와 실제 업무 수행 중심으로 확장 중"
       - '변경 후'는 개조체(음슴체) 문체로 보다 간결하고 가독성 높게 작성. 사용자가 최대한 빠르고 쉽게 파악할 수 있도록 간결하고 핵심만 정리해 작성하는 것이 중요함.
   - [x] **Streaming 응답 구현** ✅ 완료 (2025-12-23)
     - Backend: SSE(Server-Sent Events) 기반 스트리밍 엔드포인트 구현 (`POST /api/v1/summarize/stream`)
     - Plain Text 출력 형식으로 변경 후 파싱 (Structured output 대신)
     - Frontend: SSE 클라이언트 구현 (`summarizeStream()`, `summarizeStreamWithCallbacks()`)
     - `InsightCard`: 실시간 bullet_points 표시 UI 구현
     - 사용자 경험 개선: 전체 응답 대기 없이 점진적으로 결과 표시
   - [x] **Streaming + Thinking Step 구현** ✅ 완료 (2025-12-23)
     - 구현 방식: Plain text 스트리밍 (옵션 3 선택)
     - Backend: `SummaryService.summarize_stream()` 메서드 구현
     - Frontend: Thinking 섹션 UI (Collapsible) 구현
   - [x] **Thinking Budget 환경설정 연동** ✅ 완료 (2025-12-23)
     - `.env` 파일에 `GEMINI_THINKING_LEVEL`, `GEMINI_THINKING_BUDGET` 환경변수 추가
     - `config.py` Settings 클래스에 Thinking 관련 필드 추가
     - `SummaryService`에서 `thinking_budget` 파라미터를 settings에서 로드
     - `llm_streaming` 인스턴스 생성 시 `thinking_budget=2048`, `include_thoughts=True` 적용
     - Thinking 레벨: `"low"` (기본값), `"off"`로 비활성화 가능
     - **핵심**: `include_thoughts=True` 설정이 있어야 thinking 블록이 응답에 포함됨

2. ~~**Vertex AI API 활성화**~~ ✅ 완료
3. ~~**오디오 서비스 구현 - Step 1**~~ ✅ 완료 (2025-12-23)

   - [x] Step 1: 대본 생성 (Gemini)
     - 3분 분량의 뉴스 리포팅 대본 생성 (8~12개 문단, 각 문단 80~120자)
     - 남성 아나운서가 대본을 읽는 느낌의 스크립트 작성
     - `POST /api/v1/audio/script` 엔드포인트 구현
     - 프론트엔드 병렬 처리 연동 완료

4. ~~**오디오 서비스 구현 - Step 2**~~ ✅ 완료 (2025-12-25)

   - [x] Step 2: TTS 음성 합성 (OpenAI TTS)
     - Step1의 스크립트를 TTS 엔진에 전달하여 오디오 파일을 생성
     - TTS API는 OpenAI TTS 사용 (`gpt-4o-mini-tts` 모델, `marin` 보이스)
     - 문단별 TTS → silence padding → pydub 병합 로직 구현
     - 저장 경로: `backend/data/users/{user_id}/audio/{article_id}.mp3`

5. **API 엔드포인트 추가**
   - [x] `POST /api/v1/summarize` ✅ 완료
   - [x] `POST /api/v1/audio/script` ✅ 완료 (대본 생성)
   - [x] `POST /api/v1/audio/script/stream` ✅ 완료 (대본 스트리밍) (2025-12-24)
   - [x] `POST /api/v1/audio/synthesize` ✅ 완료 (TTS 합성) (2025-12-25)
   - [x] `GET /api/v1/audio/{article_id}.mp3` ✅ 완료 (오디오 파일 서빙) (2025-12-25)

### 🟡 Medium Priority (Phase 4)

6. **TanStack Query 설정** (프론트엔드)

   - `@tanstack/react-query` 설치
   - QueryClient Provider 설정

7. **API 연동 및 상태 관리**
   - 크롤링 → 요약 → 오디오 병렬 처리 흐름
   - 더미 데이터를 실제 API 응답으로 교체

### 🟢 Low Priority (Phase 5)

8. **에러 처리 고도화**
9. **배포 설정** (Dockerfile, Vercel)

### 🔵 Infrastructure (Phase 6 - 신규)

10. **LLM Ops 개발**

- 상세 내용은 [Phase 6: LLM Ops](#phase-6-llm-ops-모니터링-및-평가) 참조

---

## Phase 3: AI 서비스 구현 (병렬 처리)

> **목표**: 정제된 데이터를 사용하여 Gemini 및 TTS API 연결.
> **선행 완료**: Google VertexAI API 인증 설정 완료 (DONE.md 참조)

### 3-1. 요약 서비스 (LLM) ✅ 완료

**백엔드 구현:**

- [x] `backend/app/services/summary.py` 구현
- [x] LangChain `ChatGoogleGenerativeAI` + Vertex AI 백엔드 연동
- [x] `with_structured_output()` 사용하여 타입 안전한 출력
- [x] 프롬프트 파일 분리 (`prompts/v1/summary.md`)
- [x] `POST /api/v1/summarize` 엔드포인트 구현

**파이프라인 연결:**

- [x] **요약 결과 JSON 로컬 저장**
  - 저장 경로: `backend/data/summary/{article_id}_{timestamp}.json`
  - `SummarizeRequest`에 `article_id` optional 필드 추가
  - 없으면 URL/content 해시 기반 자동 생성
- [x] **Frontend 연동**
  - `InsightCard` 컴포넌트에 실제 요약 데이터 표시
  - 크롤링 완료 후 요약 API 자동 호출 흐름 구현
  - 로딩/에러 상태 UI 구현
  - ⚠️ 현재 `useState` + `fetch`로 임시 구현 (Phase 4에서 TanStack Query로 마이그레이션 예정)

**구현된 구조:**

```python
# backend/app/services/summary.py
from langchain_google_genai import ChatGoogleGenerativeAI
from output_schemas.summary import SummaryResult

class SummaryService:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            credentials=credentials,  # 서비스 계정
            project=project_id,       # Vertex AI 자동 선택
        )
        self.llm_structured = self.llm.with_structured_output(SummaryResult)

    async def summarize(self, content: str) -> SummaryResult:
        prompt = format_prompt("v1", "summary", content=content)
        return await self.llm_structured.ainvoke(prompt)
```

**완료 조건:**

1. 요약 API 호출 시 결과가 로컬 JSON 파일로 저장됨
2. Frontend InsightCard에서 실제 요약 결과가 표시됨
3. 사용자가 URL 입력 → 크롤링 → 요약 흐름을 end-to-end로 확인 가능

### 3-2. 오디오 서비스 (대본 생성 + TTS)

#### Step 1: 대본 생성 ✅ 완료 (2025-12-23)

- [x] `backend/app/services/audio.py` AudioService 구현
- [x] `backend/output_schemas/audio.py` NewsScript 스키마 정의
- [x] `backend/prompts/v1/news_script.md` 프롬프트 작성
- [x] `POST /api/v1/audio/script` 엔드포인트 구현
- [x] **Frontend 병렬 처리 연동**
  - 크롤링 완료 후 요약 + 스크립트 생성 동시 실행
  - AudioPlayerCard에서 스크립트 정보 표시

**구현된 구조:**

```python
# backend/output_schemas/audio.py
class NewsScript(BaseModel):
    paragraphs: list[str]        # 문단별 스크립트 (8~12개, TTS 청킹용)
    title: str                   # 뉴스 헤드라인
    estimated_duration_sec: int  # 예상 분량 (초)
    total_characters: int        # 총 글자 수

# backend/app/services/audio.py
class AudioService:
    async def generate_script(
        self,
        content: str,
        original_content: str | None = None,
    ) -> NewsScript:
        """콘텐츠를 뉴스 스크립트로 변환"""
        ...
```

#### Step 2: TTS 음성 합성 ✅ 완료 (2025-12-25)

- [x] OpenAI TTS API 연동 (`openai` SDK, `gpt-4o-mini-tts` 모델)
- [x] `synthesize_speech()` 메서드 구현
- [x] 문단별 TTS 병렬 합성 (`asyncio.gather`) → silence padding → pydub 병합
- [x] 오디오 파일 저장: `backend/data/users/{user_id}/audio/{article_id}.mp3`
- [x] `POST /api/v1/audio/synthesize` 엔드포인트 추가
- [x] `GET /api/v1/audio/{article_id}.mp3` 파일 서빙 엔드포인트 추가
- [x] Frontend AudioPlayerCard에서 실제 오디오 재생 기능 구현

**구현된 구조:**

```python
# backend/app/services/audio.py - TTS 핵심 메서드
async def synthesize_speech(
    self, script: NewsScript, article_id: str, user_id: str, ...
) -> dict:
    """뉴스 스크립트를 음성으로 합성"""
    # 1. 문단별 병렬 TTS 합성
    tasks = [self._call_openai_tts(p) for p in script.paragraphs]
    audio_chunks = await asyncio.gather(*tasks)

    # 2. pydub으로 silence padding + 병합
    merged_audio, duration_sec = self._merge_audio_chunks(list(audio_chunks))

    # 3. MP3 저장
    audio_path = save_dir / f"{article_id}.mp3"
    with open(audio_path, "wb") as f:
        f.write(merged_audio)

    return {"audio_path": audio_path, "duration_sec": duration_sec, ...}
```

### 3-3. API 엔드포인트

- [x] `POST /api/v1/summarize` - 요약 생성 ✅ 완료
- [x] `POST /api/v1/audio/script` - 대본 생성 ✅ 완료 (2025-12-23)
- [x] `POST /api/v1/audio/script/stream` - 대본 스트리밍 ✅ 완료 (2025-12-24)
- [x] `POST /api/v1/audio/synthesize` - TTS 음성 합성 ✅ 완료 (2025-12-25)
- [x] `GET /api/v1/audio/{article_id}.mp3` - 오디오 파일 서빙 ✅ 완료 (2025-12-25)

**실제 구현된 API 요청/응답:**

```bash
# 요약 API (스트리밍)
POST /api/v1/summarize/stream
{
  "content": "정제된 콘텐츠...",
  "original_content": "원본 외부 링크 콘텐츠...",  # Optional
  "url": "https://...",
  "article_id": "topic_25115",
  "user_id": "default"  # Optional
}

Response: SSE 스트리밍
event: thinking
data: AI 추론 과정...

event: content
data: 요약 결과...

event: done
data: {"bullet_points": [...], "main_topic": "..."}

# 대본 생성 API ✅ 완료
POST /api/v1/audio/script
{
  "content": "정제된 콘텐츠...",
  "original_content": "원본 외부 링크 콘텐츠...",  # Optional
  "url": "https://...",
  "article_id": "topic_25115",
  "user_id": "default"  # Optional
}

Response:
{
  "user_id": "default",
  "article_id": "topic_25115",
  "script": {
    "paragraphs": ["첫 번째 문단...", "두 번째 문단...", ...],
    "title": "뉴스 헤드라인 제목 (20~40자)",
    "estimated_duration_sec": 180,
    "total_characters": 950
  },
  "model": "gemini-2.5-flash",
  "processing_time_ms": 2345,
  "saved_path": "data/users/default/audio/topic_25115_2025-12-23T23-19-07.json"
}

# TTS 합성 API ✅ 완료 (2025-12-25)
POST /api/v1/audio/synthesize
{
  "article_id": "topic_25115",
  "user_id": "default"
}

Response:
{
  "audio_url": "/api/v1/audio/topic_25115.mp3?user_id=default",
  "duration_seconds": 145.5,
  "file_size_bytes": 2332800,
  "user_id": "default",
  "article_id": "topic_25115",
  "processing_time_ms": 12345
}

# 오디오 파일 서빙 ✅ 완료 (2025-12-25)
GET /api/v1/audio/{article_id}.mp3?user_id=default

Response: audio/mpeg (MP3 파일 스트리밍)
```

### 3-4. 병렬 처리 아키텍처 ✅ 전체 구현 완료

```
[POST /api/v1/crawl]
       │
       ▼
[CrawledArticle] ──────────────────────────────────────┐
       │                                                │
       ▼                                                ▼
[POST /api/v1/summarize/stream]         [POST /api/v1/audio/script/stream]
       │ (SSE 스트리밍)                          │ (SSE 스트리밍)
       ▼                                                ▼
   [Summary] ✅                                  [NewsScript] ✅
       │                                                │
       │                                                ▼
       │                              [POST /api/v1/audio/synthesize] ✅
       │                                                │
       │                                                ▼
       │                                     [GET /{article_id}.mp3] ✅
       │                                                │
       └────────────────┬───────────────────────────────┘
                        ▼
                [Frontend Display]
                - InsightCard (요약)
                - AudioPlayerCard (스크립트 + 실제 오디오 재생) ✅
```

**완료 상태:**

- ✅ 크롤링 → 요약 + 스크립트 **병렬 처리** 구현 완료
- ✅ Frontend에서 SSE 스트리밍으로 요약/스크립트 동시 수신
- ✅ TTS 음성 합성 (Step 2) 구현 완료 (2025-12-25)
- ✅ 실제 오디오 재생/다운로드 기능 구현 완료

---

## Phase 4: 프론트엔드 연동 (TanStack Query)

> **목표**: 실제 데이터 연결 및 낙관적 UI 업데이트 구현.

### ⚠️ 현재 상태 (임시 구현)

Phase 3-1에서 `useState` + `fetch`로 프론트엔드 연동을 **임시 구현**했습니다.
TanStack Query로 마이그레이션하여 다음 기능을 개선해야 합니다:

- 캐싱 및 중복 요청 방지
- 낙관적 업데이트 (Optimistic Updates)
- 자동 재시도 (Retry)
- 요청 취소 (Cancellation)

**현재 임시 구현된 파일:**

- `frontend/lib/api.ts`: API 클라이언트 유틸리티 ✅
- `frontend/app/page.tsx`: useState로 상태 관리 (→ useMutation으로 교체 필요)

### 4-1. 데이터 페칭 설정

- [ ] `@tanstack/react-query` 설치 (`pnpm add @tanstack/react-query`)
- [ ] `QueryClientProvider` 설정 (`frontend/app/providers.tsx`)
- [x] API 클라이언트 유틸리티 (`frontend/lib/api.ts`) ✅ 임시 구현 완료

**예상 구조:**

```typescript
// frontend/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = {
  crawl: (url: string) =>
    fetch(`${API_BASE}/api/v1/crawl`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }).then((res) => res.json()),

  summarize: (content: string) =>
    fetch(`${API_BASE}/api/v1/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }).then((res) => res.json()),

  generateAudio: (content: string, articleId: string) =>
    fetch(`${API_BASE}/api/v1/audio`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, article_id: articleId }),
    }).then((res) => res.json()),
};
```

### 4-2. 병렬 처리 흐름 구현

- [ ] **Step 1**: 크롤링 `useMutation` 호출 → 소스 패널 렌더링
- [ ] **Step 2**: 크롤링 성공 시 요약 및 오디오 `useMutation`을 **동시에** 트리거
- [ ] 로딩 상태별 스켈레톤 UI 표시

**예상 훅 구조:**

```typescript
// frontend/hooks/useArticleProcessing.ts
export function useArticleProcessing() {
  const crawlMutation = useMutation({
    mutationFn: api.crawl,
    onSuccess: (data) => {
      // 크롤링 성공 시 요약과 오디오를 동시에 요청
      summarizeMutation.mutate(data.cleaned_content);
      audioMutation.mutate({
        content: data.cleaned_content,
        articleId: data.article_id,
      });
    },
  });

  const summarizeMutation = useMutation({ mutationFn: api.summarize });
  const audioMutation = useMutation({ mutationFn: api.generateAudio });

  return {
    crawl: crawlMutation,
    summary: summarizeMutation,
    audio: audioMutation,
    isProcessing:
      crawlMutation.isPending ||
      summarizeMutation.isPending ||
      audioMutation.isPending,
  };
}
```

### 4-3. 상태 연결

- [x] `SourcePanel`: 더미 데이터 → 실제 API 응답 연결 ✅ (임시: props drilling)
- [x] `InsightCard`: 더미 데이터 → 실제 API 응답 연결 ✅ (임시: props drilling)
- [x] `AudioPlayerCard`: 스크립트 데이터 연결 ✅ (임시: props drilling)

> **TODO**: TanStack Query 도입 시 `useMutation` 훅으로 마이그레이션 필요

---

## Phase 5: 마무리 및 개선

### 5-1. 에러 처리

- [ ] 크롤링 차단 시 사용자 친화적 메시지
- [ ] API 제한 (Rate Limit) 처리
- [ ] 유효하지 않은 URL 처리
- [ ] 네트워크 오류 재시도 로직

### 5-2. 디테일 작업

- [x] 오디오 탐색 (Seeking) 기능 ✅ (2025-12-25)
- [ ] 재생 속도 조절 기능
- [x] 오디오 다운로드 기능 ✅ (2025-12-25)

### 5-3. 배포 설정

- [ ] `backend/Dockerfile` 작성 (Railway용)
- [ ] `frontend/` Vercel 설정
- [ ] 환경 변수 설정 가이드

---

## Phase 6: LLM Ops (모니터링 및 평가)

> **목표**: LLM 호출 추적, 비용 모니터링, 품질 평가 시스템 구축
> **도구 선택지**: 로컬(Langfuse) / 클라우드(Weights & Biases Weave)

### 6-1. Langfuse 설치 및 설정 (로컬/셀프호스팅)

- [ ] **Docker Compose로 Langfuse 서버 설치**
  ```bash
  # docker-compose.yml 작성
  docker compose up -d
  ```
- [ ] `langfuse` Python SDK 설치 (`pyproject.toml` 추가)
- [ ] LangChain 콜백 핸들러 통합
  ```python
  from langfuse.callback import CallbackHandler
  handler = CallbackHandler()
  llm.invoke(prompt, config={"callbacks": [handler]})
  ```
- [ ] 환경변수 설정 (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`)

### 6-2. Weights & Biases Weave (클라우드)

- [ ] `weave` SDK 설치
- [ ] W&B 프로젝트 설정
- [ ] LLM 호출에 `@weave.op()` 데코레이터 적용

  ```python
  import weave

  @weave.op()
  async def summarize(content: str) -> SummaryResult:
      ...
  ```

### 6-3. 모니터링 항목

- [ ] **입력/출력 저장**: 프롬프트 및 LLM 응답 기록
- [ ] **LLM Chain/Agent I/O Trace**: 호출 체인 시각화
- [ ] **비용 추적 (Cost)**: 토큰 사용량 및 API 비용 계산
- [ ] **지연 시간 (Latency)**: 응답 시간 모니터링

### 6-4. 평가 시스템 (Evaluation)

- [ ] **요약 품질 평가 메트릭 정의**
  - 정확성 (Factual Accuracy)
  - 완결성 (Completeness)
  - 간결성 (Conciseness)
- [ ] **LLM-as-Judge 평가 파이프라인 구축**
  ```python
  # 평가 프롬프트 예시
  """
  원본 텍스트와 요약을 비교하여 1-5점으로 평가해주세요.
  """
  ```
- [ ] **Human Feedback 수집 UI** (선택)
- [ ] **A/B 테스트 프레임워크**: 프롬프트 버전별 성능 비교

### 6-5. 대시보드

- [ ] Langfuse UI 또는 W&B Dashboard에서 다음 항목 시각화:
  - 일별/주별 API 호출 수
  - 평균 응답 시간
  - 토큰 사용량 및 비용
  - 에러율

**참고 문서:**

- Langfuse: https://langfuse.com/docs
- W&B Weave: https://wandb.ai/site/weave

---

## 📝 참고 사항

### 실행 환경

```bash
# Frontend (Port 3000)
cd frontend
pnpm dev

# Backend (Port 8000)
cd backend
uv run uvicorn app.main:app --reload
```

### 디렉토리 구조 (현재)

```
backend/
├── data/
│   └── users/                  # ✅ 사용자별 데이터 저장
│       └── {user_id}/          # 기본값: "default"
│           ├── crawled/        # 크롤링 결과
│           ├── summary/        # 요약 결과
│           └── audio/          # ✅ 스크립트 결과 (오디오 파일은 TTS 구현 후)
├── prompts/
│   └── v1/
│       ├── summary.md          # ✅ 완료 (요약 프롬프트)
│       ├── summary_stream.md   # ✅ 완료 (스트리밍 요약 프롬프트)
│       └── news_script.md      # ✅ 완료 (뉴스 대본 프롬프트)
├── output_schemas/
│   ├── __init__.py             # ✅ 완료
│   ├── summary.py              # ✅ 완료 (SummaryResult)
│   └── audio.py                # ✅ 완료 (NewsScript)
├── app/
│   ├── services/
│   │   ├── crawlers/           # ✅ 완료
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py
│   │   │   ├── base.py
│   │   │   ├── geeknews.py
│   │   │   ├── medium.py
│   │   │   └── factory.py
│   │   ├── prompt_loader.py    # ✅ 완료 (프롬프트 로더)
│   │   ├── summary.py          # ✅ 완료 (SummaryService + tenacity retry)
│   │   └── audio.py            # ✅ 완료 (AudioService - Step 1 대본 생성 + Step 2 TTS 합성)
│   └── api/v1/
│       ├── crawl.py            # ✅ 완료 (user_id 지원)
│       ├── summarize.py        # ✅ 완료 (user_id 지원)
│       └── audio.py            # ✅ 완료 (script, script/stream, synthesize, *.mp3)

frontend/
├── lib/
│   ├── utils.ts                # ✅ 완료
│   └── api.ts                  # ✅ 완료 (API 클라이언트 - crawl, summarize, generateScript, synthesizeAudio)
├── app/
│   └── page.tsx                # ✅ 완료 (병렬 처리 - 요약 + 스크립트 + TTS 합성)
└── components/
    ├── input-area.tsx          # ✅ 완료 (URL 입력)
    ├── content-panel.tsx       # ✅ 완료 (상태 전달 - audioUrl, audioDuration 포함)
    ├── source-panel.tsx        # ✅ 완료 (크롤링 결과 표시)
    ├── intelligence-panel.tsx  # ✅ 완료 (요약/오디오 래퍼 - 스크립트 상태 전달)
    ├── insight-card.tsx        # ✅ 완료 (요약 결과 표시)
    └── audio-player-card.tsx   # ✅ 완료 (스크립트 + 실제 오디오 재생/다운로드)
```

### 데이터 저장 구조

```
data/users/{user_id}/
├── crawled/
│   └── {article_id}_{timestamp}.json    # 크롤링 결과
├── summary/
│   └── {article_id}_{timestamp}.json    # 요약 결과
└── audio/
    ├── {article_id}_{timestamp}.json    # 뉴스 스크립트 (Step 1) ✅
    └── {article_id}.mp3                 # 오디오 파일 (Step 2 TTS) ✅
```

> **참고**: 현재 프로토타입에서는 `user_id`가 `"default"`로 고정됩니다.
> 추후 로그인 시스템 도입 시 실제 사용자 ID로 교체 예정.

### 관련 문서

- `docs/DONE.md`: 완료된 작업 히스토리 및 설계 결정 기록
- `docs/PRD.md`: 제품 요구사항 정의서
- `docs/DESIGN-SPEC.md`: 설계 명세서
- `backend/README.md`: 백엔드 설정 및 실행 방법
- `frontend/README.md`: 프론트엔드 설정 및 실행 방법
