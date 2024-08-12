# Use the official Python 3.11 image from Docker Hub
FROM python:3.11

# Set the working directory in the Docker container
WORKDIR /app

# Poetry env inside app
ENV POETRY_CACHE_DIR=/app/poetry_cache

# Copy the Python dependencies file and the Poetry configuration files
COPY pyproject.toml poetry.lock* /app/

# Copy your Google Cloud service key
COPY ./keyfile.json /app/keyfile.json
COPY ./token.json /app/token.json
COPY ./config.yml /app/config.yml

# Install poetry
RUN pip install --no-cache-dir poetry


# Install the project dependencies defined in pyproject.toml and poetry.lock
RUN poetry install --no-dev  # Skip development dependencies if present

# Copy the source code into the container
COPY ./src /app/src/
COPY ./logs /app/logs/
COPY ./data/price_catalogues /app/data/price_catalogues/

# By default, run your application using the Python command that calls your app.
# For example, if your main script is `src/main.py`, you can use:
# CMD ["python", "src/main.py"]

# Adjust CMD as per your application's entry point
CMD ["python", "src/app.py"]
