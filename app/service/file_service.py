import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.folder import Folder
from app.db.kb_file import KBFile
from app.db.user import User
from app.service.s3_service import AsyncS3Service


class FileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.s3_service = AsyncS3Service()

    def _build_s3_key(self, filename: str, folder_s3_key: str) -> str:
        ext = ""
        if "." in filename:
            ext = filename[filename.rfind(".") :]  # noqa
        unique_name = uuid.uuid4().hex + ext
        return f"{folder_s3_key.rstrip('/')}/{unique_name}"

    async def create_file(
        self,
        content: bytes,
        original_name: str,
        folder_id: int,
        owner: User,
        content_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> KBFile:
        folder = await self._get_folder_by_id(folder_id)
        if not folder:
            raise ValueError("Folder not found")

        s3_key = self._build_s3_key(original_name, folder.s3_key)
        await self.s3_service.upload_file(
            content=content,
            filename=s3_key.split("/")[-1],
            folder=folder.s3_key,
            content_type=content_type,
        )

        kb_file = KBFile(
            name=s3_key.split("/")[-1],
            original_name=original_name,
            s3_key=s3_key,
            content_type=content_type,
            size=len(content) if content else None,
            description=description,
            folder_id=folder_id,
            owner_id=owner.id,
        )
        self.db.add(kb_file)
        await self.db.commit()
        await self.db.refresh(kb_file)
        return kb_file

    async def get_file(self, file_id: int) -> Optional[KBFile]:
        return await self._get_file_by_id(file_id)

    async def get_download_url(self, file_id: int) -> Optional[str]:
        kb_file = await self._get_file_by_id(file_id)
        if not kb_file:
            return None
        return await self.s3_service.generate_download_url(kb_file.s3_key, filename=kb_file.original_name)

    async def list_files(self, folder_id: int) -> List[KBFile]:
        result = await self.db.execute(select(KBFile).where(KBFile.folder_id == folder_id))
        return list(result.scalars().all())

    async def update_file(
        self,
        file_id: int,
        description: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[KBFile]:
        kb_file = await self._get_file_by_id(file_id)
        if not kb_file:
            return None
        if name is not None:
            kb_file.name = name
        if description is not None:
            kb_file.description = description
        await self.db.commit()
        await self.db.refresh(kb_file)
        return kb_file

    async def delete_file(self, file_id: int) -> bool:
        kb_file = await self._get_file_by_id(file_id)
        if not kb_file:
            return False
        await self.s3_service.delete_file(kb_file.s3_key)
        await self.db.delete(kb_file)
        await self.db.commit()
        return True

    async def _get_folder_by_id(self, folder_id: int) -> Optional[Folder]:
        result = await self.db.execute(select(Folder).where(Folder.id == folder_id))
        return result.scalar_one_or_none()

    async def _get_file_by_id(self, file_id: int) -> Optional[KBFile]:
        result = await self.db.execute(select(KBFile).where(KBFile.id == file_id))
        return result.scalar_one_or_none()
