"""
Storage Service

환경변수로 전환 가능한 Storage 추상화 레이어입니다.
- STORAGE_BACKEND=local: 로컬 파일시스템
- STORAGE_BACKEND=gcs: Google Cloud Storage

경로 구조:
    users/{user_id}/crawled/{article_id}_{timestamp}.json
    users/{user_id}/summary/{article_id}_{timestamp}.json
    users/{user_id}/audio/{article_id}_{timestamp}.json
    users/{user_id}/audio/{article_id}.mp3
"""

import fnmatch
import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Protocol, runtime_checkable

from google.auth import default as get_default_credentials
from google.auth.transport import requests as auth_requests
from google.cloud import storage as gcs
from google.oauth2 import service_account
from loguru import logger

from app.core.config import settings

# 기본 로컬 데이터 디렉토리
DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _get_gcs_credentials() -> service_account.Credentials | None:
    """
    GCS용 서비스 계정 자격 증명을 가져옵니다.

    환경변수 GOOGLE_APPLICATION_CREDENTIALS가 설정되어 있으면 해당 파일에서,
    없으면 기본 위치(~/readforme-key.json)에서 자격 증명을 로드합니다.

    Returns:
        service_account.Credentials 또는 None (ADC 사용 시)
    """
    # 1. 환경변수에서 키 파일 경로 확인
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    # 2. 환경변수가 없으면 기본 경로 사용
    if not credentials_path:
        default_key_path = Path.home() / "readforme-key.json"
        if default_key_path.exists():
            credentials_path = str(default_key_path)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            logger.debug(f"GCS: 기본 키 파일 사용: {credentials_path}")

    # 3. 키 파일이 있으면 자격 증명 생성
    if credentials_path and Path(credentials_path).exists():
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return credentials

    # 4. 키 파일이 없으면 None 반환 (ADC 자동 감지 사용)
    logger.warning(
        "GCS: 서비스 계정 키 파일을 찾을 수 없습니다. ADC 자동 감지를 시도합니다."
    )
    return None


@runtime_checkable
class StorageService(Protocol):
    """Storage 서비스 프로토콜 (인터페이스)"""

    async def save_json(self, path: str, data: dict) -> str:
        """JSON 데이터를 저장합니다.

        Args:
            path: 저장 경로 (예: users/default/crawled/article_123.json)
            data: 저장할 딕셔너리 데이터

        Returns:
            저장된 전체 경로 (로컬: 절대경로, GCS: gs:// URI)
        """
        ...

    async def load_json(self, path: str) -> dict | None:
        """JSON 데이터를 로드합니다.

        Args:
            path: 로드할 경로

        Returns:
            로드된 딕셔너리 데이터 (없으면 None)
        """
        ...

    async def save_bytes(
        self, path: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """바이너리 데이터를 저장합니다.

        Args:
            path: 저장 경로
            data: 저장할 바이트 데이터
            content_type: MIME 타입

        Returns:
            저장된 전체 경로
        """
        ...

    async def load_bytes(self, path: str) -> bytes | None:
        """바이너리 데이터를 로드합니다.

        Args:
            path: 로드할 경로

        Returns:
            로드된 바이트 데이터 (없으면 None)
        """
        ...

    async def list_files(self, prefix: str, pattern: str = "*") -> list[str]:
        """특정 prefix 하위의 파일 목록을 반환합니다.

        Args:
            prefix: 탐색할 경로 prefix (예: users/default/audio/)
            pattern: 파일 패턴 (예: "article_*.json")

        Returns:
            매칭된 파일 경로 리스트
        """
        ...

    async def get_download_url(self, path: str, expiry_minutes: int = 60) -> str:
        """파일 다운로드 URL을 반환합니다.

        Args:
            path: 파일 경로
            expiry_minutes: URL 만료 시간 (분, GCS Signed URL용)

        Returns:
            다운로드 가능한 URL (로컬: file://, GCS: signed URL)
        """
        ...

    def exists(self, path: str) -> bool:
        """파일 존재 여부를 확인합니다.

        Args:
            path: 확인할 경로

        Returns:
            존재하면 True
        """
        ...

    def get_local_path(self, path: str) -> Path | None:
        """로컬 파일 경로를 반환합니다 (로컬 스토리지 전용).

        Args:
            path: 파일 경로

        Returns:
            로컬 Path 객체 (GCS인 경우 None)
        """
        ...


class LocalStorageService:
    """로컬 파일시스템 기반 스토리지 서비스"""

    def __init__(self, base_dir: Path | None = None):
        """
        Args:
            base_dir: 기본 데이터 디렉토리 (None이면 backend/data/)
        """
        self.base_dir = base_dir or DEFAULT_DATA_DIR
        logger.info(f"LocalStorageService 초기화: base_dir={self.base_dir}")

    def _resolve_path(self, path: str) -> Path:
        """상대 경로를 절대 경로로 변환합니다."""
        return self.base_dir / path

    async def save_json(self, path: str, data: dict) -> str:
        """JSON 데이터를 로컬 파일시스템에 저장합니다."""
        full_path = self._resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.debug(f"LocalStorage: JSON 저장 완료: {full_path}")
        return str(full_path)

    async def load_json(self, path: str) -> dict | None:
        """JSON 데이터를 로컬 파일시스템에서 로드합니다."""
        full_path = self._resolve_path(path)

        if not full_path.exists():
            return None

        try:
            with open(full_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"LocalStorage: JSON 로드 실패: {full_path}, error={e}")
            return None

    async def save_bytes(
        self, path: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """바이너리 데이터를 로컬 파일시스템에 저장합니다."""
        full_path = self._resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "wb") as f:
            f.write(data)

        logger.debug(
            f"LocalStorage: 바이너리 저장 완료: {full_path} ({len(data)} bytes)"
        )
        return str(full_path)

    async def load_bytes(self, path: str) -> bytes | None:
        """바이너리 데이터를 로컬 파일시스템에서 로드합니다."""
        full_path = self._resolve_path(path)

        if not full_path.exists():
            return None

        try:
            with open(full_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"LocalStorage: 바이너리 로드 실패: {full_path}, error={e}")
            return None

    async def list_files(self, prefix: str, pattern: str = "*") -> list[str]:
        """특정 prefix 하위의 파일 목록을 반환합니다."""
        base_path = self._resolve_path(prefix)

        if not base_path.exists():
            return []

        # glob 패턴으로 파일 검색
        matched_files = []
        for file_path in base_path.iterdir():
            if file_path.is_file() and fnmatch.fnmatch(file_path.name, pattern):
                # 상대 경로로 반환
                relative_path = str(file_path.relative_to(self.base_dir))
                matched_files.append(relative_path)

        return matched_files

    async def get_download_url(self, path: str, expiry_minutes: int = 60) -> str:
        """로컬 파일 경로를 file:// URL로 반환합니다."""
        full_path = self._resolve_path(path)
        return f"file://{full_path}"

    def exists(self, path: str) -> bool:
        """파일 존재 여부를 확인합니다."""
        full_path = self._resolve_path(path)
        return full_path.exists()

    def get_local_path(self, path: str) -> Path | None:
        """로컬 파일 경로를 반환합니다."""
        return self._resolve_path(path)


class GCSStorageService:
    """Google Cloud Storage 기반 스토리지 서비스"""

    def __init__(
        self,
        bucket_name: str | None = None,
        project_id: str | None = None,
    ):
        """
        Args:
            bucket_name: GCS 버킷 이름 (None이면 settings에서 로드)
            project_id: GCP 프로젝트 ID (None이면 settings에서 로드)
        """
        self.bucket_name = bucket_name or settings.GCS_BUCKET_NAME
        self.project_id = project_id or settings.GCS_PROJECT_ID

        # GCS 클라이언트 초기화
        credentials = _get_gcs_credentials()
        self.client = gcs.Client(
            project=self.project_id,
            credentials=credentials,
        )
        self.bucket = self.client.bucket(self.bucket_name)

        logger.info(
            f"GCSStorageService 초기화: bucket={self.bucket_name}, "
            f"project={self.project_id}"
        )

    async def save_json(self, path: str, data: dict) -> str:
        """JSON 데이터를 GCS에 저장합니다."""
        blob = self.bucket.blob(path)
        json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        blob.upload_from_string(json_str, content_type="application/json")

        uri = f"gs://{self.bucket_name}/{path}"
        logger.debug(f"GCS: JSON 저장 완료: {uri}")
        return uri

    async def load_json(self, path: str) -> dict | None:
        """JSON 데이터를 GCS에서 로드합니다."""
        blob = self.bucket.blob(path)

        if not blob.exists():
            return None

        try:
            json_str = blob.download_as_text()
            return json.loads(json_str)
        except Exception as e:
            logger.error(
                f"GCS: JSON 로드 실패: gs://{self.bucket_name}/{path}, error={e}"
            )
            return None

    async def save_bytes(
        self, path: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """바이너리 데이터를 GCS에 저장합니다."""
        blob = self.bucket.blob(path)
        blob.upload_from_string(data, content_type=content_type)

        uri = f"gs://{self.bucket_name}/{path}"
        logger.debug(f"GCS: 바이너리 저장 완료: {uri} ({len(data)} bytes)")
        return uri

    async def load_bytes(self, path: str) -> bytes | None:
        """바이너리 데이터를 GCS에서 로드합니다."""
        blob = self.bucket.blob(path)

        if not blob.exists():
            return None

        try:
            return blob.download_as_bytes()
        except Exception as e:
            logger.error(
                f"GCS: 바이너리 로드 실패: gs://{self.bucket_name}/{path}, error={e}"
            )
            return None

    async def list_files(self, prefix: str, pattern: str = "*") -> list[str]:
        """특정 prefix 하위의 파일 목록을 반환합니다."""
        # prefix가 /로 끝나지 않으면 추가
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"

        blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)

        matched_files = []
        for blob in blobs:
            # 디렉토리가 아닌 파일만
            if not blob.name.endswith("/"):
                filename = blob.name.split("/")[-1]
                if fnmatch.fnmatch(filename, pattern):
                    matched_files.append(blob.name)

        return matched_files

    async def get_download_url(self, path: str, expiry_minutes: int = 60) -> str:
        """
        IAM Credentials API를 사용하여 GCS Signed URL을 생성합니다.

        Cloud Run 환경에서는 서비스 계정 키 파일 없이도 IAM API를 통해
        Signed URL을 생성할 수 있습니다.

        요구 사항:
        - 서비스 계정에 roles/iam.serviceAccountTokenCreator 권한 필요
        """
        blob = self.bucket.blob(path)

        # ADC에서 기본 자격 증명 가져오기
        credentials, project = get_default_credentials()

        # 토큰 갱신 (만료된 경우 대비)
        auth_request = auth_requests.Request()
        credentials.refresh(auth_request)

        # service_account_email과 access_token을 제공하면
        # IAM Credentials API를 사용하여 서명 생성 (키 파일 불필요)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiry_minutes),
            method="GET",
            service_account_email=credentials.service_account_email,
            access_token=credentials.token,
        )

        logger.debug(f"GCS: Signed URL 생성 (IAM): {path} (만료: {expiry_minutes}분)")
        return url

    def exists(self, path: str) -> bool:
        """파일 존재 여부를 확인합니다."""
        blob = self.bucket.blob(path)
        return blob.exists()

    def get_local_path(self, path: str) -> Path | None:
        """GCS는 로컬 경로가 없으므로 None을 반환합니다."""
        return None


# 싱글톤 인스턴스
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """
    Storage 서비스 싱글톤 인스턴스를 가져옵니다.

    STORAGE_BACKEND 환경변수에 따라 적절한 서비스를 반환합니다:
    - "local": LocalStorageService
    - "gcs": GCSStorageService

    Returns:
        StorageService 구현체
    """
    global _storage_service

    if _storage_service is None:
        backend = settings.STORAGE_BACKEND.lower()

        if backend == "gcs":
            _storage_service = GCSStorageService()
        else:
            # 기본값: local
            _storage_service = LocalStorageService()

        logger.info(f"StorageService 초기화 완료: backend={backend}")

    return _storage_service


def is_gcs_storage() -> bool:
    """현재 스토리지 백엔드가 GCS인지 확인합니다."""
    return settings.STORAGE_BACKEND.lower() == "gcs"
