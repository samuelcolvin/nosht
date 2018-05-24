.DEFAULT_GOAL := all

.PHONY: install
install:
	pip install -r tests/requirements.txt
	pip install -r src/requirements.txt
	pip install -U aiohttp-devtools docker-compose

.PHONY: isort
isort:
	isort -rc -w 120 -sg */run.py src
	isort -rc -w 120 tests

.PHONY: lint
lint:
	flake8 src/ tests/
	pytest src -p no:sugar -q --cache-clear
	cd js; yarn lint; cd ..

.PHONY: test
test:
	pytest --cov=src

.PHONY: testcov
testcov: test
	coverage html

.PHONY: all
all: testcov lint

.PHONY: docker-dev
docker-dev:
	@echo "running locally for development and testing"
	@echo "You'll want to run docker-logs in anther window see what's going on"
	@echo "================================================================================"
	@echo ""
	@echo "running docker compose..."
	docker-compose up -d --build

.PHONY: build-web
build-web:
	docker build . -t nosht-web

.PHONY: build-worker
build-worker:
	docker build . -t nosht-worker --build-arg MODE=worker

.PHONY: other
other: build-web build-worker
	docker tag nosht-web registry.heroku.com/nosht/web
	docker tag nosht-worker registry.heroku.com/nosht/worker
	@# TODO this isn't atomic, can we make it atomic without using two dockerfiles?
	docker push registry.heroku.com/nosht/web
	docker push registry.heroku.com/nosht/worker
