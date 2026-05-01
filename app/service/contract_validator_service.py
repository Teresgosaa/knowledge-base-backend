from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Optional

import openai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.compliance import ComplianceCriteria, ValidationReport
from app.settings.settings import settings

logger = logging.getLogger(__name__)

STATUS_ORDER = {"OK": 0, "WARNING": 1, "REJECT": 2}

CRITERION_SYSTEM_PROMPT = """Ты — юридический аналитик, проверяющий договоры. Проанализируй предоставленный текст договора по заданному критерию.

Верни ТОЛЬКО валидный JSON без пояснений и без markdown-оформления:
{
  "status": "OK",
  "summary": "краткий вывод 1-2 предложения",
  "findings": [{"text": "цитата из договора", "section": "пункт договора"}],
  "recommendations": ["что исправить или на что обратить внимание"]
}

Возможные значения status: "OK", "WARNING", "REJECT".
Если данных недостаточно для однозначного вывода — ставь WARNING.
ВАЖНО: если критерий проверяет историю нарушений контрагента и никаких нарушений не найдено — это хорошо, ставь OK. Отсутствие негативной информации не является основанием для WARNING.
"""


class ContractValidatorService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def _get_llm_client(self) -> openai.OpenAI:
        return openai.OpenAI(
            api_key="ignored",
            base_url="https://ai.api.cloud.yandex.net/v1",
            default_headers={
                "Authorization": f"Api-Key {settings.yandex_cloud_api_key}",
                "x-folder-id": settings.yandex_cloud_folder or "",
            },
        )

    def _call_llm_sync(
        self,
        client: openai.OpenAI,
        criterion: ComplianceCriteria,
        context: str,
        token_counter: dict,
    ) -> dict[str, Any]:
        prompt = (
            f"КРИТЕРИЙ: {criterion.name}\n"
            f"Что проверять: {criterion.description or criterion.check_prompt}\n\n"
            f"Условия оценки:\n"
            f"- OK: {criterion.ok_condition or 'всё присутствует'}\n"
            f"- WARNING: {criterion.warning_condition or 'часть данных отсутствует'}\n"
            f"- REJECT: {criterion.reject_condition or 'критические данные отсутствуют'}\n\n"
            f"ТЕКСТ ДОГОВОРА:\n{context[:8000]}"
        )

        try:
            response = client.chat.completions.create(
                model=f"gpt://{settings.yandex_cloud_folder}/{settings.yandex_cloud_model}",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": CRITERION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1000,
            )
            if hasattr(response, "usage") and response.usage:
                token_counter["prompt"] = token_counter.get("prompt", 0) + (response.usage.prompt_tokens or 0)
                token_counter["completion"] = token_counter.get("completion", 0) + (response.usage.completion_tokens or 0)

            raw = (response.choices[0].message.content or "").strip()

            # Strip markdown fences if present
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            result = json.loads(raw)
            result["criterion_id"] = criterion.id
            result["criterion_name"] = criterion.name

            # Ensure required fields
            if "status" not in result or result["status"] not in STATUS_ORDER:
                result["status"] = "WARNING"
            result.setdefault("summary", "")
            result.setdefault("findings", [])
            result.setdefault("recommendations", [])

            return result

        except json.JSONDecodeError as exc:
            logger.warning("JSON parse error for criterion '%s': %s | raw: %.200s", criterion.name, exc, raw)
            return self._error_result(criterion, f"Ошибка разбора ответа LLM: {exc}")
        except Exception as exc:
            logger.error("LLM error for criterion '%s': %s", criterion.name, exc, exc_info=True)
            return self._error_result(criterion, str(exc))

    @staticmethod
    def _error_result(criterion: ComplianceCriteria, error_msg: str) -> dict[str, Any]:
        return {
            "criterion_id": criterion.id,
            "criterion_name": criterion.name,
            "status": "WARNING",
            "summary": f"Не удалось выполнить проверку: {error_msg}",
            "findings": [],
            "recommendations": ["Повторить проверку вручную"],
        }

    async def _get_document_context(self, document_id: str) -> str:
        """Fetch document text via RAG vector search."""
        try:
            from app.service.rag_chatbot_service import rag_chatbot_service
            result = await rag_chatbot_service.retrieve(
                f"полный текст договора {document_id}"
            )
            return result.get("context", "") or ""
        except Exception as exc:
            logger.warning("RAG context unavailable for '%s': %s", document_id, exc)
            return ""

    async def validate_contract(
        self,
        document_id: str,
        user_id: int,
        contract_type: str = "transport",
    ) -> ValidationReport:
        # 1. Get document context from vector store
        context = await self._get_document_context(document_id)
        if not context:
            logger.warning("Empty context for document_id='%s', validation will be limited", document_id)

        # 2. Load active criteria
        result = await self._db.execute(
            select(ComplianceCriteria)
            .where(
                ComplianceCriteria.is_active == True,
                ComplianceCriteria.contract_type == contract_type,
            )
            .order_by(ComplianceCriteria.order_num)
        )
        criteria = list(result.scalars().all())

        if not criteria:
            raise ValueError(f"Нет активных критериев для типа договора '{contract_type}'")

        # 3. Run all criteria checks in parallel
        client = self._get_llm_client()
        loop = asyncio.get_event_loop()
        token_counter: dict = {"prompt": 0, "completion": 0}

        tasks = [
            loop.run_in_executor(None, self._call_llm_sync, client, c, context, token_counter)
            for c in criteria
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 4. Normalize — handle exceptions from gather
        results = []
        for i, r in enumerate(raw_results):
            if isinstance(r, Exception):
                results.append(self._error_result(criteria[i], str(r)))
            else:
                results.append(r)

        # 5. overall_status = worst status across all criteria
        overall_status = max(
            (r.get("status", "OK") for r in results),
            key=lambda s: STATUS_ORDER.get(s, 0),
            default="OK",
        )

        total_tokens = token_counter["prompt"] + token_counter["completion"]
        logger.info(
            "Validation of '%s' complete: %s | criteria=%d | tokens=%d",
            document_id, overall_status, len(results), total_tokens,
        )

        # 6. Save report
        report = ValidationReport(
            id=uuid.uuid4(),
            document_id=document_id,
            bundle=[document_id],
            overall_status=overall_status,
            results=results,
            user_id=user_id,
        )
        self._db.add(report)
        await self._db.commit()
        await self._db.refresh(report)
        return report

    async def get_report(self, report_id: uuid.UUID) -> Optional[ValidationReport]:
        result = await self._db.execute(
            select(ValidationReport).where(ValidationReport.id == report_id)
        )
        return result.scalar_one_or_none()
