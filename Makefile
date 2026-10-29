.PHONY: dev demo-offline test build-ui

dev:
	python3 -m uvicorn app.main:app --reload --port 8000

demo-offline:
	@echo "QED offline demo UI: http://127.0.0.1:8000"
	@echo "POST demo_replicated: curl -X POST http://127.0.0.1:8000/api/runs -H \"Content-Type: application/json\" -d '{\"paper_id\":\"demo_replicated\",\"claim\":\"wages rise\"}'"
	@echo "POST demo_failed: curl -X POST http://127.0.0.1:8000/api/runs -H \"Content-Type: application/json\" -d '{\"paper_id\":\"demo_failed\",\"claim\":\"wages rise\"}'"
	QED_OFFLINE=1 python3 -m uvicorn app.main:app --port 8000

test:
	python3 -m pytest -q

build-ui:
	@if command -v npm >/dev/null 2>&1; then \
		(cd ui && (npm ci || npm install) && npm run build); \
	else \
		echo "npm not found; using checked-in fallback bundle"; \
	fi
	@test -f app/static/index.html && echo "ui bundle ready: app/static/index.html"
