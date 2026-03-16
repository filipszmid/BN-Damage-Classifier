FROM python:3.11

#WORKDIR /

ENV POETRY_CACHE_DIR=/poetry_cache

COPY pyproject.toml poetry.lock* README.md /

COPY ./src /src/
COPY ./interface /interface/
COPY ./.streamlit /.streamlit/

RUN pip install --no-cache-dir poetry

RUN poetry install # --only dev  # Skip development dependencies if present


RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY data/cma/price_catalogues /data/cma/price_catalogues/
COPY data/cma/model/run_20240823-014941_grindable data/cma/model/run_20240823-014941_grindable


CMD ["python", "-m", "uvicorn", "interface.rest_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
