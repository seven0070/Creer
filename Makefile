.PHONY: help backend-install backend-test backend-run extension-install extension-compile extension-package smoke doctor docker-up docker-down certs check

help:
	@echo "Creer make targets:"
	@echo "  make backend-install   pip install backend deps"
	@echo "  make backend-test      pytest"
	@echo "  make backend-run       uvicorn on :8000"
	@echo "  make extension-install npm ci in extension/"
	@echo "  make extension-compile typecheck + esbuild bundle"
	@echo "  make extension-package build creer-*.vsix"
	@echo "  make smoke             API smoke (backend must be up)"
	@echo "  make doctor            curl /doctor"
	@echo "  make docker-up         docker compose up --build"
	@echo "  make docker-down       docker compose down"
	@echo "  make certs             generate local mTLS certs"
	@echo "  make check             backend-test + extension-compile"

backend-install:
	cd backend && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt

backend-test:
	cd backend && PYTHONPATH=. CREER_OFFLINE=1 ./venv/bin/python -m pytest tests/ -q

backend-run:
	cd backend && PYTHONPATH=. ./venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000

extension-install:
	cd extension && npm ci

extension-compile:
	cd extension && npm run compile

extension-package:
	cd extension && npm run package

smoke:
	./scripts/smoke.sh

doctor:
	curl -sf "$${CREER_URL:-http://127.0.0.1:8000}/doctor" | python3 -m json.tool

docker-up:
	docker compose up --build

docker-down:
	docker compose down

certs:
	./scripts/gen-dev-certs.sh

check: backend-test extension-compile
