from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class LayerType(str, Enum):
    DOCUMENT = "document"
    STRUCTURE = "structure"
    SEMANTIC = "semantic"
    EVIDENCE = "evidence"
    CONTROL = "control"


class NodeType(str, Enum):
    DOCUMENT = "Document"
    DOCUMENT_VERSION = "DocumentVersion"
    CLAUSE = "Clause"
    TEXT_UNIT = "TextUnit"
    REFERENCE = "Reference"
    FINDING = "Finding"
    BUSINESS_OBJECT = "BusinessObject"
    DOCUMENT_TYPE = "DocumentType"
    REGISTRATION_NUMBER = "RegistrationNumber"
    CONTRACT_TYPE = "ContractType"
    START_DATE = "StartDate"
    END_DATE = "EndDate"
    UNTIL_FULL_PERFORMANCE = "UntilFullPerformance"
    STANDARD_CONTRACT = "StandardContract"
    BUSINESS_PARTNER = "BusinessPartner"
    SUPPLIER = "Supplier"
    CONTRACTOR = "Contractor"
    PERFORMER_EXECUTOR = "PerformerExecutor"
    STRUCTURE_UNIT = "StructureUnit"
    SUBJECT = "Subject"
    AMOUNT_WITH_VAT = "AmountWithVAT"
    AMOUNT_WITHOUT_VAT = "AmountWithoutVAT"
    VAT_RATE = "VATRate"
    VAT_AMOUNT = "VATAmount"
    PAYMENT_FORM = "PaymentForm"
    CONTRACT_CURRENCY = "ContractCurrency"
    KASUD_ID = "KASUDID"
    PAYMENT_TERMS = "PaymentTerms"
    BUSINESS_UNIT = "BusinessUnit"
    CUSTOMER_CLIENT = "CustomerClient"
    BUYER = "Buyer"
    PROJECT = "Project"
    INVESTMENT_PROJECT_CODE = "InvestmentProjectCode"
    FRAME_CONTRACT = "FrameContract"
    PAYER = "Payer"
    RECIPIENT = "Recipient"
    BUDGET_ITEM = "BudgetItem"
    STANDARD_NON_STANDARD = "StandardNonStandard"
    EXPENSE_CONTRACT = "ExpenseContract"
    REVENUE_CONTRACT = "RevenueContract"
    SAP_PROJECT = "SAPProject"
    WIN_PARTICIPANT = "WinParticipant"
    LOT_NUMBER = "LotNumber"
    LOT_WINNER = "LotWinner"
    MATERIAL_NAME = "MaterialName"
    GOODS_PRODUCT = "GoodsProduct"
    SKU_ARTICLE_NUMBER = "SKUArticleNumber"
    POSITION_ITEM = "PositionItem"
    ENS_CODE = "ENSCode"
    MATERIAL = "Material"
    UNIT_OF_MEASUREMENT = "UnitOfMeasurement"
    QUANTITY = "Quantity"
    VOLUME = "Volume"
    COST = "Cost"
    PRICE = "Price"
    DELIVERY_PERIOD = "DeliveryPeriod"


class RelationshipType(str, Enum):
    HAS_VERSION = "HAS_VERSION"
    HAS_CLAUSE = "HAS_CLAUSE"
    HAS_CHILD = "HAS_CHILD"
    PRECEDES = "PRECEDES"
    HAS_TEXT_UNIT = "HAS_TEXT_UNIT"
    REFERS_TO = "REFERS_TO"
    HAS_ATTACHMENT = "HAS_ATTACHMENT"
    AMENDS = "AMENDS"
    RELATES_TO_PO = "RELATES_TO_PO"
    MENTIONED_IN = "MENTIONED_IN"
    PLAYS_ROLE_IN = "PLAYS_ROLE_IN"
    DEFINES_TERM = "DEFINES_TERM"
    IMPOSES = "IMPOSES"
    ON_PARTY = "ON_PARTY"
    ABOUT_OBJECT = "ABOUT_OBJECT"
    CHECKS = "CHECKS"
    RESULT_OF = "RESULT_OF"
    SUPPORTED_BY = "SUPPORTED_BY"


class DocumentSubtype(str, Enum):
    CONTRACT = "Contract"
    ADDENDUM = "Addendum"
    ANNEX = "Annex"
    PO = "PurchaseOrder"
    SPECIFICATION = "Specification"
    AMENDMENT = "Amendment"
    ACT = "Act"
    PROTOCOL = "Protocol"
    INVOICE = "Invoice"
    RFQ = "RFQ"


class FindingType(str, Enum):
    MISMATCH = "mismatch"
    MISSING = "missing"
    CONFLICT = "conflict"
    RISK = "risk"


class ClauseType(str, Enum):
    SECTION = "section"
    CLAUSE = "clause"
    SUBCLAUSE = "subclause"
    ANNEX_ITEM = "annex_item"
    TABLE_ROW = "table_row"


@dataclass(frozen=True)
class PropertyDef:
    name: str
    type: str
    required: bool = False
    description: str = ""
    default: str | None = None


@dataclass(frozen=True)
class LayerDef:
    name: str
    layer_type: LayerType
    description: str
    node_types: List[NodeType]


@dataclass(frozen=True)
class NodeDef:
    node_type: NodeType
    layer: LayerType
    label: str
    description: str
    properties: List[PropertyDef] = field(default_factory=list)
    subtypes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RelationshipDef:
    rel_type: RelationshipType
    source_types: List[NodeType]
    target_types: List[NodeType]
    description: str
    properties: List[PropertyDef] = field(default_factory=list)


SEMANTIC_NODE_TYPES = [
    NodeType.DOCUMENT_TYPE,
    NodeType.REGISTRATION_NUMBER,
    NodeType.CONTRACT_TYPE,
    NodeType.START_DATE,
    NodeType.END_DATE,
    NodeType.UNTIL_FULL_PERFORMANCE,
    NodeType.STANDARD_CONTRACT,
    NodeType.BUSINESS_PARTNER,
    NodeType.SUPPLIER,
    NodeType.CONTRACTOR,
    NodeType.PERFORMER_EXECUTOR,
    NodeType.STRUCTURE_UNIT,
    NodeType.SUBJECT,
    NodeType.AMOUNT_WITH_VAT,
    NodeType.AMOUNT_WITHOUT_VAT,
    NodeType.VAT_RATE,
    NodeType.VAT_AMOUNT,
    NodeType.PAYMENT_FORM,
    NodeType.CONTRACT_CURRENCY,
    NodeType.KASUD_ID,
    NodeType.PAYMENT_TERMS,
    NodeType.BUSINESS_UNIT,
    NodeType.CUSTOMER_CLIENT,
    NodeType.BUYER,
    NodeType.PROJECT,
    NodeType.INVESTMENT_PROJECT_CODE,
    NodeType.FRAME_CONTRACT,
    NodeType.PAYER,
    NodeType.RECIPIENT,
    NodeType.BUDGET_ITEM,
    NodeType.STANDARD_NON_STANDARD,
    NodeType.EXPENSE_CONTRACT,
    NodeType.REVENUE_CONTRACT,
    NodeType.SAP_PROJECT,
    NodeType.WIN_PARTICIPANT,
    NodeType.LOT_NUMBER,
    NodeType.LOT_WINNER,
    NodeType.MATERIAL_NAME,
    NodeType.GOODS_PRODUCT,
    NodeType.SKU_ARTICLE_NUMBER,
    NodeType.POSITION_ITEM,
    NodeType.ENS_CODE,
    NodeType.MATERIAL,
    NodeType.UNIT_OF_MEASUREMENT,
    NodeType.QUANTITY,
    NodeType.VOLUME,
    NodeType.COST,
    NodeType.PRICE,
    NodeType.DELIVERY_PERIOD,
]

RUSSIAN_NAME_TO_NODE_TYPE = {
    "виддокумента": NodeType.DOCUMENT_TYPE,
    "номеррегистрационный": NodeType.REGISTRATION_NUMBER,
    "виддоговора": NodeType.CONTRACT_TYPE,
    "началодействия": NodeType.START_DATE,
    "датаначала": NodeType.START_DATE,
    "окончаниедействия": NodeType.END_DATE,
    "флаг'дополногоисполнения'": NodeType.UNTIL_FULL_PERFORMANCE,
    "флагдополногоисполнения": NodeType.UNTIL_FULL_PERFORMANCE,
    "типовойдоговор": NodeType.STANDARD_CONTRACT,
    "деловойпартнер": NodeType.BUSINESS_PARTNER,
    "поставщик": NodeType.SUPPLIER,
    "подрядчик": NodeType.CONTRACTOR,
    "исполнитель": NodeType.PERFORMER_EXECUTOR,
    "структурноеподразделение": NodeType.STRUCTURE_UNIT,
    "предметдоговора": NodeType.SUBJECT,
    "суммадоговорасндс": NodeType.AMOUNT_WITH_VAT,
    "суммадоговорабезндс": NodeType.AMOUNT_WITHOUT_VAT,
    "ставкандс": NodeType.VAT_RATE,
    "суммандс": NodeType.VAT_AMOUNT,
    "формаоплаты": NodeType.PAYMENT_FORM,
    "валютадоговора": NodeType.CONTRACT_CURRENCY,
    "идрккасуд": NodeType.KASUD_ID,
    "idрккасуд": NodeType.KASUD_ID,
    "условияоплаты": NodeType.PAYMENT_TERMS,
    "бе": NodeType.BUSINESS_UNIT,
    "заказчик": NodeType.CUSTOMER_CLIENT,
    "покупатель": NodeType.BUYER,
    "проект": NodeType.PROJECT,
    "кодинвестиционногопроекта": NodeType.INVESTMENT_PROJECT_CODE,
    "рамочныйдоговор": NodeType.FRAME_CONTRACT,
    "плательщик": NodeType.PAYER,
    "получатель": NodeType.RECIPIENT,
    "статьябюджета": NodeType.BUDGET_ITEM,
    "договорсоставленпотиповойнетиповойформе": NodeType.STANDARD_NON_STANDARD,
    "договоррасхода": NodeType.EXPENSE_CONTRACT,
    "договордохода": NodeType.REVENUE_CONTRACT,
    "номерпроектаsap": NodeType.SAP_PROJECT,
    "наименованиеучастникапобедителя": NodeType.WIN_PARTICIPANT,
    "номерлота": NodeType.LOT_NUMBER,
    "победительполоту": NodeType.LOT_WINNER,
    "наименованиематериала": NodeType.MATERIAL_NAME,
    "товар": NodeType.GOODS_PRODUCT,
    "артикул": NodeType.SKU_ARTICLE_NUMBER,
    "позиция": NodeType.POSITION_ITEM,
    "коденс": NodeType.ENS_CODE,
    "материал": NodeType.MATERIAL,
    "единицаизмерения": NodeType.UNIT_OF_MEASUREMENT,
    "количество": NodeType.QUANTITY,
    "объём": NodeType.VOLUME,
    "стоимость": NodeType.COST,
    "цена": NodeType.PRICE,
    "периодпоставки": NodeType.DELIVERY_PERIOD,
}

LAYER_DEFINITIONS: List[LayerDef] = [
    LayerDef(
        name="Document Layer",
        layer_type=LayerType.DOCUMENT,
        description="Договор, приложение, допсоглашение, PO, спецификация, акт",
        node_types=[
            NodeType.DOCUMENT,
            NodeType.DOCUMENT_VERSION,
            NodeType.BUSINESS_OBJECT,
        ],
    ),
    LayerDef(
        name="Structure Layer",
        layer_type=LayerType.STRUCTURE,
        description="section / clause / subclause / annex item / table row",
        node_types=[NodeType.CLAUSE, NodeType.REFERENCE],
    ),
    LayerDef(
        name="Semantic Layer",
        layer_type=LayerType.SEMANTIC,
        description=(
            "Сущности RAG Anything: стороны, суммы, даты, валюты, условия оплаты, товары, проекты"
        ),
        node_types=SEMANTIC_NODE_TYPES,
    ),
    LayerDef(
        name="Evidence Layer",
        layer_type=LayerType.EVIDENCE,
        description="Текстовые единицы, excerpts, spans, page anchors, offsets",
        node_types=[NodeType.TEXT_UNIT],
    ),
]

NODE_DEFINITIONS: List[NodeDef] = [
    NodeDef(
        node_type=NodeType.DOCUMENT,
        layer=LayerType.DOCUMENT,
        label="Document",
        description="Любой документ: Contract, Addendum, Annex, PO, Specification, Amendment",
        properties=[
            PropertyDef(
                "uid",
                "str",
                required=True,
                description="Уникальный идентификатор документа",
            ),
            PropertyDef(
                "doc_id",
                "str",
                required=True,
                description="Бизнес-идентификатор (agreement_id)",
            ),
            PropertyDef("title", "str", description="Название документа"),
            PropertyDef(
                "doc_subtype",
                "str",
                required=True,
                description=(
                    "Подтип: Contract, Addendum, Annex, PO, Specification, Amendment, Act, Protocol"
                ),
            ),
            PropertyDef("original_filename", "str", description="Имя файла"),
            PropertyDef("s3_key", "str", description="Путь в S3"),
            PropertyDef("language", "str", default="ru", description="Язык документа"),
            PropertyDef("file_hash", "str", description="SHA-256 хэш файла"),
        ],
        subtypes=[e.value for e in DocumentSubtype],
    ),
    NodeDef(
        node_type=NodeType.DOCUMENT_VERSION,
        layer=LayerType.DOCUMENT,
        label="DocumentVersion",
        description="Версия документа или состояние на дату",
        properties=[
            PropertyDef(
                "uid",
                "str",
                required=True,
                description="Уникальный идентификатор версии",
            ),
            PropertyDef("version", "int", required=True, description="Номер версии"),
            PropertyDef(
                "status",
                "str",
                default="draft",
                description="Статус: draft, active, superseded, archived",
            ),
            PropertyDef("effective_date", "str", description="Дата вступления в силу"),
            PropertyDef("created_at", "str", description="Дата создания версии"),
        ],
    ),
    NodeDef(
        node_type=NodeType.CLAUSE,
        layer=LayerType.STRUCTURE,
        label="Clause",
        description="Нормализованный структурный элемент: раздел, пункт, подпункт",
        properties=[
            PropertyDef("uid", "str", required=True, description="Уникальный идентификатор"),
            PropertyDef(
                "clause_id",
                "str",
                required=True,
                description="Номер/идентификатор пункта (напр. '4.2', 'Приложение 1')",
            ),
            PropertyDef(
                "clause_type",
                "str",
                required=True,
                description="Тип: section, clause, subclause, annex_item, table_row",
            ),
            PropertyDef("title", "str", description="Заголовок раздела/пункта"),
            PropertyDef("full_text", "str", description="Полный текст пункта"),
            PropertyDef("order_index", "int", description="Порядковый номер в документе"),
            PropertyDef("page_number", "int", description="Номер страницы"),
            PropertyDef("doc_id", "str", description="Привязка к документу"),
        ],
    ),
    NodeDef(
        node_type=NodeType.TEXT_UNIT,
        layer=LayerType.EVIDENCE,
        label="TextUnit",
        description="Поисковая текстовая единица для embeddings и цитирования",
        properties=[
            PropertyDef("uid", "str", required=True, description="Уникальный идентификатор"),
            PropertyDef("text", "str", required=True, description="Текст единицы"),
            PropertyDef(
                "text_type",
                "str",
                default="excerpt",
                description="Тип: excerpt, span, paragraph, sentence",
            ),
            PropertyDef("page_number", "int", description="Номер страницы"),
            PropertyDef("offset_start", "int", description="Начальное смещение в документе"),
            PropertyDef("offset_end", "int", description="Конечное смещение в документе"),
            PropertyDef("doc_id", "str", description="Привязка к документу"),
        ],
    ),
    NodeDef(
        node_type=NodeType.REFERENCE,
        layer=LayerType.STRUCTURE,
        label="Reference",
        description="Внутренняя/внешняя ссылка",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef(
                "ref_text",
                "str",
                required=True,
                description="Текст ссылки (напр. 'согласно п. 4.2')",
            ),
            PropertyDef("ref_target", "str", description="Целевой пункт/документ"),
            PropertyDef("ref_type", "str", description="Тип: internal, external"),
            PropertyDef("doc_id", "str"),
        ],
    ),
    # NodeDef(
    #     node_type=NodeType.COMPLIANCE_RULE,
    #     layer=LayerType.CONTROL,
    #     label="ComplianceRule",
    #     description="Машинно-исполняемое правило сверки",
    #     properties=[
    #         PropertyDef("uid", "str", required=True),
    #         PropertyDef("rule_id", "str", required=True, description="Идентификатор правила"),
    #         PropertyDef("name", "str", required=True, description="Название правила"),
    #         PropertyDef("description", "str", description="Описание правила"),
    #         PropertyDef(
    #             "severity",
    #             "str",
    #             default="medium",
    #             description="Критичность: critical, high, medium, low",
    #         ),
    #         PropertyDef(
    #             "check_type",
    #             "str",
    #             required=True,
    #             description="Тип проверки: existence, value_match, date_range, cross_reference",
    #         ),
    #         PropertyDef("parameters", "str", description="JSON-параметры правила"),
    #     ],
    # ),
    NodeDef(
        node_type=NodeType.FINDING,
        layer=LayerType.CONTROL,
        label="Finding",
        description="Результат проверки: mismatch, missing, conflict, risk",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef(
                "finding_type",
                "str",
                required=True,
                description="Тип: mismatch, missing, conflict, risk",
            ),
            PropertyDef(
                "severity",
                "str",
                default="medium",
                description="Критичность: critical, high, medium, low",
            ),
            PropertyDef("description", "str", required=True, description="Описание находки"),
            PropertyDef("expected_value", "str", description="Ожидаемое значение"),
            PropertyDef("actual_value", "str", description="Фактическое значение"),
            PropertyDef("confidence", "float", description="Уверенность 0.0-1.0"),
            PropertyDef(
                "status",
                "str",
                default="open",
                description="Статус: open, confirmed, dismissed, resolved",
            ),
            PropertyDef("reviewer_decision", "str", description="Решение ревьюера"),
            PropertyDef("doc_id", "str"),
        ],
    ),
    NodeDef(
        node_type=NodeType.BUSINESS_OBJECT,
        layer=LayerType.DOCUMENT,
        label="BusinessObject",
        description="Объекты закупки: PurchaseOrder, SupplierMaster, RFQ, Invoice",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef(
                "bo_type",
                "str",
                required=True,
                description="Тип: PurchaseOrder, SupplierMaster, RFQ, Invoice",
            ),
            PropertyDef("external_id", "str", description="Внешний идентификатор"),
            PropertyDef("name", "str", description="Название"),
            PropertyDef("status", "str", description="Статус объекта"),
            PropertyDef("metadata", "str", description="JSON-метаданные"),
        ],
    ),
    NodeDef(
        node_type=NodeType.DOCUMENT_TYPE,
        layer=LayerType.SEMANTIC,
        label="DocumentType",
        description="Вид документа",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="виддокумента"),
            PropertyDef("value", "str", required=True, description="Значение"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.REGISTRATION_NUMBER,
        layer=LayerType.SEMANTIC,
        label="RegistrationNumber",
        description="Номер регистрационный",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="номеррегистрационный"),
            PropertyDef("number", "str", required=True, description="Номер"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.CONTRACT_TYPE,
        layer=LayerType.SEMANTIC,
        label="ContractType",
        description="Вид договора",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="виддоговора"),
            PropertyDef("type", "str", required=True, description="Тип договора"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.START_DATE,
        layer=LayerType.SEMANTIC,
        label="StartDate",
        description="Начало действия / Дата начала",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="началодействия/датаначала"),
            PropertyDef("date_value", "str", required=True, description="Дата в ISO формате"),
            PropertyDef("original_text", "str", description="Исходный текст"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.END_DATE,
        layer=LayerType.SEMANTIC,
        label="EndDate",
        description="Окончание действия",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="окончаниедействия"),
            PropertyDef("date_value", "str", required=True, description="Дата в ISO формате"),
            PropertyDef("original_text", "str", description="Исходный текст"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.UNTIL_FULL_PERFORMANCE,
        layer=LayerType.SEMANTIC,
        label="UntilFullPerformance",
        description="Флаг 'До полного исполнения'",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="флаг'дополногоисполнения'"),
            PropertyDef("is_until_full_performance", "bool", required=True),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.STANDARD_CONTRACT,
        layer=LayerType.SEMANTIC,
        label="StandardContract",
        description="Типовой договор",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="типовойдоговор"),
            PropertyDef("is_standard", "bool", required=True),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.BUSINESS_PARTNER,
        layer=LayerType.SEMANTIC,
        label="BusinessPartner",
        description="Деловой партнер",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="деловойпартнер"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("inn", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.SUPPLIER,
        layer=LayerType.SEMANTIC,
        label="Supplier",
        description="Поставщик",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="поставщик"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("inn", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.CONTRACTOR,
        layer=LayerType.SEMANTIC,
        label="Contractor",
        description="Подрядчик",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="подрядчик"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("inn", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.PERFORMER_EXECUTOR,
        layer=LayerType.SEMANTIC,
        label="PerformerExecutor",
        description="Исполнитель",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="исполнитель"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.STRUCTURE_UNIT,
        layer=LayerType.SEMANTIC,
        label="StructureUnit",
        description="Структурное подразделение",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="структурноеподразделение"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.SUBJECT,
        layer=LayerType.SEMANTIC,
        label="Subject",
        description="Предмет договора",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="предметдоговора"),
            PropertyDef("description", "str", required=True, description="Описание"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.AMOUNT_WITH_VAT,
        layer=LayerType.SEMANTIC,
        label="AmountWithVAT",
        description="Сумма договора с НДС",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="суммадоговорасндс"),
            PropertyDef("value", "float", required=True, description="Сумма"),
            PropertyDef("currency", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.AMOUNT_WITHOUT_VAT,
        layer=LayerType.SEMANTIC,
        label="AmountWithoutVAT",
        description="Сумма договора без НДС",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="суммадоговорабезндс"),
            PropertyDef("value", "float", required=True, description="Сумма"),
            PropertyDef("currency", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.VAT_RATE,
        layer=LayerType.SEMANTIC,
        label="VATRate",
        description="Ставка НДС",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="ставкандс"),
            PropertyDef("rate", "float", required=True, description="Ставка НДС в %"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.VAT_AMOUNT,
        layer=LayerType.SEMANTIC,
        label="VATAmount",
        description="Сумма НДС",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="суммандс"),
            PropertyDef("value", "float", required=True, description="Сумма НДС"),
            PropertyDef("currency", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.PAYMENT_FORM,
        layer=LayerType.SEMANTIC,
        label="PaymentForm",
        description="Форма оплаты",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="формаоплаты"),
            PropertyDef("form", "str", required=True, description="Форма оплаты"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.CONTRACT_CURRENCY,
        layer=LayerType.SEMANTIC,
        label="ContractCurrency",
        description="Валюта договора",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="валютадоговора"),
            PropertyDef("code", "str", required=True, description="Код валюты"),
            PropertyDef("name", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.KASUD_ID,
        layer=LayerType.SEMANTIC,
        label="KASUDID",
        description="ID РК КАСУД",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="идрккабуд"),
            PropertyDef("kasud_id", "str", required=True, description="Идентификатор КАСУД"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.PAYMENT_TERMS,
        layer=LayerType.SEMANTIC,
        label="PaymentTerms",
        description="Условия оплаты",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="условияоплаты"),
            PropertyDef("description", "str", required=True, description="Описание условий"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.BUSINESS_UNIT,
        layer=LayerType.SEMANTIC,
        label="BusinessUnit",
        description="БЕ",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="бе"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("code", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.CUSTOMER_CLIENT,
        layer=LayerType.SEMANTIC,
        label="CustomerClient",
        description="Заказчик",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="заказчик"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.BUYER,
        layer=LayerType.SEMANTIC,
        label="Buyer",
        description="Покупатель",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="покупатель"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.PROJECT,
        layer=LayerType.SEMANTIC,
        label="Project",
        description="Проект",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="проект"),
            PropertyDef("name", "str", required=True, description="Наименование проекта"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.INVESTMENT_PROJECT_CODE,
        layer=LayerType.SEMANTIC,
        label="InvestmentProjectCode",
        description="Код инвестиционного проекта",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="кодинвестиционногопроекта"),
            PropertyDef("code", "str", required=True, description="Код проекта"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.FRAME_CONTRACT,
        layer=LayerType.SEMANTIC,
        label="FrameContract",
        description="Рамочный договор",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="рамочныйдоговор"),
            PropertyDef("is_frame", "bool", required=True),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.PAYER,
        layer=LayerType.SEMANTIC,
        label="Payer",
        description="Плательщик",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="плательщик"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.RECIPIENT,
        layer=LayerType.SEMANTIC,
        label="Recipient",
        description="Получатель",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="получатель"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.BUDGET_ITEM,
        layer=LayerType.SEMANTIC,
        label="BudgetItem",
        description="Статья бюджета",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="статьябюджета"),
            PropertyDef("name", "str", required=True, description="Наименование статьи"),
            PropertyDef("code", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.STANDARD_NON_STANDARD,
        layer=LayerType.SEMANTIC,
        label="StandardNonStandard",
        description="Договор составлен по типовой/нетиповой форме",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef(
                "label", "str", required=True, description="договорсоставленпотиповой/нетиповойформе"
            ),
            PropertyDef("is_standard", "bool", required=True),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.EXPENSE_CONTRACT,
        layer=LayerType.SEMANTIC,
        label="ExpenseContract",
        description="Договор расхода",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="договоррасхода"),
            PropertyDef("is_expense", "bool", required=True),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.REVENUE_CONTRACT,
        layer=LayerType.SEMANTIC,
        label="RevenueContract",
        description="Договор дохода",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="договордохода"),
            PropertyDef("is_revenue", "bool", required=True),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.SAP_PROJECT,
        layer=LayerType.SEMANTIC,
        label="SAPProject",
        description="Номер проекта SAP",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="номерпроектазп"),
            PropertyDef("sap_id", "str", required=True, description="ID проекта в SAP"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.WIN_PARTICIPANT,
        layer=LayerType.SEMANTIC,
        label="WinParticipant",
        description="Наименование участника-победителя",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="наименованиеучастника-победителя"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.LOT_NUMBER,
        layer=LayerType.SEMANTIC,
        label="LotNumber",
        description="Номер лота",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="номерлота"),
            PropertyDef("number", "str", required=True, description="Номер лота"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.LOT_WINNER,
        layer=LayerType.SEMANTIC,
        label="LotWinner",
        description="Победитель по лоту",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="победительполоту"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.MATERIAL_NAME,
        layer=LayerType.SEMANTIC,
        label="MaterialName",
        description="Наименование материала",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="наименованиематериала"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.GOODS_PRODUCT,
        layer=LayerType.SEMANTIC,
        label="GoodsProduct",
        description="Товар",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="товар"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.SKU_ARTICLE_NUMBER,
        layer=LayerType.SEMANTIC,
        label="SKUArticleNumber",
        description="Артикул",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="артикул"),
            PropertyDef("sku", "str", required=True, description="Артикул"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.POSITION_ITEM,
        layer=LayerType.SEMANTIC,
        label="PositionItem",
        description="Позиция",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="позиция"),
            PropertyDef("position_number", "str", required=True, description="Номер позиции"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.ENS_CODE,
        layer=LayerType.SEMANTIC,
        label="ENSCode",
        description="Код ЕНС",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="коденс"),
            PropertyDef("code", "str", required=True, description="Код ЕНС"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.MATERIAL,
        layer=LayerType.SEMANTIC,
        label="Material",
        description="Материал",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="материал"),
            PropertyDef("name", "str", required=True, description="Наименование"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.UNIT_OF_MEASUREMENT,
        layer=LayerType.SEMANTIC,
        label="UnitOfMeasurement",
        description="Единица измерения",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="единицаизмерения"),
            PropertyDef("unit", "str", required=True, description="Единица измерения"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.QUANTITY,
        layer=LayerType.SEMANTIC,
        label="Quantity",
        description="Количество",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="количество"),
            PropertyDef("value", "float", required=True, description="Количество"),
            PropertyDef("unit", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.VOLUME,
        layer=LayerType.SEMANTIC,
        label="Volume",
        description="Объём",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="объём"),
            PropertyDef("value", "float", required=True, description="Объем"),
            PropertyDef("unit", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.COST,
        layer=LayerType.SEMANTIC,
        label="Cost",
        description="Стоимость",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="стоимость"),
            PropertyDef("value", "float", required=True, description="Стоимость"),
            PropertyDef("currency", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.PRICE,
        layer=LayerType.SEMANTIC,
        label="Price",
        description="Цена",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="цена"),
            PropertyDef("value", "float", required=True, description="Цена"),
            PropertyDef("currency", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
    NodeDef(
        node_type=NodeType.DELIVERY_PERIOD,
        layer=LayerType.SEMANTIC,
        label="DeliveryPeriod",
        description="Период поставки",
        properties=[
            PropertyDef("uid", "str", required=True),
            PropertyDef("label", "str", required=True, description="периодпоставки"),
            PropertyDef("description", "str", required=True, description="Описание срока"),
            PropertyDef("start_date", "str"),
            PropertyDef("end_date", "str"),
            PropertyDef("doc_id", "str", required=True),
        ],
    ),
]

RELATIONSHIP_DEFINITIONS: List[RelationshipDef] = [
    RelationshipDef(
        rel_type=RelationshipType.HAS_VERSION,
        source_types=[NodeType.DOCUMENT],
        target_types=[NodeType.DOCUMENT_VERSION],
        description="Документ имеет версию",
    ),
    RelationshipDef(
        rel_type=RelationshipType.HAS_CLAUSE,
        source_types=[NodeType.DOCUMENT_VERSION],
        target_types=[NodeType.CLAUSE],
        description="Версия документа содержит пункт",
    ),
    RelationshipDef(
        rel_type=RelationshipType.HAS_CHILD,
        source_types=[NodeType.CLAUSE],
        target_types=[NodeType.CLAUSE],
        description="Пункт содержит подпункт",
    ),
    RelationshipDef(
        rel_type=RelationshipType.PRECEDES,
        source_types=[NodeType.CLAUSE],
        target_types=[NodeType.CLAUSE],
        description="Пункт предшествует другому",
        properties=[PropertyDef("order", "int", description="Порядок следования")],
    ),
    RelationshipDef(
        rel_type=RelationshipType.HAS_TEXT_UNIT,
        source_types=[NodeType.CLAUSE],
        target_types=[NodeType.TEXT_UNIT],
        description="Пункт содержит текстовую единицу",
    ),
    RelationshipDef(
        rel_type=RelationshipType.REFERS_TO,
        source_types=[NodeType.CLAUSE],
        target_types=[NodeType.CLAUSE],
        description="Пункт ссылается на другой пункт",
        properties=[PropertyDef("ref_text", "str", description="Текст ссылки")],
    ),
    RelationshipDef(
        rel_type=RelationshipType.HAS_ATTACHMENT,
        source_types=[NodeType.DOCUMENT],
        target_types=[NodeType.DOCUMENT],
        description="Документ имеет приложение",
    ),
    RelationshipDef(
        rel_type=RelationshipType.AMENDS,
        source_types=[NodeType.DOCUMENT],
        target_types=[NodeType.DOCUMENT],
        description="Документ изменяет другой документ",
    ),
    RelationshipDef(
        rel_type=RelationshipType.RELATES_TO_PO,
        source_types=[NodeType.DOCUMENT],
        target_types=[NodeType.BUSINESS_OBJECT],
        description="Документ связан с заказом на закупку",
    ),
    RelationshipDef(
        rel_type=RelationshipType.MENTIONED_IN,
        source_types=SEMANTIC_NODE_TYPES,
        target_types=[NodeType.CLAUSE],
        description="Сущность упомянута в пункте",
    ),
    RelationshipDef(
        rel_type=RelationshipType.PLAYS_ROLE_IN,
        source_types=[NodeType.SUPPLIER, NodeType.CONTRACTOR, NodeType.CUSTOMER_CLIENT, NodeType.BUYER],
        target_types=[NodeType.DOCUMENT],
        description="Организация играет роль в документе",
        properties=[
            PropertyDef(
                "role",
                "str",
                required=True,
                description="Роль: supplier, buyer, contractor, customer",
            )
        ],
    ),
    RelationshipDef(
        rel_type=RelationshipType.DEFINES_TERM,
        source_types=[NodeType.CLAUSE],
        target_types=[NodeType.PAYMENT_TERMS, NodeType.DELIVERY_PERIOD],
        description="Пункт определяет условие",
    ),
    RelationshipDef(
        rel_type=RelationshipType.ABOUT_OBJECT,
        source_types=[NodeType.SUBJECT],
        target_types=[NodeType.BUSINESS_OBJECT, NodeType.GOODS_PRODUCT, NodeType.MATERIAL],
        description="Предмет касается объекта/товара",
    ),
    # RelationshipDef(
    #     rel_type=RelationshipType.CHECKS,
    #     source_types=[NodeType.COMPLIANCE_RULE],
    #     target_types=SEMANTIC_NODE_TYPES,
    #     description="Правило проверяет сущность",
    # ),
    # RelationshipDef(
    #     rel_type=RelationshipType.RESULT_OF,
    #     source_types=[NodeType.FINDING],
    #     target_types=[NodeType.COMPLIANCE_RULE],
    #     description="Находка — результат проверки правила",
    # ),
    RelationshipDef(
        rel_type=RelationshipType.SUPPORTED_BY,
        source_types=[NodeType.FINDING],
        target_types=[NodeType.CLAUSE, NodeType.TEXT_UNIT, NodeType.BUSINESS_OBJECT],
        description="Находка подкрепляется пунктом/текстом/объектом",
    ),
]

NODE_TYPE_TO_LAYER: Dict[NodeType, LayerType] = {nd.node_type: nd.layer for nd in NODE_DEFINITIONS}

LABEL_TO_NODE_TYPE: Dict[str, NodeType] = {nd.node_type.value: nd.node_type for nd in NODE_DEFINITIONS}

REL_TYPE_TO_LABEL: Dict[str, str] = {rt.value: rt.value for rt in RelationshipType}

ENTITY_SUBTYPE_MAP: Dict[str, NodeType] = {
    "DocumentType": NodeType.DOCUMENT_TYPE,
    "RegistrationNumber": NodeType.REGISTRATION_NUMBER,
    "ContractType": NodeType.CONTRACT_TYPE,
    "StartDate": NodeType.START_DATE,
    "EndDate": NodeType.END_DATE,
    "UntilFullPerformance": NodeType.UNTIL_FULL_PERFORMANCE,
    "StandardContract": NodeType.STANDARD_CONTRACT,
    "BusinessPartner": NodeType.BUSINESS_PARTNER,
    "Supplier": NodeType.SUPPLIER,
    "Contractor": NodeType.CONTRACTOR,
    "PerformerExecutor": NodeType.PERFORMER_EXECUTOR,
    "StructureUnit": NodeType.STRUCTURE_UNIT,
    "Subject": NodeType.SUBJECT,
    "AmountWithVAT": NodeType.AMOUNT_WITH_VAT,
    "AmountWithoutVAT": NodeType.AMOUNT_WITHOUT_VAT,
    "VATRate": NodeType.VAT_RATE,
    "VATAmount": NodeType.VAT_AMOUNT,
    "PaymentForm": NodeType.PAYMENT_FORM,
    "ContractCurrency": NodeType.CONTRACT_CURRENCY,
    "KASUDID": NodeType.KASUD_ID,
    "PaymentTerms": NodeType.PAYMENT_TERMS,
    "BusinessUnit": NodeType.BUSINESS_UNIT,
    "CustomerClient": NodeType.CUSTOMER_CLIENT,
    "Buyer": NodeType.BUYER,
    "Project": NodeType.PROJECT,
    "InvestmentProjectCode": NodeType.INVESTMENT_PROJECT_CODE,
    "FrameContract": NodeType.FRAME_CONTRACT,
    "Payer": NodeType.PAYER,
    "Recipient": NodeType.RECIPIENT,
    "BudgetItem": NodeType.BUDGET_ITEM,
    "StandardNonStandard": NodeType.STANDARD_NON_STANDARD,
    "ExpenseContract": NodeType.EXPENSE_CONTRACT,
    "RevenueContract": NodeType.REVENUE_CONTRACT,
    "SAPProject": NodeType.SAP_PROJECT,
    "WinParticipant": NodeType.WIN_PARTICIPANT,
    "LotNumber": NodeType.LOT_NUMBER,
    "LotWinner": NodeType.LOT_WINNER,
    "MaterialName": NodeType.MATERIAL_NAME,
    "GoodsProduct": NodeType.GOODS_PRODUCT,
    "SKUArticleNumber": NodeType.SKU_ARTICLE_NUMBER,
    "PositionItem": NodeType.POSITION_ITEM,
    "ENSCode": NodeType.ENS_CODE,
    "Material": NodeType.MATERIAL,
    "UnitOfMeasurement": NodeType.UNIT_OF_MEASUREMENT,
    "Quantity": NodeType.QUANTITY,
    "Volume": NodeType.VOLUME,
    "Cost": NodeType.COST,
    "Price": NodeType.PRICE,
    "DeliveryPeriod": NodeType.DELIVERY_PERIOD,
}
