# Data Crawling & Archiving Package

현재 **GeekNews**, **Medium** 웹 크롤링과 **Naver Mail** 기반의 뉴스레터 아카이빙을 지원합니다.

## 📁 프로젝트 구조

```text
data_crawling/src
├── __init__.py                    # 패키지 초기화
├── base_crawler.py                # 기본 추상 크롤러 클래스
├── geeknews_base.py               # GeekNews 전용 기본 클래스
├── geeknews_weekly_crawler.py     # Weekly 뉴스레터 크롤러
├── geeknews_article_crawler.py    # 개별 아티클 크롤러
├── medium_crawler.py              # Medium 블로그 크롤러
├── naver_email_archiver.py        # Naver 이메일 뉴스레터 아카이버 (NEW)
├── requirements.txt               # 의존성
└── README.md                      # 이 파일
```

## 🏗️ 아키텍처

### Web Crawlers (OOP Based)

```text
                    BaseCrawler (ABC)
                         │
           ┌─────────────┴─────────────┐
           │                           │
  GeekNewsBaseCrawler             MediumCrawler
      /           \
     /             \
WeeklyCrawler   ArticleCrawler
```

### Email Archiver (Standalone)

  * **NaverEmailArchiver**: IMAP을 사용하여 특정 뉴스레터 메일을 필터링 및 텍스트로 백업합니다.

### 클래스 설명

| 클래스 | 유형 | 설명 |
|--------|------|------|
| `BaseCrawler` | Abstract | 모든 웹 크롤러의 기본 클래스 (HTTP 요청, 파싱, 저장) |
| `GeekNewsWeeklyCrawler` | Web | GeekNews Weekly 뉴스레터 페이지 크롤러 |
| `GeekNewsArticleCrawler` | Web | GeekNews 개별 아티클 및 댓글 크롤러 |
| `MediumCrawler` | Web | Medium 블로그 아티클 파싱 및 노이즈 제거 크롤러 |
| `NaverEmailArchiver` | Email | Naver 메일함에서 특정 뉴스레터를 수집하여 저장 |

## 🚀 설치 및 설정

### 1\. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2\. 환경 변수 설정 (.env)

이메일 아카이버를 사용하기 위해 프로젝트 루트에 `.env` 파일을 생성하고 네이버 계정 정보를 입력해야 합니다.

```env
# .env file
NAVER_USER="your_naver_id"
NAVER_PASS="your_naver_password"
```

> **Note**: 2단계 인증을 사용하는 경우, 네이버 계정 설정에서 '애플리케이션 비밀번호'를 생성하여 `NAVER_PASS`에 입력해야 합니다.

## 📖 사용법 (CLI)

### 📧 Naver Email Archiver

지정된 뉴스레터(Turing Post, The Sequence 등)를 백업합니다.

```bash
# 1. 모든 타겟 메일함 검사 (기본)
python src/naver_email_archiver.py

# 2. 특정 날짜의 메일만 수집 (YYYYMMDD)
python src/naver_email_archiver.py --date 20251127

# 3. 읽지 않은 메일만 수집 후 '읽음' 처리
python src/naver_email_archiver.py --status unread

# 4. 복합 필터링
python src/naver_email_archiver.py -d 20251127 -s unread
```

### 🌐 Web Crawlers

#### Medium 크롤러

```bash
# 기본 사용
python src/medium_crawler.py {url}

# 출력 디렉토리 지정
python src/medium_crawler.py {url} --output ./medium_docs
```

#### GeekNews 크롤러

```bash
# Weekly 크롤러
python src/geeknews_weekly_crawler.py {url}

# Article 크롤러 (댓글 포함)
python src/geeknews_article_crawler.py {url} --comments
```

## 📄 출력 형식 예시

### Email Archive 출력

저장 경로: `./email_archives/{Category}/[YYYYMMDD] {Title}.txt`

```text
Subject: [The Sequence] Supercharging LLMs with GraphRAG
From: thesequence@substack.com
To: my_email@naver.com
Date: 2025-11-27 09:00:00+09:00
----------------------------------------

(Content Body Cleaned via BeautifulSoup)
...
```

### Medium 출력

```text
============================================================
Title: Building a Production-Grade Enterprise AI Platform with vLLM
URL: https://medium.com/...
Platform: medium
...
============================================================
...
```

## 🔧 타겟 뉴스레터 수정

`src/naver_email_archiver.py` 상단의 `TARGET_SOURCES` 딕셔너리를 수정하여 수집할 이메일 소스를 변경할 수 있습니다.

```python
TARGET_SOURCES = {
    "Category/FolderName": "sender@email.com",
    # 예시
    "Tech/Newsletter": "newsletter@tech.com",
}
```

## 📝 라이선스

MIT License