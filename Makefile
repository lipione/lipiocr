.PHONY: backend-install backend-dev backend-test frontend-install frontend-dev frontend-test frontend-build compose-build compose-up compose-down remote-sync test

backend-install:
	cd backend && python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip && .venv/bin/python -m pip install -e '.[test]'

backend-dev:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8010

backend-test:
	cd backend && .venv/bin/python -m pytest -q

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && NEXT_PUBLIC_API_BASE_URL=http://localhost:8010 npm run dev

frontend-test:
	cd frontend && npm run test

frontend-build:
	cd frontend && npm run lint && npm run build

test: backend-test frontend-test frontend-build

compose-build:
	cd infra && docker compose build

compose-up:
	cd infra && docker compose --env-file .env up -d

compose-down:
	cd infra && docker compose --env-file .env down

remote-sync:
	rsync -az --delete \
		--exclude '.git' \
		--exclude 'backend/.venv' \
		--exclude 'backend/.pytest_cache' \
		--exclude 'backend/lipiocr_backend.egg-info' \
		--exclude 'frontend/node_modules' \
		--exclude 'frontend/.next' \
		--exclude 'infra/.env' \
		--exclude 'storage' \
		-e 'ssh -i ~/.ssh/lipiocr_codex_ed25519 -p 41447' \
		./ ekduiteen@202.51.2.50:/data/lipiocr/
