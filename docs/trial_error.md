# 시행착오 기록 (Trial & Error Log)

> 개발 중 발생한 문제와 해결 과정을 기록합니다.

---

## 목차

1. [CORS Preflight 요청 실패 (2025-12-23)](#cors-preflight-요청-실패-2025-12-23)
2. [프론트엔드-백엔드 스키마 불일치로 인한 422 에러 (2025-12-23)](#프론트엔드-백엔드-스키마-불일치로-인한-422-에러-2025-12-23)
3. [Gemini Thinking이 스트리밍되지 않는 문제 (2025-12-23)](#gemini-thinking이-스트리밍되지-않는-문제-2025-12-23)
4. [한국 뉴스 사이트 크롤링 실패 - 봇 차단 (2025-12-25)](#한국-뉴스-사이트-크롤링-실패---봇-차단-2025-12-25)
5. [범용 크롤러 콘텐츠 추출 부족 (2025-12-25)](#범용-크롤러-콘텐츠-추출-부족-2025-12-25)
6. [Medium 크롤러 미러 서비스 불안정 (2025-12-25)](#medium-크롤러-미러-서비스-불안정-2025-12-25)

---

## CORS Preflight 요청 실패 (2025-12-23)

### 1) 문제 상황

프론트엔드(localhost:3000)에서 백엔드(localhost:8000)로 API 요청 시 CORS 에러 발생.

**증상:**

- 브라우저 콘솔: `Access to fetch at 'http://localhost:8000/api/v1/crawl' from origin 'http://localhost:3000' has been blocked by CORS policy`
- 백엔드 로그: `OPTIONS /api/v1/crawl HTTP/1.1" 400 Bad Request`
- CORS 미들웨어가 활성화되었다고 로그에 표시되었지만 preflight 요청이 계속 실패

**혼란스러웠던 점:**

- `.env`에 `BACKEND_CORS_ORIGINS=["http://localhost:3000/"]` 설정 완료
- 백엔드 로그에 `CORS 허용 origins: ['http://localhost:3000/']`, `CORS 미들웨어 활성화됨` 표시
- 설정이 제대로 되어있는 것처럼 보였지만 계속 실패

---

### 2) 문제 원인

**Origin 문자열 불일치 (Trailing Slash)**

| 구분                     | 값                       | 비고                    |
| ------------------------ | ------------------------ | ----------------------- |
| 브라우저가 보내는 Origin | `http://localhost:3000`  | trailing slash **없음** |
| 백엔드 허용 Origin       | `http://localhost:3000/` | trailing slash **있음** |

CORS는 **정확한 문자열 일치(exact string match)**를 요구합니다.
단 하나의 문자(`/`)만 달라도 Origin이 일치하지 않는 것으로 판단되어 CORS 정책 위반으로 처리됩니다.

**원인 발생 경로:**

1. `.env` 파일에 URL 끝에 `/`를 포함하여 작성: `["http://localhost:3000/"]`
2. Pydantic의 `AnyHttpUrl` 타입이 URL을 파싱할 때 trailing slash를 그대로 유지
3. FastAPI CORS 미들웨어가 이 값을 그대로 사용하여 비교
4. 브라우저 Origin(`http://localhost:3000`)과 불일치 → CORS 실패

---

### 3) 해결 방안

**방안 A: `.env` 파일 수정** (권장)

```env
# Before (문제)
BACKEND_CORS_ORIGINS=["http://localhost:3000/"]

# After (해결)
BACKEND_CORS_ORIGINS=["http://localhost:3000"]
```

**방안 B: 코드에서 정규화 처리** (방어적 프로그래밍)

```python
# main.py에서 trailing slash 자동 제거
cors_origins_normalized = [o.rstrip("/") for o in cors_origins]
```

현재는 **방안 B**를 적용하여 `.env` 설정 오류에도 방어적으로 대응하도록 구현했습니다.

---

### 4) Before & After

#### Before (문제 발생)

```python
# backend/app/main.py
def get_application() -> FastAPI:
    _app = FastAPI(...)

    cors_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
    # cors_origins = ['http://localhost:3000/']  ← trailing slash 포함

    if cors_origins:
        _app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,  # 불일치 발생!
            ...
        )
```

**결과:**

```
브라우저 Origin: http://localhost:3000
허용된 Origin:   http://localhost:3000/
→ 불일치 → CORS 실패 → 400 Bad Request
```

#### After (문제 해결)

```python
# backend/app/main.py
def get_application() -> FastAPI:
    _app = FastAPI(...)

    cors_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]

    # trailing slash 제거 (정규화)
    cors_origins_normalized = [o.rstrip("/") for o in cors_origins]
    # cors_origins_normalized = ['http://localhost:3000']  ← trailing slash 제거됨

    if cors_origins_normalized:
        _app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins_normalized,  # 정규화된 값 사용
            ...
        )
```

**결과:**

```
브라우저 Origin: http://localhost:3000
허용된 Origin:   http://localhost:3000
→ 일치 → CORS 성공 → 200 OK
```

---

### 5) Insight

#### 핵심 교훈

1. **CORS는 정확한 문자열 비교를 수행한다**

   - 프로토콜, 호스트, 포트뿐만 아니라 **경로 구분자(`/`)까지** 정확히 일치해야 함
   - `http://localhost:3000` ≠ `http://localhost:3000/`

2. **설정값은 항상 정규화하라 (Defensive Programming)**

   - 사용자 입력이나 설정 파일의 값은 예상치 못한 형태일 수 있음
   - trailing/leading 공백, slash 등을 코드에서 정리하는 것이 안전

3. **"설정이 맞는 것 같은데 안 되는" 상황에서는 실제 값을 로깅하라**

   - 로그에 `CORS 허용 origins: ['http://localhost:3000/']`가 출력되었지만 trailing slash를 눈치채지 못함
   - 디버그 로그로 `has_trailing_slash: [true]`를 명시적으로 출력했을 때 비로소 발견

4. **CORS 디버깅 체크리스트**
   - [ ] 허용된 Origin과 브라우저 Origin이 **문자 단위로** 정확히 일치하는가?
   - [ ] trailing slash가 있는가?
   - [ ] 프로토콜(http/https)이 일치하는가?
   - [ ] 포트 번호가 일치하는가?
   - [ ] CORS 미들웨어가 라우터보다 먼저 등록되어 있는가?

#### 재발 방지

1. **`.env.example` 파일에 올바른 형식 예시 제공**

   ```env
   # CORS 설정 (trailing slash 없이 작성)
   BACKEND_CORS_ORIGINS=["http://localhost:3000"]
   ```

2. **코드에서 정규화 처리 유지**

   - 실수로 trailing slash가 포함되어도 자동 수정됨

3. **CI/CD에서 CORS 테스트 추가 고려**
   - preflight 요청이 200을 반환하는지 자동 테스트

---

## 프론트엔드-백엔드 스키마 불일치로 인한 422 에러 (2025-12-23)

### 1) 문제 상황

프론트엔드에서 크롤링 → 요약 파이프라인 실행 시, 요약 API 호출에서 422 에러 발생.

**증상:**

- 브라우저 콘솔: `POST http://localhost:8000/api/v1/summarize 422 (Unprocessable Entity)`
- 브라우저 콘솔: `Uncaught TypeError: Cannot read properties of undefined (reading 'slice')` at `source-panel.tsx:105`
- 크롤링은 200 OK로 성공했지만, 요약 API 호출 시 필수 필드 누락 에러

**혼란스러웠던 점:**

- 크롤링 API는 정상 동작하고 데이터가 잘 반환됨
- 프론트엔드 타입 정의(`CrawlResponse`)가 존재하고 `content` 필드가 명시됨
- 요약 API 호출 시 `crawled.content`를 전달했는데 왜 필드가 없다고 하는지 이해 불가

---

### 2) 문제 원인

**백엔드와 프론트엔드 간 데이터 스키마 불일치**

| 구분                       | 필드명            | 비고               |
| -------------------------- | ----------------- | ------------------ |
| 백엔드 `CleanedArticle`    | `cleaned_content` | 실제 API 응답      |
| 프론트엔드 `CrawlResponse` | `content`         | 타입 정의 (잘못됨) |

**문제 발생 경로:**

1. 백엔드 `CleanedArticle` 스키마에서 `cleaned_content` 필드명 사용
2. 프론트엔드 `CrawlResponse` 타입은 `content` 필드를 기대
3. `crawled.content`가 `undefined`가 됨 (존재하지 않는 필드 접근)
4. 요약 API 호출 시 `content: undefined` 전송 → Pydantic validation 실패 → 422 에러
5. `source-panel.tsx`에서 `data.content.slice(0, 300)` 호출 시 undefined 에러

**디버그 로그 증거:**

```json
// 크롤링 응답 원본 데이터
{
  "keys": ["title","cleaned_content","preview_text","url","platform","crawled_at","metadata","original_content"],
  "hasContent": false,
  "hasCleanedContent": true
}

// 요약 API 호출 직전
{
  "contentType": "undefined",
  "isUndefined": true
}

// 422 에러 응답
{
  "detail": [{"type":"missing","loc":["body","content"],"msg":"Field required"}]
}
```

---

### 3) 해결 방안

**프론트엔드 타입을 백엔드 스키마와 일치시킴**

수정 파일:

1. `frontend/lib/api.ts` - `CrawlResponse` 타입 수정
2. `frontend/app/page.tsx` - 요약 API 호출 시 올바른 필드 사용
3. `frontend/components/source-panel.tsx` - 렌더링 시 올바른 필드 사용

---

### 4) Before & After

#### Before (문제 발생)

```typescript
// frontend/lib/api.ts
export interface CrawlResponse {
  url: string;
  title: string;
  content: string; // ❌ 백엔드에 없는 필드
  platform: string;
  author: string | null; // ❌ metadata 내부에 있음
  thumbnail_url: string | null; // ❌ metadata.og_image
  word_count: number; // ❌ 백엔드에 없는 필드
  // ...
}

// frontend/app/page.tsx
const summary = await summarizeContent({
  content: crawled.content, // ❌ undefined
  // ...
});

// frontend/components/source-panel.tsx
{
  data.content.slice(0, 300);
} // ❌ undefined.slice() 에러
```

#### After (문제 해결)

```typescript
// frontend/lib/api.ts
export interface ArticleMetadata {
  og_image?: string;
  author?: string;
  published_at?: string;
  // ...
}

export interface CrawlResponse {
  title: string;
  cleaned_content: string; // ✅ 백엔드와 일치
  preview_text: string; // ✅ 백엔드와 일치
  url: string;
  platform: string;
  crawled_at: string;
  metadata: ArticleMetadata; // ✅ 백엔드와 일치
  original_content: string;
}

// frontend/app/page.tsx
const summary = await summarizeContent({
  content: crawled.cleaned_content, // ✅ 올바른 필드
  // ...
});

// frontend/components/source-panel.tsx
{
  data.preview_text || data.cleaned_content?.slice(0, 300);
} // ✅ 올바른 필드
{
  data.metadata?.author;
} // ✅ metadata 객체 접근
{
  data.metadata?.og_image;
} // ✅ metadata 객체 접근
```

---

### 5) Insight

#### 핵심 교훈

1. **프론트엔드 타입은 백엔드 스키마의 "그림자"가 아니다**

   - 별도로 정의한 타입은 실제 API 응답과 동기화되지 않음
   - 백엔드 스키마가 변경되면 프론트엔드 타입도 수동으로 업데이트 필요

2. **"데이터가 있는 것 같은데 없다"면 필드명을 의심하라**

   - 크롤링은 성공했지만 `content`가 undefined → 필드명이 다른 것
   - 디버그 로그로 `Object.keys()`를 출력하면 실제 필드명 확인 가능

3. **타입스크립트 타입 ≠ 런타임 보장**

   - `CrawlResponse` 타입에 `content: string`이 있어도 런타임에 없을 수 있음
   - 타입은 컴파일 타임 검사일 뿐, 실제 API 응답을 보장하지 않음

4. **프론트엔드-백엔드 스키마 불일치 디버깅 체크리스트**
   - [ ] 백엔드 응답의 실제 필드명 확인 (`Object.keys()` 로깅)
   - [ ] 프론트엔드 타입 정의와 백엔드 스키마 비교
   - [ ] 중첩 객체 구조 확인 (예: `author` vs `metadata.author`)
   - [ ] optional 필드와 required 필드 구분

#### 재발 방지

1. **백엔드 스키마에서 타입 자동 생성 고려**

   - OpenAPI 스키마 기반 타입 생성 도구 활용 (예: `openapi-typescript`)
   - 백엔드 변경 시 프론트엔드 타입 자동 동기화

2. **API 응답 검증 레이어 추가**

   - Zod 등으로 런타임 응답 검증
   - 필드 누락 시 명확한 에러 메시지 제공

3. **E2E 테스트로 파이프라인 검증**
   - 크롤링 → 요약 전체 플로우 자동화 테스트

---

## Gemini Thinking이 스트리밍되지 않는 문제 (2025-12-23)

### 1) 문제 상황

Gemini의 Thinking (AI 추론 과정) 기능을 구현했으나, Frontend UI에 Thinking 내용이 표시되지 않음.

**증상:**

- `thinking_budget=2048`로 설정했으나 Thinking 섹션이 비어있음
- 스트리밍 응답은 정상적으로 수신되지만 모두 `content` 타입
- `thinking` 이벤트가 전혀 발생하지 않음

**혼란스러웠던 점:**

- `thinking_budget` 파라미터를 `ChatGoogleGenerativeAI`에 정상 전달
- 백엔드 로그에 `thinking_budget=2048`로 초기화됨 확인
- LangChain 문서에서 `thinking_budget` 설정만으로 충분해 보였음

---

### 2) 문제 원인

**`include_thoughts=True` 파라미터 누락**

LangChain 문서에 명시된 내용:

> **To see a thinking model's reasoning, set `include_thoughts=True`**

| 파라미터           | 역할                        | 비고                                  |
| ------------------ | --------------------------- | ------------------------------------- |
| `thinking_budget`  | Thinking 토큰 예산 설정     | 얼마나 "생각"할지 제어                |
| `include_thoughts` | Thinking 내용을 응답에 포함 | **이게 없으면 thinking 블록 미포함!** |

**문제 발생 경로:**

1. `thinking_budget=2048`만 설정
2. Gemini API는 내부적으로 thinking 수행 (토큰 소비)
3. 하지만 `include_thoughts=True`가 없어서 응답에 thinking 블록 미포함
4. `chunk.content`가 항상 `str` 타입 (list가 아님)
5. thinking 파싱 로직에 도달하지 않음

**디버그 로그 증거:**

```json
// 청크 #1 (문제 상황)
{
  "content_type": "str",
  "is_list": false,
  "content_preview": "[주제]\n조직 내 정보 필터링 구조가..."
}
```

모든 청크에서 `content_type`이 `"str"`이고 `is_list: false`였음.

---

### 3) 해결 방안

**`include_thoughts=True` 파라미터 추가**

```python
self.llm_streaming = ChatGoogleGenerativeAI(
    model=model_name,
    credentials=credentials,
    project=self.project_id,
    temperature=0.3,
    thinking_budget=self.thinking_budget,
    include_thoughts=True,  # ← 이 파라미터 추가!
)
```

---

### 4) Before & After

#### Before (문제 발생)

```python
# backend/app/services/summary.py
self.llm_streaming = ChatGoogleGenerativeAI(
    model=model_name,
    credentials=credentials,
    project=self.project_id,
    temperature=0.3,
    thinking_budget=self.thinking_budget,  # ← 이것만 설정
)
```

**결과:**

```
chunk.content = "문자열 응답..."  # str 타입
→ thinking 블록 없음 → UI에 표시 안 됨
```

#### After (문제 해결)

```python
# backend/app/services/summary.py
self.llm_streaming = ChatGoogleGenerativeAI(
    model=model_name,
    credentials=credentials,
    project=self.project_id,
    temperature=0.3,
    thinking_budget=self.thinking_budget,
    include_thoughts=True,  # ← 추가됨
)
```

**결과:**

```
chunk.content = [
  {"type": "thinking", "thinking": "분석 중..."},
  {"type": "text", "text": "요약 결과..."}
]  # list 타입
→ thinking 블록 파싱 → UI에 표시됨
```

---

### 5) Insight

#### 핵심 교훈

1. **LangChain 문서를 꼼꼼히 읽어라**

   - `thinking_budget`과 `include_thoughts`는 별개의 파라미터
   - `thinking_budget`: 토큰 예산 (얼마나 생각할지)
   - `include_thoughts`: 응답에 포함 여부 (보여줄지 말지)

2. **"설정했는데 안 되면" 응답 구조를 로깅하라**

   - `chunk.content`의 타입(`str` vs `list`)을 확인
   - `isinstance(chunk.content, list)` 조건이 왜 안 들어가는지 추적

3. **파라미터 이름에 속지 말라**
   - `thinking_budget`이라는 이름만 보고 "이거면 되겠지" 생각
   - 실제로는 예산 설정과 출력 포함이 분리된 개념

#### 재발 방지

1. **API 파라미터 체크리스트 확인**

   - 새 기능 구현 시 관련 파라미터 전체 목록 검토
   - "필수" vs "선택" 파라미터 구분

2. **공식 문서의 예제 코드를 그대로 따르기**

   ```python
   # LangChain 문서 예제
   llm = ChatGoogleGenerativeAI(
       model="gemini-2.5-flash",
       thinking_budget=1024,
       include_thoughts=True,  # ← 문서에 명시됨
   )
   ```

3. **응답 구조 검증 로그 추가**
   - 개발 중에는 `type(chunk.content).__name__` 로깅
   - 예상과 다른 타입이면 즉시 원인 추적

---

## 한국 뉴스 사이트 크롤링 실패 - 봇 차단 (2025-12-25)

### 1) 문제 상황

GenericCrawler로 한국 주요 뉴스 사이트(조선일보, 한겨레)를 크롤링 시도했으나 404 에러 발생.

**증상:**

- `curl` 또는 `httpx`로 조선일보, 한겨레 URL 요청 시 404 응답
- 브라우저에서는 정상 접근 가능
- GeekNews, a16z, Anthropic 등 다른 사이트는 정상 크롤링

**혼란스러웠던 점:**

- URL이 유효하고 브라우저에서 접근 가능
- 네이버 뉴스는 동일한 방식으로 크롤링 성공
- 특정 한국 뉴스 사이트만 실패

---

### 2) 문제 원인

**봇 차단 (Bot Detection)**

| 사이트     | 응답 | 원인                            |
| ---------- | ---- | ------------------------------- |
| 조선일보   | 404  | User-Agent 또는 IP 기반 봇 차단 |
| 한겨레     | 404  | 동일                            |
| BBC Korean | 404  | 동일                            |

많은 뉴스 사이트들이 봇 트래픽을 차단하기 위해:

1. User-Agent 검사
2. JavaScript 렌더링 필수화
3. Cloudflare 등 WAF 적용
4. 리퍼러 검사

---

### 3) 해결 방안

**방안 A: User-Agent 변경** (부분 효과)

```python
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36..."
}
```

**방안 B: Playwright 사용** (Phase 7 예정)

```python
# 동적 렌더링이 필요한 사이트용
from playwright.async_api import async_playwright
```

**방안 C: 사용자 안내**

```
"이 뉴스 사이트는 직접 접근이 제한됩니다.
네이버 뉴스 링크로 시도해보세요."
```

현재는 **방안 C**를 적용하여 사용자에게 적절한 안내 제공.

---

### 4) Before & After

#### Before (문제 발생)

```python
# GenericCrawler - 기본 헤더만 사용
async def fetch_html(self, url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)  # 404 for 조선일보
        return response.text
```

**결과:**

```
조선일보 URL → 404 Not Found
한겨레 URL → 404 Not Found
```

#### After (개선)

```python
# 1. 에러 코드로 사용자 친화적 메시지 제공
ERROR_MESSAGES = {
    "CRAWL_FAILED": "크롤링 중 오류가 발생했습니다. 일부 뉴스 사이트는 직접 접근이 제한될 수 있습니다.",
}

# 2. 대안 URL 안내 (네이버 뉴스 등)
```

---

### 5) Insight

#### 핵심 교훈

1. **모든 웹사이트가 크롤링 가능하지 않다**

   - 봇 차단은 일반적인 보안 조치
   - 특히 한국 주요 언론사들은 봇 차단이 강함

2. **대안 경로를 고려하라**

   - 네이버 뉴스 등 집계 플랫폼 활용
   - RSS 피드 사용 검토
   - 공식 API 제공 여부 확인

3. **사용자 경험을 해치지 않게 실패 처리**
   - 명확한 에러 메시지
   - 대안 URL 제안
   - 지원 플랫폼 목록 안내

#### 재발 방지

1. **지원/미지원 플랫폼 문서화**

   - 테스트한 사이트 목록과 결과 기록
   - 사용자에게 지원 현황 안내

2. **Phase 7에서 Playwright 검토**
   - JavaScript 렌더링이 필요한 사이트 대응
   - 단, 리소스 비용 고려 필요

---

## 범용 크롤러 콘텐츠 추출 부족 (2025-12-25)

### 1) 문제 상황

trafilatura만 사용할 경우 일부 사이트에서 콘텐츠가 충분히 추출되지 않는 문제.

**증상:**

- trafilatura가 50자 미만의 콘텐츠만 추출
- 페이지에는 분명히 본문이 있지만 추출 실패
- `NO_CONTENT` 에러 발생

---

### 2) 문제 원인

**trafilatura의 본문 추출 알고리즘 한계**

| 원인                 | 설명                                      |
| -------------------- | ----------------------------------------- |
| 비표준 HTML 구조     | `<article>`, `<main>` 없이 `<div>`만 사용 |
| 언어 감지 실패       | 한국어/영어 혼용 시 잘못된 언어로 감지    |
| 광고/내비게이션 과다 | 본문보다 부가 요소가 많은 경우            |

---

### 3) 해결 방안

**BeautifulSoup Fallback 구현**

```python
def _extract_content_fallback(self, html: str) -> str | None:
    """trafilatura 실패 시 BeautifulSoup으로 추출"""
    soup = BeautifulSoup(html, "lxml")

    # 일반적인 본문 컨테이너 셀렉터
    selectors = [
        "article",
        "main",
        ".post-content",
        ".article-content",
        ".entry-content",
        "#content",
        ".content",
    ]

    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(separator="\n", strip=True)
            if len(text) >= 50:
                return text

    return None
```

---

### 4) Before & After

#### Before (문제 발생)

```python
def _extract_content(self, html: str) -> str | None:
    return trafilatura.extract(html)  # 일부 사이트에서 실패
```

**결과:**

```
일부 사이트 → None 또는 짧은 텍스트 → NO_CONTENT 에러
```

#### After (개선)

```python
def _extract_content(self, html: str) -> str | None:
    # 1차: trafilatura 시도
    content = trafilatura.extract(
        html,
        target_language="ko",
        favor_recall=True,  # 더 많은 콘텐츠 추출 우선
    )
    if content and len(content) >= 50:
        return content

    # 2차: BeautifulSoup fallback
    return self._extract_content_fallback(html)
```

**결과:**

```
trafilatura 실패 사이트 → BeautifulSoup으로 추출 성공
```

---

### 5) Insight

#### 핵심 교훈

1. **단일 도구에 의존하지 말라**

   - trafilatura는 훌륭하지만 완벽하지 않음
   - Fallback 전략이 필수

2. **옵션 파라미터를 활용하라**

   - `favor_recall=True`: 더 많은 콘텐츠 추출 우선
   - `target_language="ko"`: 한국어 콘텐츠 우선

3. **콘텐츠 길이 검증을 추가하라**
   - 50자 미만은 유의미한 콘텐츠가 아닐 가능성 높음
   - 임계치를 두고 fallback 트리거

#### 재발 방지

1. **다단계 추출 전략**

   ```
   trafilatura → BeautifulSoup (셀렉터) → BeautifulSoup (body 전체)
   ```

2. **콘텐츠 길이 기반 검증**

   - 최소 길이 임계치 설정
   - 너무 짧으면 에러 또는 fallback

3. **플랫폼별 커스텀 셀렉터 확장**
   - 자주 실패하는 사이트에 대해 커스텀 셀렉터 추가

---

## Medium 크롤러 미러 서비스 불안정 (2025-12-25)

### 1) 문제 상황

Medium 아티클 크롤링 시 Freedium 미러 서비스가 빈번하게 404를 반환하여 크롤링 실패율이 높았음.

**증상:**

- Freedium (`freedium.cfd`)에서 많은 Medium 아티클이 404 반환
- 원본 Medium URL은 봇 탐지로 403 Forbidden 반환
- 일부 아티클만 성공적으로 크롤링 가능
- 사용자가 애용하는 플랫폼이라 높은 성공률 필요

**혼란스러웠던 점:**

- Freedium이 모든 Medium 아티클을 지원할 것으로 예상했음
- 일부 아티클은 성공, 일부는 실패 - 규칙이 불명확
- 미러 서비스가 실시간 크롤링이 아닌 캐시 기반인 것으로 추정

---

### 2) 문제 원인

**미러 서비스의 캐시 기반 운영**

| 미러 서비스 | 동작 방식            | 한계               |
| ----------- | -------------------- | ------------------ |
| Freedium    | 캐시된 아티클만 제공 | 모든 아티클 지원 X |
| Scribe.rip  | 실시간 프록시 시도   | 일부 아티클 404    |
| 원본 Medium | 봇 탐지              | httpx로 403 반환   |

**실패 경로:**

1. 사용자가 Medium URL 입력
2. Freedium에서 404 (캐시에 없음)
3. 원본 Medium에서 403 (봇 차단)
4. 크롤링 실패

**테스트 결과:**

```
@shahbhat/vllm 아티클    → Freedium ✅ 성공
netflix-techblog 아티클  → Freedium ✅ 성공
towards-data-science     → Freedium ❌ 404
@nishantsubramani        → 모든 방법 ❌ 실패 (아티클 삭제됨)
```

---

### 3) 해결 방안

**5단계 Fallback 전략 구현**

```
Medium URL
    │
    ▼
┌─────────────┐
│  Freedium   │ ──→ 성공 시 반환
└─────────────┘
    │ 실패
    ▼
┌─────────────┐
│ Scribe.rip  │ ──→ 성공 시 반환
└─────────────┘
    │ 실패
    ▼
┌─────────────┐
│ trafilatura │ ──→ 성공 시 반환
│ (원본 URL)  │
└─────────────┘
    │ 실패
    ▼
┌─────────────┐
│ 원본 Medium │ ──→ 성공 시 반환
│ (직접 파싱) │
└─────────────┘
    │ 실패
    ▼
┌─────────────┐
│ 🎭 Playwright │ ──→ 동적 렌더링
│ (최후의 수단) │     404 감지 시 실패 처리
└─────────────┘
```

**구현 세부 사항:**

1. **Scribe.rip 미러 추가**: Freedium 대안으로 추가
2. **trafilatura fallback**: 원본 URL에서 직접 추출 시도
3. **Playwright 동적 렌더링**: headless Chromium으로 JavaScript 렌더링
4. **404 페이지 콘텐츠 필터링**: Medium 특유의 404 페이지 문구 감지

---

### 4) Before & After

#### Before (문제 발생)

```python
# backend/app/services/crawlers/medium.py
async def extract(self, url: str) -> Optional[CrawledArticle]:
    # Freedium만 시도
    if self.use_freedium:
        freedium_url = self._convert_to_freedium_url(original_url)
        html = await self.fetch_html(freedium_url)

        if html:
            return self._parse_freedium_content(soup, original_url)

    # Freedium 실패 시 원본 URL 시도 (대부분 403)
    html = await self.fetch_html(original_url)
    return self._parse_medium_content(soup, original_url)
```

**결과:**

```
Freedium 404 → 원본 403 → 크롤링 실패
많은 아티클에서 실패
```

#### After (개선)

```python
# backend/app/services/crawlers/medium.py
MIRROR_SERVICES = [
    ("freedium", "https://freedium.cfd"),
    ("scribe", "https://scribe.rip"),
]

async def extract(self, url: str) -> Optional[CrawledArticle]:
    # 1. 미러 서비스 순차 시도
    for service_name, base_url in self.MIRROR_SERVICES:
        mirror_url = self._convert_to_mirror_url(original_url, service_name)
        html = await self.fetch_html(mirror_url)

        if html and len(html) > 1000 and not self._is_error_page(html):
            result = self._parse_content(soup, original_url, service_name)
            if result and len(result.content) > 100:
                return result

    # 2. trafilatura fallback
    result = await self._extract_with_trafilatura(original_url)
    if result:
        return result

    # 3. 원본 Medium 직접 파싱
    html = await self.fetch_html(original_url)
    if html:
        result = self._parse_medium_content(soup, original_url)
        if result and len(result.content) > 100:
            return result

    # 4. Playwright 동적 렌더링 (최후의 수단)
    result = await self._extract_with_playwright(original_url)
    if result:
        return result

    return None
```

```python
# Playwright fallback 구현
async def _extract_with_playwright(self, url: str) -> Optional[CrawledArticle]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; ...)...",
        )

        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)  # JS 렌더링 대기

        html = await page.content()
        await browser.close()

        # trafilatura로 본문 추출
        content = trafilatura.extract(html, favor_recall=True)

        # 404 페이지 콘텐츠 필터링
        if self._is_404_content(content):
            return None

        return CrawledArticle(...)
```

```python
# 404 페이지 콘텐츠 감지
def _is_404_content(self, content: str) -> bool:
    if not content:
        return True

    error_indicators = [
        "page not found",
        "404",
        "out of nothing, something",  # Medium 404 특유 문구
        "you can find (just about) anything on medium",
    ]

    first_part = content.lower()[:500]
    return any(indicator in first_part for indicator in error_indicators)
```

**결과:**

```
Freedium 404 → Scribe 404 → trafilatura 403 → Playwright 시도
→ 실제 콘텐츠 있으면 성공, 404 페이지면 올바르게 실패 처리
```

---

### 5) Insight

#### 핵심 교훈

1. **미러 서비스는 완벽하지 않다**

   - Freedium/Scribe 모두 캐시 기반으로 모든 아티클 지원 X
   - 여러 미러를 순차적으로 시도하는 전략 필요

2. **다단계 Fallback이 필수**

   - 단일 방법에 의존하면 실패율 높음
   - 미러 → trafilatura → Playwright 순서로 시도
   - 각 단계에서 콘텐츠 품질 검증 (길이, 404 감지)

3. **Playwright는 최후의 수단으로 사용**

   - 약 30초의 추가 시간 소요
   - 리소스 비용이 높음 (브라우저 실행)
   - 하지만 봇 탐지 우회에 효과적

4. **404 페이지 콘텐츠 필터링이 중요**
   - Playwright는 HTML을 성공적으로 가져오지만 내용이 404 페이지일 수 있음
   - 콘텐츠 자체를 검사하여 유효성 확인 필요

#### 최종 테스트 결과

| 아티클           | Freedium | Scribe | trafilatura | Playwright  | 결과            |
| ---------------- | -------- | ------ | ----------- | ----------- | --------------- |
| @shahbhat/vllm   | ✅       | -      | -           | -           | **성공**        |
| netflix-techblog | ✅       | -      | -           | -           | **성공**        |
| google-cloud     | ❌ 404   | ❌ 404 | ✅          | -           | **성공**        |
| 삭제된 아티클    | ❌ 404   | ❌ 404 | ❌ 403      | ✅→404 감지 | **올바른 실패** |

#### 재발 방지

1. **미러 서비스 모니터링**

   - 새로운 미러 서비스 발견 시 추가 검토
   - 기존 미러 서비스 상태 주기적 확인

2. **Fallback 단계 확장 가능하게 설계**

   - 새로운 방법 추가 시 기존 코드 수정 최소화
   - 각 단계가 독립적으로 동작

3. **에러 로깅 상세화**
   - 각 단계의 성공/실패 원인 로깅
   - 디버깅 및 개선점 파악 용이

---

## 템플릿

새로운 시행착오 기록 시 아래 템플릿을 사용하세요:

```markdown
## [문제 제목] (YYYY-MM-DD)

### 1) 문제 상황

- 증상
- 에러 메시지
- 혼란스러웠던 점

### 2) 문제 원인

- 근본 원인 분석
- 원인 발생 경로

### 3) 해결 방안

- 방안 A, B, C...
- 선택한 방안과 이유

### 4) Before & After

- 코드/설정 변경 전후 비교

### 5) Insight

- 핵심 교훈
- 재발 방지 방안
```
