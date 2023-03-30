api_docs:
	npx spectaql --one-file --target-file=docs.html --target-dir=terraso_backend/apps/graphql/templates/ terraso_backend/apps/graphql/spectaql.yml

backup: build_backup_docker_image
	@docker run --rm --env-file --mount type=bind,source=backup/url_rewrites.conf,destination=/etc/terraso/url_rewrites.conf,readonly backup/.env techmatters/terraso_backend

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
	flake8 terraso_backend && isort -c terraso_backend

lock: pip-tools
	CUSTOM_COMPILE_COMMAND="make lock" pip-compile --upgrade --generate-hashes --output-file requirements.txt requirements/base.in requirements/deploy.in

lock-dev: pip-tools
	CUSTOM_COMPILE_COMMAND="make lock-dev" pip-compile --upgrade --generate-hashes --output-file requirements-dev.txt requirements/dev.in

migrate: check_rebuild
	./scripts/run.sh python terraso_backend/manage.py migrate --no-input

makemigrations: check_rebuild
	./scripts/run.sh python terraso_backend/manage.py makemigrations

compile-translations:
	./scripts/run.sh python terraso_backend/manage.py compilemessages --locale=es --locale=en

generate-translations:
	./scripts/run.sh python terraso_backend/manage.py makemessages --locale=es --locale=en

translate: generate-translations compile-translations

pip-tools: ${VIRTUAL_ENV}/scripts/pip-sync

setup-git-hooks:
	@cp scripts/pre-commit.sample .git/hooks/pre-commit
	@cp scripts/commit-msg.sample .git/hooks/commit-msg
	@echo "git hooks installed"

pre-commit: lint

run:
	@./scripts/docker.sh

setup: build setup-pre-commit

start-%:
	@docker-compose up -d $(@:start-%=%)

stop:
	@docker-compose stop

test: clean check_rebuild compile-translations
	./scripts/run.sh pytest terraso_backend

test-ci: clean
	# Same action as 'test' but avoiding to create test cache
	./scripts/run.sh pytest -p no:cacheprovider terraso_backend


${VIRTUAL_ENV}/scripts/black:
	pip install black

${VIRTUAL_ENV}/scripts/isort:
	pip install isort

${VIRTUAL_ENV}/scripts/pip-sync:
	pip install pip-tools
