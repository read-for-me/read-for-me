# 개발 완료 이력 (Development History)

> 이 문서는 일자별 개발 완료 이력의 인덱스입니다.
> 상세 내용은 각 일자별 파일을 참조하세요.

---

## 일자별 완료 이력

| 일자       | Phase        | 주요 작업                                                                               | 링크                          |
| ---------- | ------------ | --------------------------------------------------------------------------------------- | ----------------------------- |
| 2025-12-26 | Phase 6, 8 | **🚀 프로덕션 배포 완료**, Phoenix Tracing, GCS Storage, Cloud Run + Vercel | [상세](done/DONE-20251226.md) |
| 2025-12-25 | Phase 3, 5   | **OpenAI TTS 음성 합성**, **GenericCrawler**, 입력 검증, 에러 핸들링 시스템             | [상세](done/DONE-20251225.md) |
| 2025-12-24 | Phase 3, 4 | 뉴스 스크립트 SSE 스트리밍, **Minimal UI Refactoring**, Anthropic 색상 테마             | [상세](done/DONE-20251224.md) |
| 2025-12-23 | Phase 2, 3 | GeekNews 원본 크롤링, 요약 서비스, Thinking 스트리밍, **뉴스 스크립트 생성, 병렬 처리** | [상세](done/DONE-20251223.md) |
| 2025-12-21 | Phase 2, 3 | 크롤러 구현 완료, API 엔드포인트, Vertex AI 인증                                        | [상세](done/DONE-20251221.md) |
| 2025-12-18 | Phase 2    | 크롤러 기반 구조 구현 (ABC, 스키마)                                                     | [상세](done/DONE-20251218.md) |
| 2025-12-16 | Phase 1    | 프로젝트 구조 개편, 백엔드 셋업, 문서화                                                 | [상세](done/DONE-20251216.md) |
| 2025-12-15 | Phase 1    | 프론트엔드 UI 껍데기                                                                    | [상세](done/DONE-20251215.md) |

---

## Phase별 진행 상황

### Phase 1: 프론트엔드 UI 및 백엔드 셋업 (완료)

- 완료일: 2025-12-16
- 관련 파일: [DONE-20251215](done/DONE-20251215.md), [DONE-20251216](done/DONE-20251216.md)

**주요 작업:**

- Next.js App Router 설정, 반응형 레이아웃
- 주요 컴포넌트 구현 (InputArea, SourcePanel, InsightCard, AudioPlayerCard)
- 프로젝트 구조 개편 (frontend/backend 분리)
- FastAPI + uv 백엔드 초기 셋업
- 문서화 (README.md)

### Phase 2: 크롤링 및 ETL 아키텍처 (완료)

- 완료일: 2025-12-21
- 관련 파일: [DONE-20251218](done/DONE-20251218.md), [DONE-20251221](done/DONE-20251221.md), [DONE-20251223](done/DONE-20251223.md)

**주요 작업:**

- 추상 기본 크롤러 (BaseCrawler ABC) 설계
- GeekNews, Medium 크롤러 구현
- 크롤러 팩토리 패턴 적용
- API 엔드포인트 구현 (POST /crawl, GET /supported-domains)
- 크롤링 결과 JSON 저장
- GeekNews 원본 외부 링크 크롤링 (trafilatura)

### Phase 3: AI 서비스 구현 (완료)

- 시작일: 2025-12-23
- 완료일: 2025-12-25
- 관련 파일: [DONE-20251221](done/DONE-20251221.md), [DONE-20251223](done/DONE-20251223.md), [DONE-20251224](done/DONE-20251224.md), [DONE-20251225](done/DONE-20251225.md)

**주요 작업:**

- Vertex AI 인증 설정
- LangChain 기반 요약 서비스 구현
- Structured Output (SummaryResult) 스키마
- 프롬프트 파일 분리 관리
- Gemini Thinking 스트리밍 구현
- **뉴스 스크립트 생성 서비스 (AudioService) 구현**
- **프론트엔드 병렬 처리 (요약 ∥ 스크립트 생성)**
- **뉴스 스크립트 SSE 스트리밍 구현** (2025-12-24)
- **Thinking UI 개선 (클리닝 함수 적용)** (2025-12-24)
- **완료 상태 전체 스크립트 Collapsible 표시** (2025-12-24)
- **OpenAI TTS 음성 합성 구현** (2025-12-25)
- **문단별 병렬 TTS 합성 + pydub 오디오 병합** (2025-12-25)
- **Frontend 실제 오디오 재생/다운로드 기능** (2025-12-25)

### Phase 4: Frontend UI 개선 (완료)

- 완료일: 2025-12-24
- 관련 파일: [DONE-20251224](done/DONE-20251224.md)

**주요 작업:**

- **Minimal UI Refactoring**: Card → 타이포그래피 기반 싱글 컬럼 레이아웃
- URL 입력창 동적 배치 (idle: 중앙, 처리 중: Header)
- Anthropic 스타일 색상 테마 (크림/코랄)
- 다크모드 토글 추가
- 섹션 제목 아이콘 + 폰트 스타일 강조
- 스트리밍 shimmer 효과

### Phase 5: 크롤러 확장 & 입력 검증 (완료)

- 완료일: 2025-12-25
- 관련 파일: [DONE-20251225](done/DONE-20251225.md)

**주요 작업:**

- **GenericCrawler 구현**: trafilatura 기반 범용 크롤러
- BeautifulSoup fallback 로직
- **CrawlerFactory 확장**: detect_platform(), fallback 로직
- **에러 핸들링 시스템**: 커스텀 예외, 에러 코드, 한국어 메시지
- **Frontend 입력 검증 UI**: 실시간 URL 검증, 플랫폼 감지 표시

### Phase 6: LLMOps & Evaluation (진행 중)

- 시작일: 2025-12-26
- 관련 파일: [DONE-20251226](done/DONE-20251226.md)

**주요 작업:**

- **6-1. Phoenix Tracing 통합** ✅: Docker Compose로 로컬 환경 구축
- **6-2. 모니터링 항목** ✅: Phoenix UI에서 입력/출력 추적, Chain Trace, 비용/지연 시간 확인
- **6-3. Evaluation Pipeline**: 🔲 대기 (평가 데이터셋, LLM-as-Judge)
- **6-4. 대시보드** ✅: Phoenix UI 기본 제공
- **환경 변수 추가**: PHOENIX_COLLECTOR_ENDPOINT, PHOENIX_PROJECT_NAME, PHOENIX_ENABLED

### Phase 8: Cloud 인프라 & CI/CD (진행 중)

- 시작일: 2025-12-26
- 관련 파일: [DONE-20251226](done/DONE-20251226.md)

**주요 작업:**

- **OpenAPI 메타데이터 개선**: description, tags, contact, license
- **UTF-8 인코딩 해결**: 커스텀 OpenAPI 엔드포인트 구현
- **Apidog CI/CD 워크플로우**: GitHub Actions 자동 동기화
- **8-1. GCS Storage 마이그레이션** ✅: Storage 추상화 레이어, Signed URL 서빙
  - `StorageService` Protocol + Local/GCS 구현체
  - 환경변수(`STORAGE_BACKEND`)로 전환 가능
  - 오디오 파일 GCS Signed URL 리다이렉트
- **8-2. 프로덕션 배포** ✅ (2025-12-26):
  - **Backend**: Cloud Run 배포, Secret Manager 연동
  - **Phoenix**: Cloud Run 배포, min-instances=0 비용 최적화
  - **Frontend**: Vercel 배포, 환경변수 설정
- **환경 변수 추가**: APIDOG_API_KEY, APIDOG_PROJECT_ID, STORAGE_BACKEND, GCS_*

**배포 URL:**

| 서비스 | URL |
|--------|-----|
| Frontend | https://read-for-me-ten.vercel.app |
| Backend | https://read-for-me-backend-383521011372.asia-northeast3.run.app |
| Phoenix | https://phoenix-383521011372.asia-northeast3.run.app |

---

## ADR 인덱스

> 설계 결정 기록 (Architecture Decision Records)

| ADR     | 제목                                         | 결정일     | 링크                                                                                          |
| ------- | -------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------- |
| ADR-001 | HTTP 클라이언트로 httpx 선택                 | 2025-12-21 | [상세](done/DONE-20251221.md#adr-001-http-클라이언트로-httpx-선택)                            |
| ADR-002 | Medium 크롤링에 Freedium 활용                | 2025-12-21 | [상세](done/DONE-20251221.md#adr-002-medium-크롤링에-freedium-미러-사이트-활용)               |
| ADR-003 | 크롤러 팩토리 패턴 적용                      | 2025-12-21 | [상세](done/DONE-20251221.md#adr-003-크롤러-팩토리-패턴-적용)                                 |
| ADR-004 | Python 패키지 관리자로 uv 선택               | 2025-12-21 | [상세](done/DONE-20251221.md#adr-004-python-패키지-관리자로-uv-선택)                          |
| ADR-005 | 추상 기본 크롤러 (ABC) 설계                  | 2025-12-21 | [상세](done/DONE-20251221.md#adr-005-추상-기본-크롤러-abc-설계)                               |
| ADR-006 | 콘텐츠 마크다운 포맷팅                       | 2025-12-21 | [상세](done/DONE-20251221.md#adr-006-콘텐츠-마크다운-포맷팅)                                  |
| ADR-007 | 크롤링 결과 로컬 JSON 저장                   | 2025-12-21 | [상세](done/DONE-20251221.md#adr-007-크롤링-결과-로컬-json-저장)                              |
| ADR-008 | LangChain Structured Output 선택             | 2025-12-23 | [상세](done/DONE-20251223.md#adr-008-langchain-structured-output-선택)                        |
| ADR-009 | 프롬프트 파일 분리 관리                      | 2025-12-23 | [상세](done/DONE-20251223.md#adr-009-프롬프트-파일-분리-관리)                                 |
| ADR-010 | LangChain ChatGoogleGenerativeAI + Vertex AI | 2025-12-23 | [상세](done/DONE-20251223.md#adr-010-langchain-chatgooglegenerativeai--vertex-ai-백엔드-선택) |
| ADR-011 | 프론트엔드 병렬 처리 오케스트레이션 선택     | 2025-12-23 | [상세](done/DONE-20251223.md#adr-011-프론트엔드-병렬-처리-오케스트레이션-선택)                |
| ADR-012 | AudioService 독립 환경변수 설정              | 2025-12-23 | [상세](done/DONE-20251223.md#adr-012-audioservice-독립-환경변수-설정)                         |
| ADR-013 | 뉴스 스크립트 스트리밍 구현 방식             | 2025-12-24 | [상세](done/DONE-20251224.md#adr-013-뉴스-스크립트-스트리밍-구현-방식)                        |
| ADR-014 | NewsScript Validation 완화                   | 2025-12-24 | [상세](done/DONE-20251224.md#adr-014-newsscript-validation-완화)                              |
| ADR-015 | Minimal UI Refactoring                       | 2025-12-24 | [상세](done/DONE-20251224.md#adr-015-minimal-ui-refactoring)                                  |
| ADR-016 | URL 입력창 동적 배치                         | 2025-12-24 | [상세](done/DONE-20251224.md#adr-016-url-입력창-동적-배치)                                    |
| ADR-017 | Anthropic 스타일 색상 테마                   | 2025-12-24 | [상세](done/DONE-20251224.md#adr-017-anthropic-스타일-색상-테마)                              |
| ADR-018 | OpenAI TTS API 선택                          | 2025-12-25 | [상세](done/DONE-20251225.md#adr-018-openai-tts-api-선택)                                     |
| ADR-019 | 문단별 병렬 TTS 합성                         | 2025-12-25 | [상세](done/DONE-20251225.md#adr-019-문단별-병렬-tts-합성)                                    |
| ADR-020 | pydub 기반 오디오 병합                       | 2025-12-25 | [상세](done/DONE-20251225.md#adr-020-pydub-기반-오디오-병합)                                  |
| ADR-021 | GenericCrawler 아키텍처                      | 2025-12-25 | [상세](done/DONE-20251225.md#adr-021-genericcrawler-아키텍처)                                 |
| ADR-022 | 비텍스트 플랫폼 명시적 제외                  | 2025-12-25 | [상세](done/DONE-20251225.md#adr-022-비텍스트-플랫폼-명시적-제외)                             |
| ADR-023 | 에러 코드 기반 에러 핸들링                   | 2025-12-25 | [상세](done/DONE-20251225.md#adr-023-에러-코드-기반-에러-핸들링)                              |
| ADR-024 | 프론트엔드 디바운스 검증                     | 2025-12-25 | [상세](done/DONE-20251225.md#adr-024-프론트엔드-디바운스-검증)                                |
| ADR-025 | OpenAPI 커스텀 엔드포인트 구현               | 2025-12-26 | [상세](done/DONE-20251226.md#adr-025-openapi-커스텀-엔드포인트-구현)                          |
| ADR-026 | Apidog CI/CD 자동 동기화                     | 2025-12-26 | [상세](done/DONE-20251226.md#adr-026-apidog-cicd-자동-동기화)                                 |
| ADR-027 | Phoenix Docker 로컬 설치 선택               | 2025-12-26 | [상세](done/DONE-20251226.md#adr-027-phoenix-docker-로컬-설치-선택)                           |
| ADR-028 | LangChain Instrumentation 명시적 선택       | 2025-12-26 | [상세](done/DONE-20251226.md#adr-028-langchain-instrumentation-명시적-선택)                   |
| ADR-029 | Storage 추상화 레이어 설계                  | 2025-12-26 | [상세](done/DONE-20251226.md#adr-029-storage-추상화-레이어-설계)                              |
| ADR-030 | GCS 오디오 서빙 Signed URL 사용             | 2025-12-26 | [상세](done/DONE-20251226.md#adr-030-gcs-오디오-서빙-signed-url-사용)                         |
| ADR-031 | Cloud Run min-instances=0 설정              | 2025-12-26 | [상세](done/DONE-20251226.md#adr-031-cloud-run-min-instances0-설정)                           |
| ADR-032 | Secret Manager로 API 키 관리                | 2025-12-26 | [상세](done/DONE-20251226.md#adr-032-secret-manager로-api-키-관리)                            |

---

## 상세 레퍼런스 바로가기

| 레퍼런스                | 설명                                        | 링크                                                |
| ----------------------- | ------------------------------------------- | --------------------------------------------------- |
| Phase 2 크롤러 레퍼런스 | 디렉토리 구조, 클래스 시그니처, 사용법 예시 | [상세](done/DONE-20251221.md#phase-2-상세-레퍼런스) |

---

## 변경 이력

| 날짜       | 변경 내용                                                                  |
| ---------- | -------------------------------------------------------------------------- |
| 2025-12-26 | **🚀 프로덕션 배포 완료**: Cloud Run (Backend + Phoenix) + Vercel (Frontend) |
| 2025-12-26 | **GCS Storage 마이그레이션**: Storage 추상화 레이어, Signed URL 서빙       |
| 2025-12-26 | **Phoenix Tracing 통합**: Docker 로컬 환경, LangChain Instrumentation      |
| 2025-12-26 | **Apidog 연동 준비**: OpenAPI 메타데이터 개선, CI/CD 자동 동기화 워크플로우 |
| 2025-12-25 | **Phase 5 완료**: GenericCrawler, 에러 핸들링, Frontend 입력 검증 UI       |
| 2025-12-25 | **OpenAI TTS 음성 합성**, 문단별 병렬 합성, pydub 오디오 병합, 실제 재생   |
| 2025-12-24 | **Minimal UI Refactoring**, Anthropic 색상 테마, 스트리밍 shimmer 효과     |
| 2025-12-24 | 뉴스 스크립트 SSE 스트리밍, Thinking UI 개선, 완료 상태 전체 스크립트 표시 |
| 2025-12-23 | 뉴스 스크립트 생성 서비스 (AudioService) 구현, 프론트엔드 병렬 처리 구현   |
| 2025-12-23 | 문서 분할: 일자별 파일로 분리, 인덱스 파일로 변환                          |
| 2025-12-23 | Hydration 에러 수정, 크롤러 콘텐츠 정제 개선, 미리보기 og_description 사용 |
| 2025-12-23 | GeekNews original_content 요약 통합 (백엔드 병합 로직, 프롬프트 구분 표시) |
| 2025-12-23 | Phase 3 시작: 요약 서비스 구현 (LangChain + Vertex AI), 프롬프트 관리 체계 |
| 2025-12-23 | GeekNews 원본 외부 링크 크롤링 기능 추가 (trafilatura, 환경변수 제어)      |
| 2025-12-22 | 문서 분리: TODO.md에서 DONE.md로 완료 항목 이동, ADR 섹션 추가             |
| 2025-12-21 | Phase 2 완료: 크롤러 구현, API 엔드포인트, 통합 테스트, JSON 저장 기능     |
| 2025-12-18 | Phase 2 시작: 추상 기본 크롤러, 데이터 스키마 구현                         |
| 2025-12-16 | Phase 1 완료: 프로젝트 구조 개편, 백엔드 셋업, 문서화                      |
| 2025-12-15 | 프론트엔드 UI 껍데기 구현                                                  |
