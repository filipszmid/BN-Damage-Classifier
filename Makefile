.PHONY: up build test venv clean

up:
	docker compose up

build:
	docker compose build --no-cache

test:
	pytest

venv:
	poetry install

clean:
	@echo "Cleaning up .txt, .png, and .webp files in logs/"
	@find logs/ \( -name '*.txt' -o -name '*.png' -o -name '*.webp' \) -exec rm -f {} +
