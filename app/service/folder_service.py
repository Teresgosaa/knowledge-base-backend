from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.folder import Folder
from app.db.user import User
from app.service.s3_service import AsyncS3Service


class FolderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.s3_service = AsyncS3Service()

    def _build_s3_key(self, name: str, parent: Optional[Folder] = None) -> str:
        slug = name.lower().replace(" ", "-")
        if parent:
            return f"{parent.s3_key.rstrip('/')}/{slug}"
        return slug

    async def create_folder(
        self,
        name: str,
        owner: User,
        parent_id: Optional[int] = None,
        description: Optional[str] = None,
    ) -> Folder:
        parent = None
        if parent_id:
            parent = await self._get_folder_by_id(parent_id)
            if not parent:
                raise ValueError("Parent folder not found")

        s3_key = self._build_s3_key(name, parent)
        await self.s3_service.create_folder(s3_key)

        folder = Folder(
            name=name,
            description=description,
            s3_key=s3_key,
            parent_id=parent_id,
            owner_id=owner.id,
        )
        self.db.add(folder)
        await self.db.commit()
        await self.db.refresh(folder)
        return folder

    async def get_folder(self, folder_id: int) -> Optional[Folder]:
        return await self._get_folder_by_id(folder_id)

    async def list_folders(
        self,
        owner: User,
        parent_id: Optional[int] = None,
    ) -> List[Folder]:
        query = select(Folder).where(Folder.owner_id == owner.id)
        if parent_id is not None:
            query = query.where(Folder.parent_id == parent_id)
        else:
            query = query.where(Folder.parent_id.is_(None))
        query = query.options(selectinload(Folder.children))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_folder(
        self,
        folder_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Folder]:
        folder = await self._get_folder_by_id(folder_id)
        if not folder:
            return None

        if name and name != folder.name:
            new_s3_key = self._build_s3_key(
                name,
                await self._get_folder_by_id(folder.parent_id) if folder.parent_id else None,
            )
            await self.s3_service.rename_folder(folder.s3_key, new_s3_key)
            folder.s3_key = new_s3_key
            folder.name = name

        if description is not None:
            folder.description = description

        await self.db.commit()
        await self.db.refresh(folder)
        return folder

    async def delete_folder(self, folder_id: int) -> bool:
        folder = await self._get_folder_by_id(folder_id)
        if not folder:
            return False
        await self.s3_service.delete_folder(folder.s3_key)
        await self.db.delete(folder)
        await self.db.commit()
        return True

    async def _get_folder_by_id(self, folder_id: int) -> Optional[Folder]:
        result = await self.db.execute(select(Folder).where(Folder.id == folder_id))
        return result.scalar_one_or_none()
