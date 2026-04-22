from __future__ import annotations

import asyncio
import json  # noqa
import logging
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Ensure the current venv's Scripts/bin directory is in PATH so that
# subprocess calls to "docling" can find docling.exe on Windows.
_venv_scripts = Path(sys.executable).parent
_path_env = os.environ.get("PATH", "")
if str(_venv_scripts) not in _path_env:
    os.environ["PATH"] = str(_venv_scripts) + os.pathsep + _path_env

import boto3
import numpy as np
import openai
import requests
from lightrag.utils import wrap_embedding_func_with_attrs
from neo4j import GraphDatabase
from raganything import RAGAnything, RAGAnythingConfig
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.dependencies import get_background_db_session
from app.db.folder import Folder
from app.db.kb_file import KBFile
from app.service.layered_graph.builder import LayeredGraphBuilder
from app.service.node_config import get_entity_type_keys
from app.settings.settings import settings

RAG_WORKING_DIR: str = "./raganything_workspace"
PARSER_OUTPUT_DIR: str = "./output"
LLM_MAX_OUTPUT_TOKENS = 3000
MAX_CONCURRENT_FILES = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

YANDEX_EMBEDDING_DIM = 256
_EMBED_URL = "https://ai.api.cloud.yandex.net:443/foundationModels/v1/textEmbedding"
_EMBED_RPS_DELAY = 0.2
_EMBED_MAX_RETRIES = 5
_EMBED_RETRY_BASE = 2.0

_IGNORED_EXTENSIONS = {
    ".ds_store",
    ".html",
    ".htm",
}



def _load_prompts_from_md(md_path: str = "./data/prompts/prompts.md") -> Dict[str, str]:
    prompts: Dict[str, str] = {}
    current_name: Optional[str] = None
    inside_fence = False
    fence_char: str = ""
    fence_len: int = 0
    fence_lines: List[str] = []

    def _is_fence(line: str, char: str) -> Tuple[bool, int]:
        stripped = line.strip()
        if not stripped.startswith(char):
            return False, 0
        n = 0
        for ch in stripped:
            if ch == char:
                n += 1
            else:
                break
        return n >= 3, n

    with open(md_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")

            if inside_fence:
                is_f, n = _is_fence(line, fence_char)
                if is_f and n >= fence_len:
                    if current_name and fence_lines:
                        prompts[current_name] = "\n".join(fence_lines)
                    inside_fence = False
                    fence_lines = []
                    current_name = None
                    fence_char = ""
                    fence_len = 0
                else:
                    fence_lines.append(line)
            else:
                stripped = line.strip()
                if stripped.startswith("## ") and not stripped.startswith("### "):
                    current_name = stripped[3:].strip()
                elif current_name:
                    for ch in ("`", "~"):
                        is_f, n = _is_fence(stripped, ch)
                        if is_f:
                            inside_fence = True
                            fence_char = ch
                            fence_len = n
                            fence_lines = []
                            break

    return prompts


def patch_lightrag_prompts() -> None:
    from lightrag.prompt import PROMPTS  # type: ignore

    prompts = _load_prompts_from_md()
    for key in (
        "entity_extraction_system_prompt",
        "entity_extraction_user_prompt",
        "entity_continue_extraction_user_prompt",
        "summarize_entity_descriptions",
    ):
        if key in prompts:
            PROMPTS[key] = prompts[key]
        else:
            logger.warning("Prompt '%s' not found in prompts.md", key)

    if "entity_extraction_examples" in prompts:
        PROMPTS["entity_extraction_examples"] = [prompts["entity_extraction_examples"]]

    logger.info("LightRAG entity extraction prompts patched from prompts.md")


async def _set_doc_id_on_nodes(rag, file_name: str, doc_id: str) -> int:
    kg = rag.lightrag.chunk_entity_relation_graph
    driver = kg._driver
    if driver is None:
        logger.warning("Neo4j driver not initialised – skipping doc_id update")
        return 0
    workspace_label = kg._get_workspace_label()

    async with driver.session() as session:
        query = (
            f"MATCH (e:`{workspace_label}`) "
            f"WHERE e.file_path IS NOT NULL "
            f"  AND e.file_path CONTAINS $file_name "
            f"SET e.doc_id = $doc_id "
            f"RETURN count(e) AS updated"
        )
        result = await session.run(query, file_name=file_name, doc_id=doc_id)
        records = await result.data()
    updated = records[0]["updated"] if records else 0
    logger.info(
        "Set doc_id='%s' on %d node(s) matching file '%s'",
        doc_id,
        updated,
        file_name,
    )
    return updated


class RAGAnythingService:
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._layered_graph_builder = LayeredGraphBuilder()

    async def _fetch_iam_token(self) -> str:
        resp = requests.post(
            "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            json={"yandexPassportOauthToken": settings.yandex_cloud_oauth_token},
            timeout=30,
            verify=False,
        )
        resp.raise_for_status()
        token = resp.json()["iamToken"]
        logger.info("Fetched fresh Yandex IAM token")
        return token

    def _make_llm_func(self, iam_token: str, token_counter: Optional[Dict] = None) -> Callable:
        async def llm_model_func(
            prompt: str,
            system_prompt: Optional[str] = None,
            history_messages: Optional[list] = None,
            **kwargs,
        ) -> str:
            try:
                loop = asyncio.get_event_loop()

                def _call() -> str:
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})
                    llm_folder = settings.yandex_cloud_folder
                    client = openai.OpenAI(
                        api_key="ignored",
                        base_url="https://ai.api.cloud.yandex.net/v1",
                        default_headers={
                            "Authorization": f"Api-Key {settings.yandex_cloud_api_key}",
                            "x-folder-id": llm_folder,
                        },
                    )
                    response = client.chat.completions.create(
                        model=f"gpt://{llm_folder}/{settings.yandex_cloud_model}",
                        messages=messages,
                        temperature=0.3,
                        max_tokens=LLM_MAX_OUTPUT_TOKENS,
                    )
                    text = response.choices[0].message.content or ""
                    if not text:
                        logger.warning(
                            "LLM chat.completions empty response: %s",
                            response.model_dump() if hasattr(response, "model_dump") else str(response),
                        )
                    if hasattr(response, "usage") and response.usage:
                        u = response.usage
                        logger.info(
                            "LLM tokens — prompt: %d, completion: %d, total: %d",
                            u.prompt_tokens,
                            u.completion_tokens,
                            u.total_tokens,
                        )
                        if token_counter is not None:
                            token_counter["prompt"] = token_counter.get("prompt", 0) + (u.prompt_tokens or 0)
                            token_counter["completion"] = token_counter.get("completion", 0) + (u.completion_tokens or 0)
                    return text

                return await loop.run_in_executor(None, _call)
            except Exception as exc:
                logger.error("Error calling Yandex Cloud LLM: %s", exc)
                return ""

        return llm_model_func

    def _make_embedding_func(self, iam_token: str) -> Callable:
        @wrap_embedding_func_with_attrs(
            embedding_dim=YANDEX_EMBEDDING_DIM,
            max_token_size=8192,
            model_name="yandex-text-search-doc",
        )
        async def embedding_func(texts: List[str]) -> np.ndarray:
            doc_uri = f"emb://{settings.yandex_cloud_folder}/text-search-doc/latest"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {iam_token}",
                "x-folder-id": settings.yandex_cloud_folder or "",
            }

            loop = asyncio.get_event_loop()

            def _embed_one(text: str) -> List[float]:
                delay = _EMBED_RETRY_BASE
                for attempt in range(_EMBED_MAX_RETRIES):
                    resp = requests.post(
                        _EMBED_URL,
                        json={"modelUri": doc_uri, "text": text},
                        headers=headers,
                        timeout=30,
                        verify=False,
                    )
                    if resp.status_code == 429:
                        wait = delay * (2**attempt)
                        logger.warning(
                            "Embedding 429 – retrying in %.1fs (attempt %d/%d)",
                            wait,
                            attempt + 1,
                            _EMBED_MAX_RETRIES,
                        )
                        import time

                        time.sleep(wait)
                        continue
                    resp.raise_for_status()
                    return resp.json()["embedding"]
                raise RuntimeError(f"Embedding API returned 429 after {_EMBED_MAX_RETRIES} retries")

            try:
                embeddings: List[List[float]] = []
                for text in texts:
                    embedding = await loop.run_in_executor(None, _embed_one, text)
                    embeddings.append(embedding)
                    await asyncio.sleep(_EMBED_RPS_DELAY)
                return np.array(embeddings, dtype=np.float32)
            except Exception as exc:
                logger.error("Error calling Yandex Cloud embedding: %s", exc)
                return np.zeros((len(texts), YANDEX_EMBEDDING_DIM), dtype=np.float32)

        return embedding_func

    def _list_s3_files_sync(self, prefix: str) -> List[Dict]:
        """List all S3 objects under a prefix (handles pagination)."""
        client = boto3.client(
            service_name="s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_secret_access_key=settings.s3_secret_key,
            aws_access_key_id=settings.s3_access_key,
        )
        objects: List[Dict] = []
        continuation_token: Optional[str] = None
        while True:
            params: Dict[str, Any] = {
                "Bucket": settings.s3_bucket_name,
                "MaxKeys": 1000,
            }
            if prefix:
                params["Prefix"] = prefix
            if continuation_token:
                params["ContinuationToken"] = continuation_token
            response = client.list_objects_v2(**params)
            objects.extend(response.get("Contents", []))
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
        return objects

    def _group_s3_files_by_agreement(
        self, s3_objects: List[Dict], prefix: str
    ) -> Dict[str, List[str]]:
        """Group S3 keys by their immediate sub-folder under *prefix*.

        Files at ``<prefix>/agreement-name/file.docx`` → key ``agreement-name``.
        Files directly under ``<prefix>/`` (no sub-folder) → key ``_root``.
        Folder-marker objects (keys ending with ``/``) are skipped.
        """
        normalized_prefix = prefix.rstrip("/") + "/" if prefix else ""
        agreements: Dict[str, List[str]] = {}
        for obj in s3_objects:
            key: str = obj["Key"]
            if key.endswith("/"):
                continue
            rel = key[len(normalized_prefix):]
            if "/" in rel:
                agreement_name = rel.split("/")[0]
            else:
                agreement_name = "_root"
            agreements.setdefault(agreement_name, []).append(key)
        return agreements

    async def _download_s3_files_direct(
        self,
        agreements: Dict[str, List[str]],
        tmp_dir: Path,
    ) -> Dict[str, List[Path]]:
        """Download S3 files grouped by agreement into *tmp_dir*.

        *agreements* maps agreement name → list of S3 keys.
        Returns the same structure with local ``Path`` objects.
        """
        loop = asyncio.get_event_loop()
        local_agreements: Dict[str, List[Path]] = {}

        for agreement_name, s3_keys in agreements.items():
            paths: List[Path] = []
            for s3_key in s3_keys:
                filename = Path(s3_key).name
                if Path(filename).suffix.lower() in _IGNORED_EXTENSIONS:
                    continue
                local_path = tmp_dir / agreement_name / filename
                await loop.run_in_executor(
                    None,
                    self._download_s3_file,
                    s3_key,
                    local_path,
                )
                paths.append(local_path)
                logger.info("Downloaded %s -> %s", s3_key, local_path)
            if paths:
                local_agreements[agreement_name] = paths

        return local_agreements

    async def _process_from_s3(self, task_id: str, s3_prefix: str) -> None:
        task = self._tasks[task_id]
        try:
            task["status"] = "fetching_iam_token"
            iam_token = await self._fetch_iam_token()

            task["status"] = "listing_s3_files"
            loop = asyncio.get_event_loop()
            s3_objects = await loop.run_in_executor(
                None, self._list_s3_files_sync, s3_prefix
            )
            logger.info(
                "Found %d objects under S3 prefix '%s'", len(s3_objects), s3_prefix
            )

            s3_agreements = self._group_s3_files_by_agreement(s3_objects, s3_prefix)
            if not s3_agreements:
                task["status"] = "error"
                task["error"] = f"No files found under S3 prefix '{s3_prefix}'"
                return

            total_files = sum(len(v) for v in s3_agreements.values())
            task["total_files"] = total_files
            logger.info(
                "Grouped into %d agreement(s), %d file(s) total",
                len(s3_agreements),
                total_files,
            )

            task["status"] = "downloading_files"
            tmp_dir = Path(tempfile.mkdtemp(prefix="rag_s3_"))
            try:
                local_agreements = await self._download_s3_files_direct(
                    s3_agreements, tmp_dir
                )
                if not local_agreements:
                    task["status"] = "error"
                    task["error"] = "No downloadable files found under the given S3 prefix"
                    return

                task["status"] = "initializing"
                token_counter: Dict = {"prompt": 0, "completion": 0}
                embedding_func = self._make_embedding_func(iam_token)
                llm_func = self._make_llm_func(iam_token, token_counter)
                rag = await self._initialize_raganything(embedding_func, llm_func)

                try:
                    task["status"] = "processing"
                    processing_results = await self._process_agreements(rag, local_agreements)
                    await rag.finalize_storages()
                except Exception:
                    await rag.finalize_storages()
                    raise

                total_tokens = token_counter["prompt"] + token_counter["completion"]
                logger.info(
                    "Indexing complete — total LLM tokens: prompt=%d, completion=%d, total=%d",
                    token_counter["prompt"],
                    token_counter["completion"],
                    total_tokens,
                )

                task["status"] = "completed"
                task["result"] = {
                    "status": "success",
                    "s3_prefix": s3_prefix,
                    "agreements": processing_results,
                    "tokens": {
                        "prompt": token_counter["prompt"],
                        "completion": token_counter["completion"],
                        "total": total_tokens,
                    },
                    "summary": {
                        "total_agreements": len(local_agreements),
                        "total_files": sum(len(v) for v in local_agreements.values()),
                        "successful_files": sum(
                            1
                            for a in processing_results.values()
                            for f in a["files"]
                            if f["status"] == "success"
                        ),
                        "failed_files": sum(
                            1
                            for a in processing_results.values()
                            for f in a["files"]
                            if f["status"] == "error"
                        ),
                    },
                }
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        except Exception as exc:
            task["status"] = "error"
            task["error"] = str(exc)
            logger.exception("RAGAnything S3 processing failed for task %s", task_id)

    async def start_processing_from_s3(self, s3_prefix: str) -> str:
        task_id = uuid.uuid4().hex
        self._tasks[task_id] = {
            "task_id": task_id,
            "s3_prefix": s3_prefix,
            "status": "pending",
        }
        asyncio.create_task(self._process_from_s3(task_id, s3_prefix))
        return task_id

    async def _scan_folder(self, db: AsyncSession, folder_id: int) -> Dict[str, List[KBFile]]:
        result = await db.execute(
            select(Folder)
            .where(Folder.id == folder_id)
            .options(selectinload(Folder.children).selectinload(Folder.files))
        )
        folder = result.scalar_one_or_none()
        if folder is None:
            raise ValueError(f"Folder with id={folder_id} not found")

        agreements: Dict[str, List[KBFile]] = {}
        for child in folder.children:
            if child.files:
                agreements[child.name] = list(child.files)
                logger.info(
                    "Sub-folder '%s': %d file(s) – %s",
                    child.name,
                    len(child.files),
                    ", ".join(f.original_name for f in child.files),
                )

        return agreements

    def _download_s3_file(self, s3_key: str, local_path: Path) -> None:
        client = boto3.client(
            service_name="s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_secret_access_key=settings.s3_secret_key,
            aws_access_key_id=settings.s3_access_key,
        )
        local_path.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(settings.s3_bucket_name, s3_key, str(local_path))

    async def _download_agreements(
        self,
        agreements: Dict[str, List[KBFile]],
        tmp_dir: Path,
    ) -> Dict[str, List[Path]]:
        loop = asyncio.get_event_loop()
        local_agreements: Dict[str, List[Path]] = {}

        for name, files in agreements.items():
            paths: List[Path] = []
            for f in files:
                if Path(f.original_name).suffix.lower() in _IGNORED_EXTENSIONS:
                    continue
                local_path = tmp_dir / name / f.original_name
                await loop.run_in_executor(
                    None,
                    self._download_s3_file,
                    f.s3_key,
                    local_path,
                )
                paths.append(local_path)
                logger.info("Downloaded %s -> %s", f.s3_key, local_path)
            if paths:
                local_agreements[name] = paths

        return local_agreements

    async def _initialize_raganything(
        self,
        embedding_func: Callable,
        llm_func: Callable,
    ) -> RAGAnything:
        from lightrag import LightRAG
        from lightrag.kg.shared_storage import initialize_pipeline_status

        patch_lightrag_prompts()

        if settings.neo4j_uri:
            os.environ.setdefault("NEO4J_URI", settings.neo4j_uri)
        if settings.neo4j_user:
            os.environ.setdefault("NEO4J_USERNAME", settings.neo4j_user)
        if settings.neo4j_password:
            os.environ.setdefault("NEO4J_PASSWORD", settings.neo4j_password)

        if settings.qdrant_uri:
            os.environ.setdefault("QDRANT_URL", settings.qdrant_uri)

        lightrag_instance = LightRAG(
            working_dir=RAG_WORKING_DIR,
            llm_model_func=llm_func,
            embedding_func=embedding_func,
            graph_storage="Neo4JStorage",
            kv_storage="JsonKVStorage",
            vector_storage="QdrantVectorDBStorage",
            doc_status_storage="JsonDocStatusStorage",
            chunk_token_size=1024,
            chunk_overlap_token_size=20,
            addon_params={
                "language": "Russian",
                "entity_types": get_entity_type_keys(),
            },
        )
        await lightrag_instance.initialize_storages()
        await initialize_pipeline_status()
        logger.info("LightRAG storages initialized (working_dir=%s)", RAG_WORKING_DIR)

        config = RAGAnythingConfig(
            parser="docling",
            parse_method="auto",
            working_dir=RAG_WORKING_DIR,
            parser_output_dir=PARSER_OUTPUT_DIR,
            enable_image_processing=False,
            enable_table_processing=True,
            enable_equation_processing=False,
            use_full_path=False,
            supported_file_extensions=[
                ".pdf",
                ".doc",
                ".docx",
                ".ppt",
                ".pptx",
                ".xls",
                ".xlsx",
                ".md",
                ".txt",
            ],
            max_concurrent_files=MAX_CONCURRENT_FILES,
        )

        rag = RAGAnything(
            lightrag=lightrag_instance,
            config=config,
        )

        logger.info(
            "RAGAnything created (parser=docling, graph_storage=Neo4JStorage, working_dir=%s)",
            RAG_WORKING_DIR,
        )
        return rag

    async def _process_agreements(
        self,
        rag: RAGAnything,
        agreements: Dict[str, List[Path]],
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {}

        for agreement_id, file_paths in agreements.items():
            logger.info(
                "=== Processing agreement '%s' (%d files) ===",
                agreement_id,
                len(file_paths),
            )
            agreement_result: Dict[str, Any] = {
                "agreement_id": agreement_id,
                "files": [],
                "status": "success",
            }

            for file_path in file_paths:
                file_str = str(file_path)
                logger.info("  Processing file: %s", file_str)
                try:
                    file_doc_id = file_path.stem.lower().replace(" ", "-").replace("_", "-")
                    await rag.process_document_complete(
                        file_path=file_str,
                        output_dir=PARSER_OUTPUT_DIR,
                        parse_method="auto",
                        display_stats=True,
                        doc_id=file_doc_id,
                    )
                    await _set_doc_id_on_nodes(rag, file_path.name, agreement_id)
                    agreement_result["files"].append({"file": file_path.name, "status": "success"})
                    logger.info("  Done: %s", file_path.name)
                except Exception as exc:
                    logger.error("  Failed: %s – %s", file_path.name, exc)
                    agreement_result["files"].append(
                        {"file": file_path.name, "status": "error", "error": str(exc)}
                    )

            failed = sum(1 for f in agreement_result["files"] if f["status"] == "error")
            if failed == len(agreement_result["files"]):
                agreement_result["status"] = "error"
            elif failed > 0:
                agreement_result["status"] = "partial"

            results[agreement_id] = agreement_result

        return results

    async def _build_layered_graphs(
        self,
        agreements: Dict[str, List[Path]],
        llm_func: Callable,
    ) -> Dict[str, Any]:
        layered_results: Dict[str, Any] = {}

        for agreement_id, file_paths in agreements.items():
            logger.info(
                "=== Building layered graph for agreement '%s' (%d files) ===",
                agreement_id,
                len(file_paths),
            )
            agreement_layered: Dict[str, Any] = {
                "agreement_id": agreement_id,
                "files": [],
            }

            for file_path in file_paths:
                try:
                    doc_text = self._layered_graph_builder.get_document_text(
                        agreement_id, PARSER_OUTPUT_DIR, file_path=str(file_path)
                    )
                    if not doc_text:
                        if file_path.suffix.lower() in (
                            ".pdf",
                            ".doc",
                            ".docx",
                            ".ppt",
                            ".pptx",
                            ".xls",
                            ".xlsx",
                        ):
                            logger.warning(
                                "No parsed text found for %s (doc_id=%s), skipping raw binary read",
                                file_path.name,
                                agreement_id,
                            )
                            doc_text = ""
                        else:
                            doc_text = file_path.read_text(encoding="utf-8", errors="replace")

                    stats = await self._layered_graph_builder.build_graph_for_document(
                        doc_id=agreement_id,
                        filename=file_path.name,
                        text=doc_text,
                        llm_func=llm_func,
                    )
                    agreement_layered["files"].append(
                        {"file": file_path.name, "status": "success", "stats": stats}
                    )
                    logger.info("  Layered graph built for %s: %s", file_path.name, stats)
                except Exception as exc:
                    logger.error("  Layered graph failed for %s: %s", file_path.name, exc)
                    agreement_layered["files"].append(
                        {"file": file_path.name, "status": "error", "error": str(exc)}
                    )

            layered_results[agreement_id] = agreement_layered
        logger.info(
            "Layered graph built Finished",
        )
        return layered_results

    def _cleanup_unrecognized_entities(self) -> int:
        allowed = [entity.lower().replace(" ", "") for entity in get_entity_type_keys()]
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        try:
            with driver.session() as session:
                result = session.run(
                    """
                    MATCH (n)
                    WHERE n.entity_type IS NOT NULL
                      AND NOT 'Layered' IN labels(n)
                      AND NOT n.entity_type IN $allowed_types
                    DETACH DELETE n
                    RETURN count(n) AS deleted
                    """,
                    allowed_types=allowed,
                )
                record = result.single()
                deleted = record["deleted"] if record else 0
            logger.info("Cleaned up %d nodes with unrecognized entity types", deleted)
            return deleted
        finally:
            driver.close()

    async def _process(self, task_id: str, folder_id: int) -> None:
        task = self._tasks[task_id]
        try:
            task["status"] = "fetching_iam_token"
            iam_token = await self._fetch_iam_token()

            task["status"] = "scanning_folder"
            async with get_background_db_session() as db:
                agreements = await self._scan_folder(db, folder_id)

            if not agreements:
                task["status"] = "error"
                task["error"] = "No sub-folders with files found"
                return

            total_files = sum(len(v) for v in agreements.values())
            task["total_files"] = total_files

            task["status"] = "downloading_files"
            tmp_dir = Path(tempfile.mkdtemp(prefix="rag_anything_"))
            try:
                local_agreements = await self._download_agreements(agreements, tmp_dir)

                if not local_agreements:
                    task["status"] = "error"
                    task["error"] = "No downloadable files found in sub-folders"
                    return

                task["status"] = "initializing"
                token_counter: Dict = {"prompt": 0, "completion": 0}
                embedding_func = self._make_embedding_func(iam_token)
                llm_func = self._make_llm_func(iam_token, token_counter)
                rag = await self._initialize_raganything(embedding_func, llm_func)

                try:
                    task["status"] = "processing"
                    processing_results = await self._process_agreements(rag, local_agreements)

                    await rag.finalize_storages()
                except Exception:
                    await rag.finalize_storages()
                    raise

                # self._cleanup_unrecognized_entities()

                task["status"] = "building_layered_graph"
                llm_func = self._make_llm_func(iam_token, token_counter)
                # layered_results = await self._build_layered_graphs(local_agreements, llm_func)

                total_tokens = token_counter["prompt"] + token_counter["completion"]
                logger.info(
                    "Indexing complete — total LLM tokens: prompt=%d, completion=%d, total=%d",
                    token_counter["prompt"],
                    token_counter["completion"],
                    total_tokens,
                )

                task["status"] = "completed"
                task["result"] = {
                    "status": "success",
                    "agreements": processing_results,
                    # "layered_graph": layered_results,
                    "tokens": {
                        "prompt": token_counter["prompt"],
                        "completion": token_counter["completion"],
                        "total": total_tokens,
                    },
                    "summary": {
                        "total_agreements": len(local_agreements),
                        "total_files": sum(len(v) for v in local_agreements.values()),
                        "successful_files": sum(
                            1
                            for a in processing_results.values()
                            for f in a["files"]
                            if f["status"] == "success"
                        ),
                        "failed_files": sum(
                            1
                            for a in processing_results.values()
                            for f in a["files"]
                            if f["status"] == "error"
                        ),
                    },
                }
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        except Exception as exc:
            task["status"] = "error"
            task["error"] = str(exc)
            logger.exception("RAGAnything processing failed for task %s", task_id)

    async def start_processing(self, folder_id: int) -> str:
        task_id = uuid.uuid4().hex
        self._tasks[task_id] = {
            "task_id": task_id,
            "folder_id": folder_id,
            "status": "pending",
        }
        asyncio.create_task(self._process(task_id, folder_id))
        return task_id

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(task_id)


rag_anything_service = RAGAnythingService()
