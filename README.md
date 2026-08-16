# astros_pipeline

Пайплайн, который скачивает данные о людях, находящихся сейчас в космосе
([open-notify.org/astros.json](http://api.open-notify.org/astros.json)),
складывает их в ClickHouse в сыром виде, парсит средствами самого ClickHouse
и строит поверх готовых данных отчётные модели с помощью dbt.

## Архитектура

```
API (astros.json)
        │
        ▼
  Python loader ──► astros_raw (RAW, ReplacingMergeTree)
                            │
                            ▼  materialized view (парсинг JSON на лету)
                          people (PARSED, ReplacingMergeTree)
                            │
                            ▼  dbt
                       stg_people (view, дедупликация)
                            │
                            ▼
                  craft_crew_summary (table, витрина)
```

Ключевой принцип: **в ClickHouse — только вставки**, никаких `UPDATE`/`DELETE`.
Дедупликация выполняется силами самого ClickHouse (`ReplacingMergeTree` +
`OPTIMIZE`) и явно — в dbt-моделях (на случай, если фоновый merge ещё не прошёл).

## Компоненты

| Сервис        | Что делает                                                      |
|---------------|-------------------------------------------------------------------|
| `clickhouse`  | Хранилище данных (Docker-образ `clickhouse/clickhouse-server`)   |
| `app`         | Python-загрузчик: скачивает JSON и вставляет его в `astros_raw`  |
| `dbt`         | Строит отчётные модели поверх таблицы `people`                   |

## Слои данных в ClickHouse

- **`astros_raw`** — сырой ответ API целиком (одна строка = один JSON-документ),
  движок `ReplacingMergeTree`.
- **`people`** — распарсенные записи (`craft`, `name`, `_inserted_at`), заполняется
  автоматически материализованным представлением `mv_raw_to_people` при каждой
  вставке в `astros_raw`.
- **`stg_people`** (dbt, view) — дедуплицированная версия `people`: для каждой
  пары (`craft`, `name`) берётся самая свежая запись, независимо от того,
  прошёл ли уже фоновый `OPTIMIZE`.
- **`craft_crew_summary`** (dbt, table) — витрина: количество и список людей
  на каждом корабле/станции.

## Обработка ошибок и ретраи (Python loader)

Запросы к API оборачиваются ретраями через `tenacity`:

- HTTP 429 и сетевые ошибки (`RequestException`) — повод для повтора.
- Таймаут между попытками растёт экспоненциально (`wait_exponential`, от 1 до 32 секунд).
- После `API__MAX_RETRIES` (по умолчанию 5) неудачных попыток подряд выбрасывается
  `FetchError`, и загрузка прерывается.

## Требования

- Docker и Docker Compose
- Python 3.12+ (если запускать `loader` или `dbt` вне контейнеров)

## Быстрый старт (всё через Docker)

```bash
docker compose up --build
```

Порядок запуска сервисов:

1. `clickhouse` поднимается и ждёт, пока healthcheck не станет зелёным.
2. `app` применяет миграции (`clickhouse-migrations`) и один раз скачивает
   данные из API, вставляя их в `astros_raw`.
3. `dbt` запускается после успешного завершения `app` и строит модели
   (`dbt run`) поверх уже наполненной `people`.

Проверить результат:

```bash
docker compose exec clickhouse clickhouse-client \
  --user default --password password --database astros_db \
  --query "SELECT * FROM craft_crew_summary"
```

Повторные запуски вручную:

```bash
docker compose run --rm app          # заново скачать данные
docker compose run --rm dbt run      # пересобрать dbt-модели
docker compose run --rm dbt test     # прогнать тесты качества данных
```

## Переменные окружения

Все настройки читаются из `.env` в корне проекта (см. `.env.example`):

```env
API__URL=http://api.open-notify.org/astros.json
API__MAX_RETRIES=5

CLICKHOUSE__HOST=clickhouse
CLICKHOUSE__PORT=8123
CLICKHOUSE__USER=default
CLICKHOUSE__PASSWORD=password
CLICKHOUSE__DB=astros_db
```

`dbt/astros_dbt/profiles.yml` использует те же переменные (`CLICKHOUSE__*`) —
отдельный `.env` для dbt не нужен.


## Тесты

Юнит-тесты для Python-загрузчика (`loader`) лежат в `tests/` и написаны на `pytest`.
Реальные обращения к API и к ClickHouse в тестах замоканы — сеть и поднятая
инфраструктура для их запуска не нужны.

Что покрыто:

- **`test_api.py`** — ретраи при HTTP 429 и сетевых ошибках, экспоненциальный
  backoff, `FetchError` после исчерпания попыток, отсутствие ретраев при успехе.
- **`test_clickhouse_client.py`** — что в ClickHouse уходит только `insert`
  (никаких DML-операций).
- **`test_main.py`** — оркестрация `fetch → client → insert`, отсутствие
  обращения к ClickHouse при ошибке скачивания.
- **`test_settings.py`** — чтение конфигурации из переменных окружения.

Установка и запуск:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

С покрытием кода:

```bash
pytest --cov=loader --cov-report=term-missing
```

dbt-часть своими тестами покрывается отдельно — через `dbt test`
(см. раздел «Быстрый старт» выше), pytest её не проверяет.

## Структура проекта

```
astros_pipeline/
├── docker-compose.yml
├── Dockerfile                    # образ для app
├── entrypoint.sh                 # миграции + запуск loader
├── requirements.txt
├── requirements-dev.txt          # pytest + pytest-cov
├── pytest.ini
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_clickhouse_client.py
│   ├── test_main.py
│   └── test_settings.py
├── .env.example
├── clickhouse/
│   └── migrations/
│       └── 001_init.sql          # astros_raw, people, mv_raw_to_people
├── loader/
│   ├── main.py
│   ├── settings.py
│   ├── clickhouse_client.py
│   └── api/
│       ├── api.py                # запрос к API + ретраи
│       └── exceptions.py
└── dbt/
    ├── Dockerfile                # образ для dbt
    ├── requirements-dbt.txt
    └── astros_dbt/
        ├── dbt_project.yml
        ├── profiles.yml
        ├── packages.yml
        └── models/
            ├── staging/
            │   ├── _sources.yml
            │   ├── _staging.yml
            │   └── stg_people.sql
            └── marts/
                ├── _marts.yml
                └── craft_crew_summary.sql
```