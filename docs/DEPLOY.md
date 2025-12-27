# 배포 가이드 (Deployment Guide)

> **작성일:** 2025-12-26
> **대상:** Read-For-Me 프로젝트의 GCP Cloud Run + Vercel 배포

---

## 📋 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [사전 준비](#2-사전-준비)
3. [Backend 배포 (Cloud Run)](#3-backend-배포-cloud-run)
4. [Frontend 배포 (Vercel)](#4-frontend-배포-vercel)
5. [환경변수 설정](#5-환경변수-설정)
6. [트러블슈팅](#6-트러블슈팅)

---

## 1. 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                     Production Architecture                      │
│                                                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│  │   Vercel    │     │  Cloud Run  │     │   Phoenix   │        │
│  │  Frontend   │────▶│   Backend   │────▶│   LLMOps    │        │
│  │  (Next.js)  │     │  (FastAPI)  │     │ (선택사항)   │        │
│  └─────────────┘     └──────┬──────┘     └─────────────┘        │
│                             │                                    │
│         ┌───────────────────┼───────────────────┐               │
│         ▼                   ▼                   ▼               │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│  │   Vertex    │     │ GCP Storage │     │   OpenAI    │        │
│  │  AI (LLM)   │     │   (data)    │     │   (TTS)     │        │
│  └─────────────┘     └─────────────┘     └─────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 사전 준비

### 2.1 필수 도구 설치

```bash
# Google Cloud CLI
brew install google-cloud-sdk

# 로그인 및 프로젝트 설정
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 2.2 GCP 서비스 활성화

```bash
# 필요한 API 활성화
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    storage.googleapis.com \
    aiplatform.googleapis.com
```

### 2.3 환경변수 준비

필요한 API 키 및 설정값:

| 환경변수               | 설명                  | 필수             |
| ---------------------- | --------------------- | ---------------- |
| `OPENAI_API_KEY`       | OpenAI API 키 (TTS용) | ✅               |
| `BACKEND_CORS_ORIGINS` | 프론트엔드 URL        | ✅               |
| `GCS_BUCKET_NAME`      | GCS 버킷 이름         | ✅ (GCS 사용 시) |
| `GCS_PROJECT_ID`       | GCP 프로젝트 ID       | ✅ (GCS 사용 시) |

---

## 3. Backend 배포 (Cloud Run)

### 3.1 로컬 Docker 빌드 테스트

```bash
# backend 디렉토리로 이동
cd backend

# Docker 이미지 빌드
docker build -t read-for-me-backend .

# 로컬에서 테스트 실행
docker run -p 8080:8080 \
    -e PROJECT_NAME=Read-For-Me \
    -e VERSION=0.1.0 \
    -e API_V1_STR=/api/v1 \
    -e 'BACKEND_CORS_ORIGINS=["http://localhost:3000"]' \
    -e OPENAI_API_KEY=***REMOVED*** \
    -e STORAGE_BACKEND=gcs \
    read-for-me-backend

# 헬스체크
curl http://localhost:8080/health
```

### 3.2 GCP Artifact Registry 설정

```bash
# Artifact Registry 리포지토리 생성 (최초 1회)
gcloud artifacts repositories create read-for-me \
    --repository-format=docker \
    --location=asia-northeast3 \
    --description="Read-For-Me Docker images"

# Docker 인증 설정
gcloud auth configure-docker asia-northeast3-docker.pkg.dev
```

### 3.3 이미지 빌드 및 푸시

```bash
# 프로젝트 ID 변수 설정
export PROJECT_ID=$(gcloud config get-value project)
export REGION=asia-northeast3
export IMAGE_NAME=asia-northeast3-docker.pkg.dev/${PROJECT_ID}/read-for-me/backend

# Cloud Build로 빌드 및 푸시
gcloud builds submit --tag ${IMAGE_NAME}:latest ./backend  # 여기까지 함

# 또는 로컬에서 빌드 후 푸시
docker build -t ${IMAGE_NAME}:latest ./backend
docker push ${IMAGE_NAME}:latest
```

### 3.4 Cloud Run 배포

```bash
# Cloud Run 서비스 배포
gcloud run deploy read-for-me-backend \
    --image ${IMAGE_NAME}:latest \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 10 \
    --set-env-vars "PROJECT_NAME=Read-For-Me" \
    --set-env-vars "VERSION=0.1.0" \
    --set-env-vars "API_V1_STR=/api/v1" \
    --set-env-vars "STORAGE_BACKEND=gcs" \
    --set-env-vars "GCS_BUCKET_NAME=read-for-me-data" \
    --set-env-vars "GCS_PROJECT_ID=${PROJECT_ID}" \
    --set-env-vars "PHOENIX_ENABLED=true"

# 민감한 환경변수는 Secret Manager 사용 권장
gcloud run services update read-for-me-backend \
    --region ${REGION} \
    --set-secrets "OPENAI_API_KEY=openai-api-key:latest"
```

### 3.5 CORS 설정 업데이트

프론트엔드 배포 후 CORS origin 업데이트:

```bash
gcloud run services update read-for-me-backend \
    --region ${REGION} \
    --update-env-vars "BACKEND_CORS_ORIGINS=https://your-app.vercel.app"
```

### 3.6 배포 확인

```bash
# 서비스 URL 확인
gcloud run services describe read-for-me-backend \
    --region ${REGION} \
    --format 'value(status.url)'

# 헬스체크
curl $(gcloud run services describe read-for-me-backend --region ${REGION} --format 'value(status.url)')/health
```

---

## 4. Frontend 배포 (Vercel)

### 4.1 Vercel 프로젝트 설정

1. [Vercel](https://vercel.com)에 로그인
2. "New Project" → GitHub 리포지토리 연결
3. **Root Directory**: `frontend` 선택
4. **Framework Preset**: Next.js (자동 감지)

### 4.2 환경변수 설정

Vercel 대시보드 → Settings → Environment Variables:

| 변수명                | 값                             | 환경        |
| --------------------- | ------------------------------ | ----------- |
| `NEXT_PUBLIC_API_URL` | `https://your-backend.run.app` | Production  |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000`        | Development |

### 4.3 배포

```bash
# Vercel CLI 사용 시
cd frontend
npx vercel --prod

# 또는 GitHub push로 자동 배포 (main 브랜치)
git push origin main
```

### 4.4 도메인 설정 (선택)

Vercel 대시보드 → Settings → Domains에서 커스텀 도메인 추가

---

## 5. 환경변수 설정

### 5.1 Backend 환경변수 전체 목록

| 환경변수               | 설명              | 기본값      | 프로덕션 권장값        |
| ---------------------- | ----------------- | ----------- | ---------------------- |
| `PROJECT_NAME`         | 프로젝트 이름     | Read-For-Me | Read-For-Me            |
| `VERSION`              | API 버전          | 0.1.0       | 0.1.0                  |
| `API_V1_STR`           | API 경로 프리픽스 | /api/v1     | /api/v1                |
| `BACKEND_CORS_ORIGINS` | 허용 Origin       | -           | Vercel URL             |
| `OPENAI_API_KEY`       | OpenAI API 키     | -           | Secret Manager         |
| `STORAGE_BACKEND`      | 스토리지 타입     | local       | gcs                    |
| `GCS_BUCKET_NAME`      | GCS 버킷명        | -           | read-for-me-data       |
| `GCS_PROJECT_ID`       | GCP 프로젝트 ID   | -           | your-project-id        |
| `PHOENIX_ENABLED`      | Phoenix 활성화    | true        | false (또는 별도 배포) |
| `DEBUG_CORS`           | CORS 디버깅       | false       | false                  |

### 5.2 Secret Manager 설정

민감한 API 키는 Secret Manager 사용:

```bash
# 시크릿 생성
echo -n "sk-your-openai-key" | gcloud secrets create openai-api-key \
    --data-file=-

# Cloud Run 서비스 계정에 권한 부여
gcloud secrets add-iam-policy-binding openai-api-key \
    --member="serviceAccount:${PROJECT_ID}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

---

## 6. 트러블슈팅

### 6.1 Cold Start 지연

Cloud Run의 cold start로 인한 첫 요청 지연 (5-10초):

```bash
# 최소 인스턴스 1개 유지 (비용 발생)
gcloud run services update read-for-me-backend \
    --region ${REGION} \
    --min-instances 1
```

### 6.2 CORS 에러

```
Access to fetch at 'https://backend...' from origin 'https://frontend...'
has been blocked by CORS policy
```

→ `BACKEND_CORS_ORIGINS`에 프론트엔드 URL이 정확히 포함되어 있는지 확인 (trailing slash 주의)

### 6.3 Playwright 브라우저 에러

```
Browser not found
```

→ Dockerfile에서 Playwright 브라우저 설치 확인:

```dockerfile
RUN playwright install chromium
```

### 6.4 GCS 권한 에러

```
403 Forbidden: Access denied
```

→ Cloud Run 서비스 계정에 Storage 권한 부여:

```bash
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${PROJECT_ID}-compute@developer.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"
```

### 6.5 메모리 부족

```
Container exceeded memory limit
```

→ Cloud Run 메모리 증가:

```bash
gcloud run services update read-for-me-backend \
    --region ${REGION} \
    --memory 2Gi
```

---

## 부록: 빠른 배포 스크립트

```bash
#!/bin/bash
# deploy.sh - 원클릭 배포 스크립트

set -e

export PROJECT_ID=$(gcloud config get-value project)
export REGION=asia-northeast3
export IMAGE_NAME=asia-northeast3-docker.pkg.dev/${PROJECT_ID}/read-for-me/backend

echo "🔨 Building Docker image..."
gcloud builds submit --tag ${IMAGE_NAME}:latest ./backend

echo "🚀 Deploying to Cloud Run..."
gcloud run deploy read-for-me-backend \
    --image ${IMAGE_NAME}:latest \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated

echo "✅ Deployment complete!"
echo "URL: $(gcloud run services describe read-for-me-backend --region ${REGION} --format 'value(status.url)')"
```

---

## 변경 이력

| 날짜       | 버전 | 변경 내용             |
| ---------- | ---- | --------------------- |
| 2025-12-26 | 1.0  | 초기 배포 가이드 작성 |
