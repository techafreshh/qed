.PHONY: dev test build-ui

dev:
	python3 -m uvicorn app.main:app --reload --port 8000

test:
	python3 -m pytest -q

build-ui:
	@if command -v npm >/dev/null 2>&1; then \
		(cd ui && (npm ci || npm install) && npm run build); \
	else \
		echo "npm not found; using checked-in fallback bundle"; \
	fi
	@test -f app/static/index.html && echo "ui bundle ready: app/static/index.html"
