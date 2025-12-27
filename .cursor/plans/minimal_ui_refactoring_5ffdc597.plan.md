---
name: Minimal UI Refactoring
overview: 현재 카드 기반의 레이아웃을 콘텐츠 중심의 미니멀 디자인으로 전환합니다. 2컬럼 구조를 싱글 컬럼으로 변경하고, 카드 border/shadow를 제거하여 타이포그래피와 여백으로 시각적 계층을 표현합니다.
todos:
  - id: style-update
    content: globals.css에 미니멀 스타일 변수 및 유틸리티 추가
    status: completed
  - id: header-input-merge
    content: Header와 InputArea를 통합하여 컴팩트한 상단 바 구현
    status: completed
    dependencies:
      - style-update
  - id: content-single-column
    content: ContentPanel을 싱글 컬럼 레이아웃으로 변경
    status: completed
    dependencies:
      - style-update
  - id: source-refactor
    content: SourcePanel에서 카드 제거, 접기/펼치기 메타 정보로 변경
    status: completed
    dependencies:
      - content-single-column
  - id: insight-refactor
    content: InsightCard에서 카드 제거, 타이포그래피 기반 섹션으로 변경
    status: completed
    dependencies:
      - content-single-column
  - id: audio-simplify
    content: AudioPlayerCard를 미니멀 플레이어로 심플화
    status: completed
    dependencies:
      - content-single-column
  - id: cleanup
    content: IntelligencePanel 제거 및 불필요한 import 정리
    status: completed
    dependencies:
      - insight-refactor
      - audio-simplify
---

# Minimal UI Refactoring Plan

## 목표

"URL 입력 -> 컨텐츠 읽기/다운로드"라는 핵심 플로우에 맞춰, 불필요한 시각 요소를 제거하고 콘텐츠 중심의 미니멀 디자인을 구현합니다.

## 디자인 컨셉

```javascript
[Before - Card Heavy]                    [After - Content First]
┌──────────────────────────┐             ┌──────────────────────────┐
│     큰 Hero 영역          │             │ Read-For-Me  [URL입력]   │
│  [URL 입력창] [실행]      │             ├──────────────────────────┤
├─────────┬────────────────┤             │                          │
│ ╭─────╮ │ ╭────────────╮ │             │ GeekNews · 2024.12.24    │
│ │Card │ │ │ Card       │ │             │ ─────────────────────    │
│ │원문 │ │ │ 요약       │ │     =>      │ # 기사 제목              │
│ ╰─────╯ │ ╰────────────╯ │             │                          │
│         │ ╭────────────╮ │             │ ▸ 첫 번째 요약           │
│         │ │ Card       │ │             │ ▸ 두 번째 요약           │
│         │ │ 오디오     │ │             │ ▸ 세 번째 요약           │
│         │ ╰────────────╯ │             │                          │
└─────────┴────────────────┘             │ ▶ ━━━○━━━━━ 2:34  [⬇]   │
                                         └──────────────────────────┘
```



## 주요 변경사항

### 1. 레이아웃 구조 변경

**파일:** [frontend/app/page.tsx](frontend/app/page.tsx)

- Header와 InputArea를 통합하여 상단 고정 바 형태로 변경
- ContentPanel을 싱글 컬럼 중앙 정렬로 변경

**파일:** [frontend/components/content-panel.tsx](frontend/components/content-panel.tsx)

- 2컬럼 그리드(5:7) -> 싱글 컬럼 (max-width: 680px)
- SourcePanel, InsightCard, AudioPlayerCard를 순차적으로 배치

---

### 2. Header + Input 통합

**파일:** [frontend/components/header.tsx](frontend/components/header.tsx)**변경 전:**

- Header: 로고 + GitHub 링크
- InputArea: Hero 섹션 + 입력창

**변경 후:**

- 통합된 상단 바: 로고 + 입력창(compact) + 실행 버튼
- 헤드라인/서브타이틀 제거
- sticky 고정 유지

---

### 3. InputArea 심플화

**파일:** [frontend/components/input-area.tsx](frontend/components/input-area.tsx)**변경 사항:**

- Hero 스타일 제거 (gradient 배경, 큰 여백)
- inline 형태의 컴팩트한 입력창으로 변경
- 헤더에 통합될 수 있도록 리팩토링

---

### 4. SourcePanel 리팩토링 (원문 정보)

**파일:** [frontend/components/source-panel.tsx](frontend/components/source-panel.tsx)**변경 사항:**

- Card 컴포넌트 제거
- 메타 정보를 한 줄로 표시: `플랫폼 · 날짜 · 글자수`
- 제목은 크게 표시
- 상세 내용은 접기/펼치기 (기본 닫힘)
- 썸네일 이미지 제거 또는 작게 축소

---

### 5. InsightCard 리팩토링 (3줄 요약)

**파일:** [frontend/components/insight-card.tsx](frontend/components/insight-card.tsx)**변경 사항:**

- Card 컴포넌트 제거 -> 단순 section으로 변경
- CardHeader/CardTitle 제거 -> 타이포그래피로 섹션 구분
- bullet point 스타일 심플화 (CheckCircle2 아이콘 -> 단순 마커)
- AI Thinking 표시는 유지 (Collapsible)

---

### 6. AudioPlayerCard 심플화 (오디오 리포팅)

**파일:** [frontend/components/audio-player-card.tsx](frontend/components/audio-player-card.tsx)**변경 사항:**

- Card 컴포넌트 제거
- 플레이어 UI 최소화: 재생 버튼 + 프로그레스 바 + 시간 + 다운로드
- 스크립트 내용은 Collapsible로 유지 (기본 닫힘)
- 배속 조절은 숨기거나 작게 표시
- AI Thinking 표시는 유지 (Collapsible)

---

### 7. IntelligencePanel 제거

**파일:** [frontend/components/intelligence-panel.tsx](frontend/components/intelligence-panel.tsx)

- 단순 wrapper 역할만 하므로 제거
- InsightCard와 AudioPlayerCard를 ContentPanel에서 직접 렌더링

---

### 8. 스타일 조정

**파일:** [frontend/app/globals.css](frontend/app/globals.css)**추가할 스타일:**

- 섹션 구분용 divider 스타일
- 읽기 최적화된 타이포그래피 스케일
- 여백(spacing) 시스템 통일

---

## 컴포넌트 구조 (After)

```javascript
page.tsx
├── HeaderWithInput (통합)
│   ├── Logo
│   └── CompactInput
│
└── ContentPanel (싱글 컬럼)
    ├── SourceSection (접기/펼치기)
    │   ├── MetaLine (플랫폼 · 날짜)
    │   ├── Title
    │   └── CollapsibleContent
    │
    ├── Divider
    │
    ├── SummarySection
    │   ├── ThinkingCollapsible
    │   └── BulletPoints
    │
    ├── Divider
    │
    └── AudioSection
        ├── ThinkingCollapsible
        ├── MinimalPlayer
        └── ScriptCollapsible
```

---

## 구현 순서

1. globals.css에 미니멀 스타일 추가
2. Header + InputArea 통합 및 심플화
3. ContentPanel 싱글 컬럼으로 변경
4. SourcePanel 리팩토링
5. InsightCard 리팩토링