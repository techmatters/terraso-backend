build_base_image:
	docker build --tag=techmatters/terraso_backend --file=Dockerfile .

build: build_base_image
	docker-compose build

check_rebuild:
	./scripts/rebuild.sh

clean:
	@find . -name *.pyc -delete
	@find . -name __pycache__ -delete

createsuperuser: check_rebuild
	./scripts/run.sh python terraso_backend/manage.py createsuperuser

format: ${VIRTUAL_ENV}/scripts/black ${VIRTUAL_ENV}/scripts/isort
	isort -rc --atomic terraso_backend
	black terraso_backend

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

lint:
	black --check terraso_backend && isort -c terraso_backend

lock: pip-tools
	CUSTOM_COMPILE_COMMAND="make lock" pip-compile --generate-hashes --output-file requirements.txt requirements/base.in requirements/deploy.in

lock-dev: pip-tools
	CUSTOM_COMPILE_COMMAND="make lock-dev" pip-compile --generate-hashes --output-file requirements-dev.txt requirements/dev.in

migrate: check_rebuild
	./scripts/run.sh python terraso_backend/manage.py migrate --no-input

makemigrations: check_rebuild
	./scripts/run.sh python terraso_backend/manage.py makemigrations

pip-tools: ${VIRTUAL_ENV}/scripts/pip-sync

run: check_rebuild
	docker-compose up

setup: lock build

start-%:
	@docker-compose up -d $(@:start-%=%)

stop:
	@docker-compose stop

test: clean check_rebuild
	./scripts/run.sh pytest terraso_backend


${VIRTUAL_ENV}/scripts/black:
	pip install black

${VIRTUAL_ENV}/scripts/isort:
	pip install isort

${VIRTUAL_ENV}/scripts/pip-sync:
	pip install pip-tools
