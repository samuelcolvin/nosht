.DEFAULT_GOAL := all

.PHONY: install
install:
	pip install -r tests/requirements.txt
	pip install -r py/requirements.txt
	pip install -U aiohttp-devtools docker-compose

.PHONY: isort
isort:
	isort -rc -w 120 -sg */run.py py
	isort -rc -w 120 tests

.PHONY: lint
lint:
	flake8 py/ tests/
	pytest py -p no:sugar -q --cache-clear
	cd js; yarn lint; cd ..

.PHONY: test
test:
	pytest --cov=py

.PHONY: testcov
testcov: test
	coverage html

.PHONY: all
all: testcov lint

.PHONY: build
build:
	docker build . -f Dockerfile.web -t nosht-web --quiet
	docker build . -f Dockerfile.worker -t nosht-worker --quiet

.PHONY: docker-dev
docker-dev: build
	@echo "running locally for development and testing"
	@echo "You'll want to run docker-logs in anther window see what's going on"
	@echo "================================================================================"
	@echo ""
	@echo "running docker compose..."
	docker-compose up -d

.PHONY: deploy
deploy:
	heroku container:push web worker --recursive --app nosht
