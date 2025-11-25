FROM python:3.11

#WORKDIR /

ENV POETRY_CACHE_DIR=/poetry_cache

COPY pyproject.toml poetry.lock* /

RUN pip install --no-cache-dir poetry

RUN poetry install --no-dev  # Skip development dependencies if present


COPY ./src /src/
COPY data/cma/price_catalogues /data/cma/price_catalogues/
COPY data/cma/model/run_20240823-014941_grindable data/cma/model/run_20240823-014941_grindable


CMD ["python", "src/app.py"]
