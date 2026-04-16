.PHONY: install lint format typecheck test up down logs crawl

install:
	python -m pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check .
	black --check .

format:
	ruff check --fix .
	black .

typecheck:
	mypy lead_pipeline

test:
	pytest

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=100

crawl:
	docker compose run --rm crawler scrapy crawl market_intel -a start_url=$(URL)
