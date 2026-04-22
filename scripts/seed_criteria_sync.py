"""
Seed script using asyncpg directly with SelectorEventLoop (Windows-safe).
Run: .venv\Scripts\python.exe scripts/seed_criteria_sync.py
"""
from __future__ import annotations

import asyncio
import sys
import os

# Use SelectorEventLoop on Windows to avoid asyncpg + ProactorEventLoop issues
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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
    host = os.getenv("DB_POSTGRES_HOST", "localhost")
    port = int(os.getenv("DB_POSTGRES_PORT", "5432"))
    user = os.getenv("DB_POSTGRES_USER", "admin")
    password = os.getenv("DB_POSTGRES_PASSWORD", "admin")
    database = os.getenv("DB_POSTGRES_NAME", "knowledge_db")

    # Also support full DATABASE_URL
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        # parse postgresql://user:pass@host:port/dbname
        import re
        m = re.match(r"postgresql(?:\+\w+)?://([^:]+):([^@]+)@([^:/]+):(\d+)/(\S+)", db_url)
        if m:
            user, password, host, port, database = m.group(1), m.group(2), m.group(3), int(m.group(4)), m.group(5)

    print(f"Connecting to {host}:{port}/{database} as {user}")

    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=database
    )

    try:
        # Check if already seeded
        count = await conn.fetchval("SELECT COUNT(*) FROM compliance_criteria")
        if count and count > 0:
            print(f"Criteria already exist ({count} rows) — skipping seed.")
            return

        for item in TRANSPORT_CRITERIA:
            await conn.execute(
                """
                INSERT INTO compliance_criteria
                    (name, description, check_prompt, ok_condition, warning_condition,
                     reject_condition, order_num, is_active, contract_type)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                """,
                item["name"], item["description"], item["check_prompt"],
                item["ok_condition"], item["warning_condition"], item["reject_condition"],
                item["order_num"], True, "transport",
            )

        print(f"Seeded {len(TRANSPORT_CRITERIA)} criteria successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
