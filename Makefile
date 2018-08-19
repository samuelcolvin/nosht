.DEFAULT_GOAL:=all
HEROKU_APP?=nosht

.PHONY: install
install:
	pip install -r py/tests/requirements.txt
	pip install -r py/requirements.txt
	pip install -r py/requirements-dev.txt

.PHONY: isort
isort:
	isort -rc -w 120 py

.PHONY: lint
lint:
	flake8 py
	pytest -p no:sugar -q --cache-clear --isort py --ignore=py/tests
	./py/tests/check_debug.sh
	cd js; yarn lint; cd ..

.PHONY: test
test:
	mkdir -p js/build
	pytest py/tests --cov=py --cov-config py/setup.cfg --isort py/tests

.PHONY: testjs
testjs:
	cd js; CI=1 yarn test --coverage; cd ..

.PHONY: testcov
testcov: test
	coverage html --rcfile=py/setup.cfg

.PHONY: all
all: testcov lint

.PHONY: build
build: COMMIT=$(shell git rev-parse HEAD)
build:
	@ # this makes sure build will work even if the deploy-settings directory doesn't exist
	mkdir -p deploy-settings-$(HEROKU_APP)/favicons
	touch deploy-settings-$(HEROKU_APP)/.env.production
	touch deploy-settings-$(HEROKU_APP)/favicons/favicon-16x16.png
	docker build . -f docker/Dockerfile.base -t nosht-python-build
	docker build . -f docker/Dockerfile.web -t nosht-web \
		--build-arg COMMIT=$(COMMIT) --build-arg HEROKU_APP=$(HEROKU_APP)
	docker build . -f docker/Dockerfile.worker -t nosht-worker --quiet \
		--build-arg COMMIT=$(COMMIT) --build-arg HEROKU_APP=$(HEROKU_APP)

.PHONY: docker-dev
docker-dev: build
	# ================================================================================
	# running locally for development and testing
	# You'll want to run docker-logs in anther window see what's going on
	# ================================================================================
	#
	# running docker compose...
	docker-compose -f docker/docker-compose.yml up -d

.PHONY: docker-dev-stop
docker-dev-stop:
	docker-compose -f docker/docker-compose.yml stop

.PHONY: dev-pgcli
dev-pgcli:
	pgcli postgres://postgres:docker@localhost:54320/nosht

.PHONY: heroku-release
heroku-push: build
	docker tag nosht-web registry.heroku.com/$(HEROKU_APP)/web
	docker push registry.heroku.com/$(HEROKU_APP)/web
	docker tag nosht-worker registry.heroku.com/$(HEROKU_APP)/worker
	docker push registry.heroku.com/$(HEROKU_APP)/worker

.PHONY: heroku-release
heroku-release:
	heroku container:release web worker -a $(HEROKU_APP)

.PHONY: heroku-pgcli
heroku-pgcli:
	pgcli `heroku config:get DATABASE_URL -a $(HEROKU_APP)`

.PHONY: heroku-set-auth-key
heroku-set-auth-key:
	heroku config:set -a $(HEROKU_APP) \
	 APP_AUTH_KEY=`python -c "from cryptography import fernet;print(fernet.Fernet.generate_key().decode())"`
