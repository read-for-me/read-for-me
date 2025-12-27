import os
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger

class GCSHandler:
    def __init__(self, project_id: str, bucket_name: str):
        self.project_id = project_id
        self.bucket_name = bucket_name
        
        # 인증은 GOOGLE_APPLICATION_CREDENTIALS 환경변수 또는 gcloud auth application-default login 사용
        self.client = storage.Client(project=self.project_id)
        self.bucket = self.client.bucket(self.bucket_name)

    def file_exists(self, blob_name: str) -> bool:
        """
        GCS 버킷에 해당 파일이 존재하는지 확인합니다.
        """
        blob = self.bucket.blob(blob_name)
        return blob.exists()

    @retry(
        stop=stop_after_attempt(3),  # 최대 3회 재시도
        wait=wait_exponential(multiplier=1, min=2, max=10),  # 지수 백오프 (2초, 4초, 8초...)
        retry=retry_if_exception_type((GoogleCloudError, ConnectionError)),
        reraise=True
    )
    def upload_string(self, content: str, destination_blob_name: str) -> str:
        """
        문자열 콘텐츠를 GCS에 업로드하고 검증합니다.
        
        Args:
            content: 저장할 텍스트 내용
            destination_blob_name: 버킷 내 저장 경로 (예: geeknews/2024/file.txt)
            
        Returns:
            gs:// 경로 문자열
        """
        blob = self.bucket.blob(destination_blob_name)
        
        try:
            # 1. 업로드 수행
            blob.upload_from_string(content, content_type="text/plain; charset=utf-8")
            
            # 2. Validation (업로드 확인)
            blob.reload()  # 메타데이터 갱신
            if not blob.exists():
                raise GoogleCloudError(f"Upload verification failed: {destination_blob_name} not found.")
            
            if blob.size == 0 and len(content) > 0:
                logger.warning(f"Warning: Uploaded file size is 0 bytes for {destination_blob_name}")

            gcs_uri = f"gs://{self.bucket_name}/{destination_blob_name}"
            logger.info(f"☁️ Successfully uploaded to GCS: {gcs_uri}")
            return gcs_uri

        except Exception as e:
            logger.error(f"❌ Failed to upload to GCS ({destination_blob_name}): {str(e)}")
            raise e