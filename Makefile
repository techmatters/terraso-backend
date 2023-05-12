DC_ENV ?= dev
DC_FILE_ARG = -f docker-compose.$(DC_ENV).yml
DC_RUN_CMD = docker compose $(DC_FILE_ARG) run --quiet-pull --rm web

SCHEMA_BUILD_CMD = $(DC_RUN_CMD) python terraso_backend/manage.py graphql_schema --schema apps.graphql.schema.schema --out=-.graphql
SCHEMA_BUILD_FILE = terraso_backend/apps/graphql/schema/schema.graphql
api_schema: check_rebuild
	$(SCHEMA_BUILD_CMD) > $(SCHEMA_BUILD_FILE)

check_api_schema: check_rebuild
	$(SCHEMA_BUILD_CMD) | diff $(SCHEMA_BUILD_FILE) -

api_docs: api_schema
	npx spectaql --one-file --target-file=docs.html --target-dir=terraso_backend/apps/graphql/templates/ terraso_backend/apps/graphql/spectaql.yml

backup: build_backup_docker_image
	@docker run --rm --env-file --mount type=bind,source=backup/url_rewrites.conf,destination=/etc/terraso/url_rewrites.conf,readonly backup/.env techmatters/terraso_backend

build_base_image:
	docker build --tag=techmatters/terraso_backend --file=Dockerfile .

build: build_base_image
	docker compose $(DC_FILE_ARG) build

check_rebuild:
	./scripts/rebuild.sh

clean:
	@find . -name *.pyc -delete
	@find . -name __pycache__ -delete

createsuperuser: check_rebuild
	$(DC_RUN_CMD) python terraso_backend/manage.py createsuperuser

format: ${VIRTUAL_ENV}/scripts/black ${VIRTUAL_ENV}/scripts/isort
	isort -rc --atomic terraso_backend
	black terraso_backend

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

lint: check_api_schema
	flake8 terraso_backend && isort -c terraso_backend

lock: pip-tools
	CUSTOM_COMPILE_COMMAND="make lock" pip-compile --upgrade --generate-hashes --output-file requirements.txt requirements/base.in requirements/deploy.in

lock-dev: pip-tools
	CUSTOM_COMPILE_COMMAND="make lock-dev" pip-compile --upgrade --generate-hashes --output-file requirements-dev.txt requirements/dev.in

migrate: check_rebuild
	$(DC_RUN_CMD) python terraso_backend/manage.py migrate --no-input

makemigrations: check_rebuild
	$(DC_RUN_CMD) python terraso_backend/manage.py makemigrations

print_migration_sql: check_rebuild
	$(DC_RUN_CMD) python terraso_backend/manage.py sqlmigrate $(APP_MIGRATION_NAME)

compile-translations:
	$(DC_RUN_CMD) django-admin compilemessages --locale=es --locale=en

generate-translations:
	$(DC_RUN_CMD) python terraso_backend/manage.py makemessages --locale=es --locale=en

translate: generate-translations compile-translations

pip-tools: ${VIRTUAL_ENV}/scripts/pip-sync

setup-git-hooks:
	@cp scripts/pre-commit.sample .git/hooks/pre-commit
	@cp scripts/commit-msg.sample .git/hooks/commit-msg
	@echo "git hooks installed"

pre-commit: lint

run:
	@./scripts/docker.sh "$(DC_FILE_ARG)"

setup: build setup-pre-commit

start-%:
	@docker compose $(DC_FILE_ARG) up -d $(@:start-%=%)

stop:
	@docker compose $(DC_FILE_ARG) stop

test: clean check_rebuild compile-translations
	if [ -z "$(PATTERN)" ]; then \
		$(DC_RUN_CMD) pytest terraso_backend; \
	else \
		$(DC_RUN_CMD) pytest terraso_backend -k $(PATTERN); \
	fi

test-ci: clean
	# Same action as 'test' but avoiding to create test cache
	$(DC_RUN_CMD) pytest -p no:cacheprovider terraso_backend

bash:
	$(DC_RUN_CMD) bash

${VIRTUAL_ENV}/scripts/black:
	pip install black

${VIRTUAL_ENV}/scripts/isort:
	pip install isort

${VIRTUAL_ENV}/scripts/pip-sync:
	pip install pip-tools
