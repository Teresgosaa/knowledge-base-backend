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


NON_SEMANTIC_NODE_TYPES: set[NodeType] = {
    NodeType.DOCUMENT,
    NodeType.DOCUMENT_VERSION,
    NodeType.CLAUSE,
    NodeType.TEXT_UNIT,
    NodeType.REFERENCE,
    NodeType.FINDING,
    NodeType.BUSINESS_OBJECT,
}


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
    uses_semantic_source: bool = False
    uses_semantic_target: bool = False


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
        node_types=[],
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
        source_types=[],
        target_types=[NodeType.CLAUSE],
        description="Сущность упомянута в пункте",
        uses_semantic_source=True,
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
    RelationshipDef(
        rel_type=RelationshipType.SUPPORTED_BY,
        source_types=[NodeType.FINDING],
        target_types=[NodeType.CLAUSE, NodeType.TEXT_UNIT, NodeType.BUSINESS_OBJECT],
        description="Находка подкрепляется пунктом/текстом/объектом",
    ),
]
