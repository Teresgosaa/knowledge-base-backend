# Инструкция по развёртыванию Knowledge Base

## Репозитории

- **Бэкенд**: https://github.com/Teresgosaa/knowledge-base-backend (ветка `develop`)
- **Фронтенд**: https://github.com/Teresgosaa/knowledge-base-frontend (ветка `develop`)

---

## Шаг 1. Установить необходимые программы

| Программа | Ссылка | Примечание |
|-----------|--------|------------|
| Python 3.12+ | https://python.org | При установке отметить "Add to PATH" |
| Node.js 18+ | https://nodejs.org | |
| PostgreSQL 15+ | https://postgresql.org | Запомнить пароль пользователя `postgres` |
| Neo4j 5 Community | https://neo4j.com/download | Desktop или Community Server |
| Docker Desktop | https://docker.com | Нужен для Qdrant |
| LibreOffice | https://libreoffice.org | Нужен для обработки PPTX в vision-режиме |
| Git | https://git-scm.com | |

---

## Шаг 2. Запустить Qdrant

Открыть PowerShell и выполнить:

```powershell
docker run -d -p 6333:6333 qdrant/qdrant
```

---

## Шаг 3. Настроить бэкенд

### 3.1 Скачать код

```powershell
git clone https://github.com/Teresgosaa/knowledge-base-backend
cd knowledge-base-backend
git checkout develop
```

### 3.2 Создать виртуальное окружение

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3.3 Установить зависимости

```powershell
pip install -e .
pip install pymupdf pypdf python-docx
```

### 3.4 Создать файл с настройками

В Проводнике открыть папку `knowledge-base-backend`, найти файл `.env.example`, скопировать его и переименовать копию в `.env`.

Открыть `.env` в любом текстовом редакторе и заполнить:

```
# База данных PostgreSQL
DATABASE_URL=postgresql://admin:admin@localhost:5432/knowledge_db
DB_POSTGRES_HOST=localhost
DB_POSTGRES_PORT=5432
DB_POSTGRES_NAME=knowledge_db
DB_POSTGRES_USER=admin
DB_POSTGRES_PASSWORD=admin

# Qdrant (векторная база)
QDRANT_URI=http://localhost:6333

# Neo4j (граф знаний)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=ваш_пароль_от_neo4j

# S3 хранилище (Yandex Object Storage)
S3_ACCESS_KEY=ваш_ключ
S3_SECRET_KEY=ваш_секретный_ключ
S3_REGION=ru-central1
S3_BUCKET_NAME=название_бакета
S3_ENDPOINT_URL=https://storage.yandexcloud.net

# Yandex Cloud (для векторных embeddings)
YANDEX_CLOUD_FOLDER=id_папки
YANDEX_CLOUD_OAUTH_TOKEN=ваш_oauth_токен
YANDEX_CLOUD_API_KEY=ваш_api_ключ

# LLM модель (RouterAI или любой OpenAI-совместимый провайдер)
ROUTERAI_API_KEY=ваш_api_ключ
ROUTERAI_BASE_URL=https://routerai.ru/api/v1
ROUTERAI_MODEL=anthropic/claude-sonnet-4.5
```

**Где взять токены Yandex Cloud:**
- OAuth токен: https://oauth.yandex.ru/authorize?response_type=token&client_id=1a6990aa636648e9b2ef855fa7bec2fb
- Folder ID и API ключ: консоль Yandex Cloud → IAM → Сервисные аккаунты

### 3.5 Создать базу данных PostgreSQL

Открыть pgAdmin или psql и выполнить:

```sql
CREATE DATABASE knowledge_db;
CREATE USER admin WITH PASSWORD 'admin';
GRANT ALL PRIVILEGES ON DATABASE knowledge_db TO admin;
```

### 3.6 Важно для Windows: создать ссылку без спецсимволов в пути

Если путь к папке проекта содержит кириллицу, пробелы или тире (`—`), нужно создать символическую ссылку. Открыть **cmd от имени администратора**:

```cmd
mklink /J C:\kb "полный\путь\к\knowledge-base-backend"
```

После этого все команды выполнять из `C:\kb`, а не из оригинальной папки.

### 3.7 Запустить бэкенд

```powershell
cd C:\kb
.venv\Scripts\python.exe -m app
```

Или дважды кликнуть на файл `start.bat` в папке проекта.

Бэкенд запустится на http://localhost:8000

> Таблицы в базе данных создаются автоматически при первом запуске.

---

## Шаг 4. Настроить фронтенд

### 4.1 Скачать код

```powershell
git clone https://github.com/Teresgosaa/knowledge-base-frontend
cd knowledge-base-frontend
git checkout develop
```

### 4.2 Установить зависимости и запустить

```powershell
npm install
npm run dev
```

Фронтенд запустится на http://localhost:5173

---

## Шаг 5. Первый вход

Открыть в браузере http://localhost:5173

- Логин: `admin`
- Пароль: `admin`

---

## Использование

### Структура папок

Файлы должны лежать в **подпапках**, а не напрямую в корневой папке. Каждая подпапка — это отдельный документ или группа документов в графе знаний.

```
Папка (например: "Презентации IBP")
└── Подпапка (например: "IBP офферинг")
    ├── файл1.pptx
    └── файл2.pdf
```

### Порядок работы

1. Создать папку в разделе **Папки**
2. Внутри неё создать подпапку
3. Загрузить документы (PPTX, PDF, DOCX, TXT, MD) в **подпапку**
4. Нажать кнопку обработки на **корневой папке** — она обработает все подпапки внутри
5. Выбрать режим обработки папки. Переключатель — иконка часов рядом с папкой (жёлтая = vision включён, серая = fast):
   - **Fast** (молния) — быстрый режим, извлекает текст напрямую. Подходит для большинства документов
   - **Vision** (часы) — медленный режим, рендерит каждый слайд/страницу как изображение и отправляет в LLM для описания. Используй для презентаций со сложной визуальной структурой: колонки, матрицы, диаграммы, где важно расположение элементов на слайде
6. Дождаться завершения обработки
7. Задать вопрос в разделе **Чат**, выбрав нужную папку для фильтрации

---

## Важные моменты

- **Яндекс IAM токен** живёт 12 часов. Если поиск перестал работать — просто перезапусти бэкенд
- **LLM модель**: по умолчанию Claude Sonnet через RouterAI (~10 сек на ответ). Можно сменить в `.env` на любую другую OpenAI-совместимую модель
- **Qwen3** работает, но отвечает 1-3 минуты из-за встроенного режима "размышления" — это нормально
- **Vision-режим** для PPTX требует LibreOffice установленного по умолчанию в `C:\Program Files\LibreOffice\`
- **Neo4j Community** не поддерживает несколько баз данных — предупреждение в логах об этом не критично, всё работает
