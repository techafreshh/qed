.PHONY: dev test

dev:
	python3 -m uvicorn app.main:app --reload --port 8000

test:
	python3 -m pytest -q
