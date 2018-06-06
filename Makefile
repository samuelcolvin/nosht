.DEFAULT_GOAL := all

.PHONY: install
install:
	pip install -r py/tests/requirements.txt
	pip install -r py/requirements.txt
	pip install -U ipython aiohttp-devtools docker-compose

.PHONY: isort
isort:
	isort -rc -w 120 py

.PHONY: lint
lint:
	flake8 py
	pytest -p no:sugar -q --cache-clear --isort py
	cd js; yarn lint; cd ..

.PHONY: test
test:
	pytest py --cov=py --cov-config py/setup.cfg

.PHONY: testcov
testcov: test
	coverage html --rcfile=py/setup.cfg

.PHONY: all
all: testcov lint

.PHONY: build
build:
	@ # this makes sure build will work even if the deploy-settings directory doesn't exist
	mkdir -p deploy-settings/favicons
	touch deploy-settings/env.production
	touch deploy-settings/favicons/favicon-16x16.png
	docker build . -f Dockerfile.web -t nosht-web
	docker build . -f Dockerfile.worker -t nosht-worker --quiet

.PHONY: docker-dev
docker-dev: build
	# ================================================================================
	# running locally for development and testing
	# You'll want to run docker-logs in anther window see what's going on
	# ================================================================================
	#
	# running docker compose...
	docker-compose up -d

.PHONY: heroku-release
heroku-push: build
	docker tag nosht-web registry.heroku.com/nosht/web
	docker push registry.heroku.com/nosht/web
	docker tag nosht-worker registry.heroku.com/nosht/worker
	docker push registry.heroku.com/nosht/worker

.PHONY: heroku-release
heroku-release:
	heroku container:release web worker -a nosht

.PHONY: heroku-pgcli
heroku-pgcli:
	pgcli `heroku config:get DATABASE_URL -a nosht`
