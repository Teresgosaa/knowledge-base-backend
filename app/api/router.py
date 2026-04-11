from __future__ import annotations

from fastapi import APIRouter

from app.api import auth, chatbot, files, folders, graph, layered_graph, rag_anything

router = APIRouter(prefix="/api")

router.include_router(auth.router)
router.include_router(folders.router)
router.include_router(files.router)
router.include_router(graph.router)
router.include_router(layered_graph.router)
router.include_router(rag_anything.router)
router.include_router(chatbot.router)


# end
