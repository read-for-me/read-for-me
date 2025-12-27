"""
Naver Email Archiver (Filter Support)

- 기본: 지정된 발신자의 '모든' 메일을 확인하여 백업합니다. (이미 파일이 있으면 건너뜀)
- 옵션: 날짜(--date) 및 읽음 상태(--status)로 필터링할 수 있습니다.
"""

import os
import re
import argparse
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv
from imap_tools import MailBox, AND
from bs4 import BeautifulSoup
from loguru import logger

from gcs_handler import GCSHandler

# ==========================================
# 1. 수집 타겟 설정
# ==========================================
TARGET_SOURCES = {
    "AI/Turing_post": "turingpost@mail.beehiiv.com",
    "AI/The_sequence": "thesequence@substack.com",
    "UIUX": "newsletter@dbdlab.io",
    "Insight": "miraklelab@mk.co.kr",
}

class NaverEmailArchiver:
    IMAP_SERVER = "imap.naver.com"

    GCS_PROJECT_ID = "gen-lang-client-0039052673"
    GCS_BUCKET_NAME = "parallel_audio_etl_data"

    def __init__(self, output_dir: str = "./email_archives", save_local: bool = True, save_gcs: bool = False):
        load_dotenv()
        self.output_dir = Path(output_dir)
        self.save_local = save_local
        self.save_gcs = save_gcs
        
        self.user = os.getenv("NAVER_USER")
        self.password = os.getenv("NAVER_PASS")

        if not self.user or not self.password:
            raise ValueError("❌ 계정 정보가 없습니다. .env 파일 설정을 확인해주세요.")

        self.gcs_handler = None
        if self.save_gcs:
            self.gcs_handler = GCSHandler(self.GCS_PROJECT_ID, self.GCS_BUCKET_NAME)

    def run(self, target_date: str = None, status: str = 'all'):
        """
        이메일 수집 실행
        :param target_date: 날짜 필터 (YYYYMMDD)
        :param status: 읽음 상태 필터 ('all', 'unread', 'read')
        """
        # 1. 날짜 파싱
        parsed_date = None
        if target_date:
            try:
                clean_date = re.sub(r'[^0-9]', '', target_date)
                parsed_date = datetime.strptime(clean_date, "%Y%m%d").date()
                date_log = f"Date={parsed_date}"
            except ValueError:
                logger.error("❌ 날짜 형식이 잘못되었습니다.")
                return
        else:
            date_log = "Date=All"

        logger.info(f"🚀 Starting Archiver: {date_log}, Status={status.upper()}")
        logger.info(f"Connecting to {self.IMAP_SERVER} as {self.user}...")

        try:
            with MailBox(self.IMAP_SERVER).login(self.user, self.password) as mailbox:
                for category_path, sender_email in TARGET_SOURCES.items():
                    self._process_sender(mailbox, category_path, sender_email, parsed_date, status)
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")

    def _process_sender(self, mailbox, category_path: str, sender_email: str, target_date: date, status: str):
        """개별 발신자 처리 로직"""
        
        # 2. 검색 조건(Criteria) 동적 생성
        criteria_kwargs = {'from_': sender_email}
        
        # 날짜 조건 추가
        if target_date:
            criteria_kwargs['date'] = target_date

        # 읽음/안읽음 상태 조건 및 마킹 여부 결정
        mark_seen_flag = False  # 기본적으로 서버 상태를 건드리지 않음 (Safe)

        if status == 'unread':
            criteria_kwargs['seen'] = False
            mark_seen_flag = True  # '안 읽은 것'을 가져올 때는 수집 후 '읽음' 처리 (Archiving flow)
        elif status == 'read':
            criteria_kwargs['seen'] = True
        # status == 'all'인 경우 'seen' 조건을 넣지 않음 (모두 가져옴)

        # 3. IMAP 검색 수행
        # imap_tools의 AND는 키워드 인자로 조건을 받습니다.
        criteria = AND(**criteria_kwargs)
        
        logger.info(f"🔎 Searching: [{category_path}] {sender_email} (Status={status})")

        try:
            msgs = list(mailbox.fetch(criteria, mark_seen=mark_seen_flag))
        except Exception as e:
            logger.error(f"   └─ ❌ Search failed: {e}")
            return
        
        if not msgs:
            logger.info(f"   └─ 📭 Result: 0 emails found.")
            return

        logger.info(f"   └─ ✅ Found {len(msgs)} emails. Saving...")

        # 4. 저장 수행
        save_dir = self.output_dir / category_path
        save_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        skip_count = 0
        for msg in msgs:
            saved = self._save_to_txt(msg, save_dir)
            if saved:
                count += 1
            else:
                skip_count += 1
        
        # 결과 로그
        log_msg = f"   └─ 🎉 Saved: {count}"
        if skip_count > 0:
            log_msg += f" (Skipped {skip_count} duplicates)"
        logger.info(log_msg)

    def _save_to_txt(self, msg, save_dir: Path) -> bool:
        """이메일을 저장합니다 (Local & GCS)."""
        try:
            date_str = msg.date.strftime("%Y%m%d")
            safe_subject = self._sanitize_filename(msg.subject)
            filename = f"[{date_str}] {safe_subject}.txt"
            
            # 메일 본문 구성
            body_content = self._extract_clean_body(msg)
            full_text = (
                f"Subject: {msg.subject}\n"
                f"From: {msg.from_}\n"
                f"To: {msg.to}\n"
                f"Date: {msg.date}\n"
                f"{'-' * 40}\n\n"
                f"{body_content}"
            )

            # 성공 여부 추적 (하나라도 새로 저장되면 True)
            action_taken = False

            # 1. Local Save Check & Write
            if self.save_local:
                filepath = save_dir / filename
                if filepath.exists():
                    # 로컬 중복 시 로그는 선택사항 (너무 많을 수 있음)
                    # logger.info(f"   └─ ⏭️  Skipped local (Duplicate): {filename}")
                    pass 
                else:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(full_text)
                    action_taken = True

            # 2. GCS Upload Check & Write
            if self.save_gcs and self.gcs_handler:
                try:
                    relative_path = save_dir.relative_to(self.output_dir)
                    gcs_path = f"email_archives/{relative_path}/{filename}"
                except ValueError:
                    gcs_path = f"email_archives/misc/{filename}"

                # GCS 중복 체크
                if self.gcs_handler.file_exists(gcs_path):
                    #  logger.info(f"   └─ ⏭️  Skipped GCS (Duplicate): {gcs_path}")
                     pass
                else:
                    self.gcs_handler.upload_string(full_text, gcs_path)
                    action_taken = True

            return action_taken

        except Exception as e:
            logger.error(f"   └─ ❌ Save failed: {e}")
            return False

    def _extract_clean_body(self, msg) -> str:
        text = ""
        if msg.html:
            soup = BeautifulSoup(msg.html, "html.parser")
            for tag in soup(["script", "style", "head", "meta", "iframe"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
        else:
            text = msg.text or ""
        return re.sub(r'\n{3,}', '\n\n', text).strip()

    @staticmethod
    def _sanitize_filename(text: str) -> str:
        text = re.sub(r'[\\/*?:"<>|]', "", text)
        text = text.replace('\n', ' ').replace('\r', '')
        return text.strip()[:100]

def main():
    parser = argparse.ArgumentParser(description="Naver Email Archiver")
    parser.add_argument("--date", "-d", help="Target date (YYYYMMDD)")
    parser.add_argument("--status", "-s", choices=['all', 'unread', 'read'], default='all')
    
    # 저장 옵션
    parser.add_argument("--gcs", action="store_true", help="Upload to Google Cloud Storage")
    parser.add_argument("--no-local", action="store_true", help="Skip local storage")
    
    args = parser.parse_args()
    
    # 로거 설정
    logger.remove()
    logger.add(lambda msg: print(msg), level="INFO", format="{message}")

    # 옵션 처리
    save_local = not args.no_local
    
    archiver = NaverEmailArchiver(save_local=save_local, save_gcs=args.gcs)
    archiver.run(target_date=args.date, status=args.status)

if __name__ == "__main__":
    main()