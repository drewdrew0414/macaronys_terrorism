.PHONY: install dev local-worker compose-up compose-down compile test

install:
	python3 -m pip install -r requirements.txt

dev:
	python3 app.py

local-worker:
	python3 app.py local-worker

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

compile:
	python3 -m py_compile app.py $$(find macaronys_backend -name '*.py' -print)

test:
	python3 -m pytest
