# Read-For-Me Client

**Read-For-Me**의 웹 클라이언트입니다. Next.js App Router를 사용하여 제작되었으며, PC/Mobile 반응형 UI를 제공합니다.

## 🛠 Tech Stack

- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: [shadcn/ui](https://ui.shadcn.com/)
- **State Management**: TanStack Query (React Query) [도입 예정]

## 🚀 Getting Started

이 프로젝트는 `pnpm`을 패키지 매니저로 권장합니다.

### 1. Installation

```bash
cd frontend
pnpm install
# pnpm이 없다면: npm install -g pnpm
```

### 2. Environment Setup

`.env.local` 파일을 생성하고 필요한 환경 변수를 설정합니다.

```bash
# frontend 디렉토리 내에서
touch .env.local
```

**Variables:**

```ini
NEXT_PUBLIC_API_URL="http://localhost:8000"
```

### 3. Running Development Server

```bash
pnpm run dev
```

브라우저에서 [http://localhost:3000](http://localhost:3000)을 엽니다.

## 📂 Project Structure

```
frontend/
├── app/                # Next.js App Router 페이지 및 레이아웃
├── components/         # React 컴포넌트
│   ├── ui/             # shadcn/ui 기본 컴포넌트 (Button, Card 등)
│   └── ...             # 비즈니스 로직 포함 컴포넌트 (AudioPlayer 등)
├── hooks/              # Custom Hooks
├── lib/                # 유틸리티 함수
└── public/             # 정적 파일 (이미지, 아이콘)
```

## 🎨 UI Components

주요 비즈니스 컴포넌트는 다음과 같습니다:

- **InputArea**: URL 입력 및 유효성 검사
- **SourcePanel**: 원문 기사 미리보기 (Left Column)
- **InsightCard**: 3줄 요약 표시 (Right Column)
- **AudioPlayerCard**: TTS 오디오 재생 및 제어

## ✅ Technical TODOs

> 전체 기능 구현 현황은 `../docs/TODO.md`를 참고하세요.

- [ ] TanStack Query 설치 및 설정
- [ ] 백엔드 API 연동 (크롤링, 요약, 오디오)
- [ ] 오디오 플레이어 Waveform 시각화 고도화
- [ ] 모바일 뷰에서의 스크롤 및 레이아웃 UX 개선
