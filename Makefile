.PHONY: api-install api-dev api-test api-lint db-migrate verify-production web-install web-dev web-build check

api-install:
	python -m pip install -e "services/api[dev]"

api-dev:
	uvicorn gridrecall_api.main:app --app-dir services/api/src --reload

api-test:
	pytest services/api/tests

api-lint:
	ruff check services/api

db-migrate:
	python -m gridrecall_api.migrations

verify-production:
	python -m gridrecall_api.verify_production

web-install:
	npm --prefix apps/dashboard install

web-dev:
	npm --prefix apps/dashboard run dev

web-build:
	npm --prefix apps/dashboard run build

check: api-lint api-test web-build
