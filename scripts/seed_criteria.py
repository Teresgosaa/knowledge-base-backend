"""
Seed script: insert 10 transport contract compliance criteria into the DB.
Run once after the backend has started (tables are created on startup).

Usage:
    cd knowledge-base-backend
    .\.venv\Scripts\python.exe scripts/seed_criteria.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make sure the app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.compliance import ComplianceCriteria
from app.settings.settings import settings

TRANSPORT_CRITERIA = [
    {
        "name": "Стороны контракта",
        "description": "Перевозчик + Заказчик: наименование, ИНН/ОГРН, ФИО подписанта, основание полномочий",
        "check_prompt": (
            "Проверь, указаны ли в договоре полные реквизиты обеих сторон: "
            "наименование организации, ИНН, ОГРН, ФИО и должность подписанта, "
            "основание полномочий (устав, доверенность)."
        ),
        "ok_condition": "Все реквизиты обеих сторон указаны полностью",
        "warning_condition": "Часть реквизитов отсутствует",
        "reject_condition": "Реквизиты сторон не указаны вообще",
        "order_num": 1,
    },
    {
        "name": "Сумма договора",
        "description": "Стоимость перевозки, тариф (за рейс/км/тонну), валюта, порядок пересмотра",
        "check_prompt": (
            "Проверь наличие в договоре: итоговой стоимости или тарифа перевозки "
            "(за рейс, км или тонну), указания валюты расчётов, порядка изменения тарифа."
        ),
        "ok_condition": "Стоимость, тариф, валюта и порядок пересмотра указаны",
        "warning_condition": "Не указан порядок пересмотра тарифа или единица тарифа",
        "reject_condition": "Стоимость и тариф не определены",
        "order_num": 2,
    },
    {
        "name": "Период действия",
        "description": "Даты начала/окончания договора и срок выполнения каждого рейса",
        "check_prompt": (
            "Проверь наличие дат начала и окончания действия договора, "
            "а также срока выполнения отдельного рейса (если применимо)."
        ),
        "ok_condition": "Даты начала/окончания и срок рейса указаны",
        "warning_condition": "Срок выполнения рейса не определён",
        "reject_condition": "Даты действия договора отсутствуют",
        "order_num": 3,
    },
    {
        "name": "Условия оплаты",
        "description": "Реквизиты для оплаты, срок оплаты, порядок документооборота",
        "check_prompt": (
            "Проверь наличие: банковских реквизитов получателя, срока оплаты (в днях или конкретной датой), "
            "перечня документов для оплаты (счёт, акт, накладная)."
        ),
        "ok_condition": "Реквизиты, срок и порядок документооборота указаны",
        "warning_condition": "Срок оплаты или перечень документов не определены",
        "reject_condition": "Условия оплаты отсутствуют",
        "order_num": 4,
    },
    {
        "name": "Предмет договора",
        "description": "Вид груза, маршрут, тип ТС, объём/вес",
        "check_prompt": (
            "Проверь описание предмета договора: вид и наименование груза, "
            "маршрут (пункт отправления и назначения), тип транспортного средства, объём или вес груза."
        ),
        "ok_condition": "Вид груза, маршрут, тип ТС и объём/вес указаны",
        "warning_condition": "Часть параметров груза или маршрута не уточнена",
        "reject_condition": "Предмет договора не определён",
        "order_num": 5,
    },
    {
        "name": "Ответственность за груз",
        "description": "Ограничение ответственности перевозчика, порядок предъявления претензий",
        "check_prompt": (
            "Проверь наличие: размера или ограничения ответственности перевозчика за утрату/порчу груза, "
            "срока и порядка предъявления претензий."
        ),
        "ok_condition": "Ответственность и порядок претензий определены",
        "warning_condition": "Порядок претензий или ограничение ответственности не описаны",
        "reject_condition": "Ответственность за груз не урегулирована",
        "order_num": 6,
    },
    {
        "name": "Нетипичные условия",
        "description": "Необычные штрафы, нестандартная конфиденциальность, арбитражная оговорка",
        "check_prompt": (
            "Выяви нетипичные условия: штрафы непропорциональные сумме договора, "
            "нестандартные условия конфиденциальности (запрет работы с конкурентами), "
            "арбитражная оговорка в пользу другой стороны."
        ),
        "ok_condition": "Нетипичных условий не выявлено",
        "warning_condition": "Выявлены необычные, но не критичные условия",
        "reject_condition": "Условия грубо нарушают интересы компании",
        "order_num": 7,
    },
    {
        "name": "Соответствие шаблону",
        "description": "Структура договора совпадает с корпоративным шаблоном",
        "check_prompt": (
            "Оцени соответствие структуры договора стандартному транспортному договору: "
            "наличие всех обязательных разделов — предмет, стороны, цена, сроки, "
            "ответственность, форс-мажор, реквизиты."
        ),
        "ok_condition": "Структура соответствует корпоративному шаблону",
        "warning_condition": "Один-два раздела отсутствуют или сокращены",
        "reject_condition": "Структура существенно отличается от стандарта",
        "order_num": 8,
    },
    {
        "name": "История контрагента",
        "description": "Задержки, утрата груза, срывы рейсов в прошлом",
        "check_prompt": (
            "Проверь, содержит ли договор или прилагаемые документы информацию об истории работы "
            "с контрагентом: предыдущие нарушения, задержки, утраты груза. "
            "Если информация недоступна — верни WARNING с рекомендацией проверить."
        ),
        "ok_condition": "Негативной истории не выявлено",
        "warning_condition": "Есть отдельные инциденты или информация недоступна",
        "reject_condition": "Систематические нарушения зафиксированы",
        "order_num": 9,
    },
    {
        "name": "Транспортные документы",
        "description": "ТТН, CMR, транспортная накладная, акты приёма-передачи",
        "check_prompt": (
            "Проверь наличие в договоре перечня обязательных транспортных документов: "
            "товарно-транспортная накладная (ТТН), накладная CMR (для международных перевозок), "
            "транспортная накладная, акт приёма-передачи груза."
        ),
        "ok_condition": "Перечень транспортных документов указан полностью",
        "warning_condition": "Перечень документов неполный",
        "reject_condition": "Транспортные документы не упомянуты",
        "order_num": 10,
    },
]


async def seed():
    db_url = (
        settings.database_url
        or f"postgresql+asyncpg://{settings.db_postgres_user}:{settings.db_postgres_password}"
           f"@{settings.db_postgres_host}:{settings.db_postgres_port}/{settings.db_postgres_name}"
    )
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if already seeded
        result = await session.execute(select(ComplianceCriteria).limit(1))
        if result.scalars().first():
            print("Criteria already exist — skipping seed.")
            return

        for item in TRANSPORT_CRITERIA:
            session.add(ComplianceCriteria(
                name=item["name"],
                description=item["description"],
                check_prompt=item["check_prompt"],
                ok_condition=item["ok_condition"],
                warning_condition=item["warning_condition"],
                reject_condition=item["reject_condition"],
                order_num=item["order_num"],
                is_active=True,
                contract_type="transport",
            ))

        await session.commit()
        print(f"Seeded {len(TRANSPORT_CRITERIA)} criteria successfully.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
