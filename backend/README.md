# Read-For-Me Backend API

**Read-For-Me**의 백엔드 서비스입니다. Python FastAPI를 기반으로 구축되었으며, 웹 크롤링, 텍스트 요약(LLM), 오디오 생성(TTS) 파이프라인을 비동기로 처리합니다.

## 🛠 Tech Stack

- **Framework**: FastAPI
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (고성능 Python 패키지 관리자)
- **Asynchronous**: `asyncio`, `uvicorn`
- **AI/Crawling**: TBD. 고려 중인 API는 `Google Gemini Pro`, `OpenAI TTS`, `BeautifulSoup4`.

## 🚀 Getting Started

이 프로젝트는 `uv`를 사용하여 의존성을 관리합니다.

### 1. Prerequisites

- Python 3.11+
- `uv` 설치 필요:
  ```bash
  # macOS/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### 2. Installation

의존성을 설치하고 가상환경을 동기화합니다.

```bash
cd backend
uv sync
```

### 3. Environment Setup

`.env` 파일을 생성하고 필요한 환경 변수를 설정합니다.

```bash
# backend 디렉토리 내에서
touch .env
```

**Required Environment Variables (`.env`):**

```ini
PROJECT_NAME="Read For Me"
VERSION="0.1.0"
API_V1_STR="/api/v1"
BACKEND_CORS_ORIGINS=["http://localhost:3000"]

# AI Keys
GEMINI_API_KEY="your-gemini-api-key"
OPENAI_API_KEY="your-openai-api-key"
```

### 4. Running the Server

개발 서버를 실행합니다. (Hot Reload 지원)

```bash
uv run uvicorn app.main:app --reload
```

- **API Server**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📂 Project Structure

```
backend/
├── app/
│   ├── api/            # API 라우트 핸들러 (v1/)
│   ├── core/           # 설정(Config) 및 공통 유틸리티
│   ├── main.py         # FastAPI 앱 진입점 (Entry Point)
│   └── services/       # 비즈니스 로직 (Crawling, Summary, Audio) [예정]
├── pyproject.toml      # 의존성 및 프로젝트 설정
└── uv.lock             # 의존성 버전 잠금 파일
```

## ✅ Technical TODOs

> 전체 프로젝트 로드맵은 `../docs/TODO.md`를 참고하세요.

- [ ] 크롤러 팩토리 패턴 구현 (GeekNews, General 등)
- [ ] (TBD) Gemini API 연동 (요약/대본 생성)
- [ ] (TBD) OpenAI TTS 연동 or Gemini API 연동 및 비동기 처리
