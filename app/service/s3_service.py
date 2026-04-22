import logging
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional
from urllib.parse import quote

import boto3  # noqa
from botocore.exceptions import ClientError

from app.settings.settings import settings

logger = logging.getLogger(__name__)


class AsyncS3Service:
    def __init__(self):
        self.session = boto3.Session()
        self._client = None

    async def get_client(self):
        """Get or create async S3 client"""
        if self._client is None:
            self._client = self.session.client(
                service_name="s3",
                endpoint_url=settings.s3_endpoint_url,
                region_name=settings.s3_region,
                aws_secret_access_key=settings.s3_secret_key,
                aws_access_key_id=settings.s3_access_key,
            )

        return self._client

    async def upload_file(
        self,
        content: bytes | BytesIO,
        filename: str,
        folder: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        # acl: str = "private",
    ) -> Dict[str, Any]:
        """
        Upload file content to S3
        """
        try:
            s3_path = await self.generate_s3_path(filename, folder)
            encoded_filename = quote(filename).replace("%28", "").replace("%29", "")

            s3_metadata = {
                "original-filename": encoded_filename,
                "uploaded-at": datetime.now().isoformat(),
                "content-type": content_type,
            }

            if metadata:
                s3_metadata.update({f"x-amz-meta-{k}": v for k, v in metadata.items()})

            client = await self.get_client()

            _ = client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=s3_path,
                Body=content,
                ContentType=content_type,
                Metadata=s3_metadata,
                # ACL=acl,
            )

            file_url = await self.generate_object_url(s3_path)

            return {
                "s3_path": s3_path,
                "file_url": file_url,
                "uploaded_at": datetime.now(),
            }

        except ClientError as e:
            logger.error(f"S3 upload error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Upload error: {str(e)}")
            raise

    async def generate_object_url(self, s3_path: str) -> str | None:
        """Generate object URL (public or presigned based on ACL)"""
        if settings.s3_endpoint_url:
            return f"{settings.s3_endpoint_url}/{settings.s3_bucket_name}/{s3_path}"
        else:
            return None

    async def generate_download_url(
        self,
        s3_path: str,
        expires_in: int = 3600,
        filename: Optional[str] = None,
    ) -> str:
        """Generate presigned download URL"""
        client = await self.get_client()

        params = {"Bucket": settings.s3_bucket_name, "Key": s3_path}

        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        url = client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)
        return url

    async def delete_file(self, s3_path: str) -> bool:
        """Delete file from S3"""
        try:
            client = await self.get_client()
            client.delete_object(Bucket=settings.s3_bucket_name, Key=s3_path)
            return True
        except ClientError as e:
            logger.error(f"Delete error: {str(e)}")
            return False

    async def list_files(self, prefix: Optional[str] = None, max_keys: int = 100) -> list:
        """List files in S3 bucket"""
        try:
            client = await self.get_client()

            params = {"Bucket": settings.s3_bucket_name, "MaxKeys": max_keys}

            if prefix:
                params["Prefix"] = prefix

            response = client.list_objects_v2(**params)
            return response.get("Contents", [])

        except ClientError as e:
            logger.error(f"List files error: {str(e)}")
            return []

    async def generate_s3_path(self, original_filename: str, folder: str | None = None) -> str:
        if folder:
            folder = folder.strip("/")
            s3_path = f"{folder}/{original_filename}"
        else:
            s3_path = original_filename
        return s3_path

    async def create_folder(self, s3_key: str) -> bool:
        try:
            client = await self.get_client()
            if not s3_key.endswith("/"):
                s3_key += "/"
            client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=s3_key,
                Body=b"",
            )
            return True
        except ClientError as e:
            logger.error(f"S3 create folder error: {str(e)}")
            raise

    async def delete_folder(self, s3_key: str) -> bool:
        try:
            client = await self.get_client()
            if not s3_key.endswith("/"):
                s3_key += "/"
            response = client.list_objects_v2(Bucket=settings.s3_bucket_name, Prefix=s3_key)
            objects = response.get("Contents", [])
            if objects:
                delete_keys = [{"Key": obj["Key"]} for obj in objects]
                client.delete_objects(
                    Bucket=settings.s3_bucket_name,
                    Delete={"Objects": delete_keys},
                )
            client.delete_object(Bucket=settings.s3_bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            logger.error(f"S3 delete folder error: {str(e)}")
            raise

    async def rename_folder(self, old_s3_key: str, new_s3_key: str) -> bool:
        try:
            client = await self.get_client()
            if not old_s3_key.endswith("/"):
                old_s3_key += "/"
            if not new_s3_key.endswith("/"):
                new_s3_key += "/"
            response = client.list_objects_v2(Bucket=settings.s3_bucket_name, Prefix=old_s3_key)
            objects = response.get("Contents", [])
            for obj in objects:
                old_key = obj["Key"]
                new_key = new_s3_key + old_key[len(old_s3_key) :]  # noqa
                client.copy_object(
                    Bucket=settings.s3_bucket_name,
                    Key=new_key,
                    CopySource={"Bucket": settings.s3_bucket_name, "Key": old_key},
                )
                client.delete_object(Bucket=settings.s3_bucket_name, Key=old_key)
            client.delete_object(Bucket=settings.s3_bucket_name, Key=old_s3_key)
            client.put_object(Bucket=settings.s3_bucket_name, Key=new_s3_key, Body=b"")
            return True
        except ClientError as e:
            logger.error(f"S3 rename folder error: {str(e)}")
            raise

    async def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None


# file end
