<div align="center">

# Estima

**Оценка рыночной стоимости квартиры, дома или участка в пару кликов**

Выберите адрес, укажите параметры, и модель машинного обучения оценит цену<br>по тысячам реальных объявлений о продаже

[![Попробовать](https://img.shields.io/badge/Попробовать-estima-2F6BFF?style=for-the-badge)](https://estima-frontend-six.vercel.app/)
[![Swagger](https://img.shields.io/badge/API-Swagger-85EA2D?style=for-the-badge&logo=swagger&logoColor=black)](https://estima-backend.onrender.com/docs)

[![CI](https://github.com/welldanov/estima-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/welldanov/estima-backend/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![CatBoost](https://img.shields.io/badge/CatBoost-FFCC00)

</div>

![Выбор адреса, параметры квартиры и результат оценки](docs/screenshot.png)

<sub>Бэкенд работает на бесплатном Render и засыпает без запросов, поэтому первая оценка может занять до минуты.</sub>

## Что умеет

- **Понимает адреса**: подсказки и геокодинг через Yandex Maps, как в привычных картах.
- **Два города**: Казань (квартиры) и Альметьевск (квартиры, дома, участки).
- **Честно говорит о точности**: если адрес на окраине или указан без номера дома, оценка помечается как приблизительная, а слишком далёкие адреса модель не оценивает вовсе.
- **Бережёт квоту**: суточный лимит запросов к Yandex не даёт сервису упереться в платный тариф.

## Насколько точно

В половине случаев оценка квартиры ошибается меньше чем на **7.7 %**. Для квартиры за 8 млн ₽ это около 600 тыс. ₽.

| | Объявлений в обучении | Ошибка модели | Ошибка «по средней цене м²» |
|---|---:|---:|---:|
| Квартиры | 18 506 | **7.7 %** | 18.9 % |
| Участки | 523 | **22.2 %** | 46.3 % |
| Дома | 431 | **31.8 %** | 34.4 % |

<sub>Медианная процентная ошибка на отложенной выборке. Дома и участки пока оцениваются грубее: объявлений по ним в десятки раз меньше.</sub>

## Как это работает

```mermaid
flowchart LR
    A[~23 000 объявлений] --> B[Очистка и разбор]
    B --> C[(SQLite)]
    C --> D[Признаки]
    D --> E[3 модели CatBoost]
    E --> F[FastAPI]
    G[Yandex Maps] --> F
    F --> H[Веб-клиент]
```

Самое интересное под капотом:

- **Чистые данные.** Заголовки объявлений разбираются по строгому формату, а доли, апартаменты, аукционы и квартиры «8 м² на 4 комнаты» отсекаются ещё на импорте.
- **Без утечек в оценке качества.** Переподанные объявления схлопываются в одно, а тестовая выборка делится по зданиям: квартиры одного дома не попадают одновременно в обучение и в проверку.
- **География как признак.** Учитываются расстояние до центра города и до ближайшей станции метро.
- **Модель не молчит об ошибках.** Несовместимая с кодом модель, незнакомый город или тип объекта дают явную ошибку, а не тихий неверный прогноз.

## Стек

| | |
|---|---|
| **Backend** | ![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white) ![Pydantic](https://img.shields.io/badge/Pydantic-E92063?logo=pydantic&logoColor=white) ![httpx](https://img.shields.io/badge/httpx-3F4F75) |
| **ML** | ![CatBoost](https://img.shields.io/badge/CatBoost-FFCC00) ![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white) ![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?logo=scikitlearn&logoColor=white) ![NumPy](https://img.shields.io/badge/NumPy-013243?logo=numpy&logoColor=white) |
| **Данные** | ![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white) ![Yandex Maps API](https://img.shields.io/badge/Yandex_Maps_API-FC3F1D) |
| **Инфраструктура** | ![uv](https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=white) ![pytest](https://img.shields.io/badge/pytest-0A9EDC?logo=pytest&logoColor=white) ![Ruff](https://img.shields.io/badge/Ruff-D7FF64?logo=ruff&logoColor=black) ![mypy](https://img.shields.io/badge/mypy-2A6DB2) ![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?logo=githubactions&logoColor=white) ![Render](https://img.shields.io/badge/Render-000000?logo=render&logoColor=white) |

## Запустить у себя

<details>
<summary>Показать инструкцию</summary>

Нужны [uv](https://docs.astral.sh/uv/) и ключи Yandex Geosuggest и Geocoder.

```bash
uv sync
cp .env.example .env    # вписать ключи Yandex
uv run uvicorn estima_backend.api.main:app --reload
```

Swagger откроется на http://localhost:8000/docs.

Пересобрать базу и переобучить модели:

```bash
uv run python -m estima_backend.ingestion.importer data/raw/avito --rebuild
uv run python scripts/train.py
```

Тесты и линтеры (то же самое запускает CI на каждый pull request):

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

</details>
