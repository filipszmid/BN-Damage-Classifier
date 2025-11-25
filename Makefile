SHELL := /bin/bash

CURRENT_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

export PYTHONPATH := $(CURRENT_DIR):$(PYTHONPATH)
export PYTHONUNBUFFERED := 1

-include .env

_BOLD := $(shell tput -T ansi bold)
_COLS := $(shell tput -T ansi cols)
_DEFAULT := $(shell tput -T ansi sgr0)
_ITALICS := $(shell tput -T ansi sitm)
_BLUE := $(shell tput -T ansi setaf 4)
_CYAN := $(shell tput -T ansi setaf 6)
_GREEN := $(shell tput -T ansi setaf 2)
_MAGENTA := $(shell tput -T ansi setaf 5)
_RED := $(shell tput -T ansi setaf 1)
_YELLOW := $(shell tput -T ansi setaf 3)


.PHONY: help
help:: ## display this help message
	$(info Please use $(_BOLD)make $(_DEFAULT)$(_ITALICS)$(_CYAN)target$(_DEFAULT) where \
	$(_ITALICS)$(_CYAN)target$(_DEFAULT) is one of:)
	@grep --no-filename "^[a-zA-Z]" $(MAKEFILE_LIST) | \
		sort | \
		awk -F ":.*?## " 'NF==2 {printf "$(_CYAN)%-20s$(_DEFAULT)%s\n", $$1, $$2}'

.PHONY: test-vars
test-vars: ## test variables
	@echo "Current dir: ${CURRENT_DIR}"

.PHONY: up
up: ## set up fast api
	docker compose up -d

.PHONY: down
down: ## down services
	docker compose down

.PHONY: build
build: ## build fast api
	docker compose build --no-cache app

.PHONY: test-integration
test-integration: ## run functional integration tests
	poetry run pytest tests/integration_tests

.PHONY: test-unit
test-unit: ## run unit tests
	poetry run pytest tests/unit_tests

.PHONY: venv
venv: ## create poetry virtual environment
	poetry install

.PHONY: clean
clean: ## clean all log files
	@echo "Cleaning up .txt, .png, and .webp files in logs/"
	@find logs/ \( -name '*.txt' -o -name '*.png' -o -name '*.webp' \) -exec rm -f {} +

.PHONY: board
board: ## open training monitoring board
	poetry run tensorboard --logdir=data/cma/model

.PHONY: train
train: ## run training script
	cd src/classifier && poetry run python3 train.py

.PHONY: tune
tune: ## run hyperparameter search
	cd src/classifier && poetry run python3 hyperparameter_tuning.py
