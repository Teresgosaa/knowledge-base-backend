import ssl
import os
import sys

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"

import requests

# ── Yandex Cloud credentials ──────────────────────────────────────────────────
YANDEX_FOLDER = "b1gi8sjb7ua7mbeg9iii"
YANDEX_API_KEY = "***REMOVED***"
YANDEX_MODEL = "yandexgpt/latest"
YANDEX_OAUTH = "***REMOVED_OAUTH***"

WORKING_DIR = r"C:\Users\anastasia.glazunova\Downloads\knowledge-base-backend\knowledge-base-backend\raganything_workspace"


def fetch_iam_token() -> str:
    resp = requests.post(
        "https://iam.api.cloud.yandex.net/iam/v1/tokens",
        json={"yandexPassportOauthToken": YANDEX_OAUTH},
        timeout=30,
        verify=False,
    )
    resp.raise_for_status()
    return resp.json()["iamToken"]


if __name__ == "__main__":
    print("Получаем IAM токен...")
    iam_token = fetch_iam_token()
    print("IAM токен получен")

    # Настраиваем через переменные окружения — parse_args() их подхватит
    os.environ["WORKING_DIR"] = WORKING_DIR
    os.environ["INPUT_DIR"] = WORKING_DIR

    # LLM: OpenAI-совместимый эндпоинт Яндекса, IAM-токен работает через Bearer
    os.environ["LLM_BINDING"] = "openai"
    os.environ["LLM_BINDING_HOST"] = "https://ai.api.cloud.yandex.net/v1"
    os.environ["LLM_BINDING_API_KEY"] = iam_token
    os.environ["LLM_MODEL"] = f"gpt://{YANDEX_FOLDER}/{YANDEX_MODEL}"

    # Embedding: тот же хост (для инициализации хранилища достаточно)
    os.environ["EMBEDDING_BINDING"] = "openai"
    os.environ["EMBEDDING_BINDING_HOST"] = "https://ai.api.cloud.yandex.net/v1"
    os.environ["EMBEDDING_BINDING_API_KEY"] = iam_token
    os.environ["EMBEDDING_MODEL"] = f"emb://{YANDEX_FOLDER}/text-search-doc/latest"
    os.environ["EMBEDDING_DIM"] = "256"

    # Хранилища — те же, что в бэкенде
    os.environ["LIGHTRAG_KV_STORAGE"] = "JsonKVStorage"
    os.environ["LIGHTRAG_GRAPH_STORAGE"] = "Neo4JStorage"
    os.environ["LIGHTRAG_VECTOR_STORAGE"] = "QdrantVectorDBStorage"
    os.environ["LIGHTRAG_DOC_STATUS_STORAGE"] = "JsonDocStatusStorage"

    # Neo4j и Qdrant
    os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
    os.environ.setdefault("NEO4J_USERNAME", "neo4j")
    os.environ.setdefault("NEO4J_PASSWORD", "mashunia")
    os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

    os.environ["SUMMARY_LANGUAGE"] = "Russian"

    # parse_args() смотрит на sys.argv — передаём пустые аргументы
    sys.argv = ["lightrag-server"]

    from lightrag.api.config import parse_args
    from lightrag.api.lightrag_server import create_app
    import uvicorn

    args = parse_args()
    app = create_app(args)

    print("Веб-интерфейс запущен: http://localhost:9621")
    uvicorn.run(app, host="0.0.0.0", port=9621)
