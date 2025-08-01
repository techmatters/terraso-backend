DC_ENV ?= dev
DC_FILE_ARG = -f docker-compose.$(DC_ENV).yml
DC_RUN_CMD ?= docker compose $(DC_FILE_ARG) run --quiet-pull --rm web

ifeq ($(DC_ENV),ci)
	UV_FLAGS = "--system"
endif

SCHEMA_BUILD_CMD = $(DC_RUN_CMD) python terraso_backend/manage.py graphql_schema --schema apps.graphql.schema.schema.schema --out=-.graphql
SCHEMA_BUILD_FILE = terraso_backend/apps/graphql/schema/schema.graphql
api_schema:
	$(SCHEMA_BUILD_CMD) > $(SCHEMA_BUILD_FILE)

check_api_schema:
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

format: ${VIRTUAL_ENV}/scripts/ruff
	ruff format terraso_backend

install:
	uv pip install -r requirements.txt $(UV_FLAGS)

install-dev:
	uv pip install -r requirements-dev.txt $(UV_FLAGS)

lint: check_api_schema
	$(DC_RUN_CMD) ruff check terraso_backend
	$(DC_RUN_CMD) ruff format terraso_backend --diff

lock:
	CUSTOM_COMPILE_COMMAND="make lock" uv pip compile --upgrade --generate-hashes --emit-build-options requirements/base.in requirements/deploy.in -o requirements.txt

lock-package:
	CUSTOM_COMPILE_COMMAND="make lock" uv pip compile --upgrade-package $(PACKAGE) --generate-hashes --emit-build-options requirements/base.in requirements/deploy.in -o requirements.txt

lock-dev:
	CUSTOM_COMPILE_COMMAND="make lock-dev" uv pip compile --upgrade --generate-hashes --emit-build-options requirements/dev.in -o requirements-dev.txt

migrate: check_rebuild
	$(DC_RUN_CMD) python terraso_backend/manage.py migrate --no-input $(APP_MIGRATION_NAME)

deploy:
	python terraso_backend/manage.py migrate --no-input
	python terraso_backend/manage.py collectstatic --no-input

makemigrations: check_rebuild
	$(DC_RUN_CMD) python terraso_backend/manage.py makemigrations

showmigrations: check_rebuild
	$(DC_RUN_CMD) python terraso_backend/manage.py showmigrations

print_migration_sql: check_rebuild
	$(DC_RUN_CMD) python terraso_backend/manage.py sqlmigrate $(APP_MIGRATION_NAME)

compile-translations:
	$(DC_RUN_CMD) django-admin compilemessages --locale=es --locale=en

generate-translations:
	$(DC_RUN_CMD) python terraso_backend/manage.py makemessages --locale=es --locale=en

translate: generate-translations compile-translations

generate-test-token:
	$(DC_RUN_CMD) python terraso_backend/manage.py generate_test_token --email $(email)

setup-git-hooks:
	@pre-commit install

run: check_rebuild
	@./scripts/docker.sh "$(DC_FILE_ARG)"

setup: build setup-pre-commit

start-%:
	@docker compose $(DC_FILE_ARG) up -d $(@:start-%=%)

stop:
	@docker compose $(DC_FILE_ARG) stop

test_unit: clean check_rebuild compile-translations
	if [ -z "$(PATTERN)" ]; then \
		$(DC_RUN_CMD) pytest terraso_backend -m "not integration"; \
	else \
		$(DC_RUN_CMD) pytest terraso_backend -m "not integration" -k $(PATTERN); \
	fi

test_integration: clean check_rebuild compile-translations
	if [ -z "$(PATTERN)" ]; then \
		$(DC_RUN_CMD) pytest terraso_backend -m integration; \
	else \
		$(DC_RUN_CMD) pytest terraso_backend -m integration -k $(PATTERN); \
	fi

test: test_unit test_integration

test_ci_unit: clean
	# Same action as 'test' but avoiding to create test cache
	$(DC_RUN_CMD) pytest -p no:cacheprovider terraso_backend -m "not integration"

test_ci_integration: clean
	# Same action as 'test' but avoiding to create test cache
	$(DC_RUN_CMD) pytest -p no:cacheprovider terraso_backend -m integration

connect_db:
	docker compose $(DC_FILE_ARG) exec db psql -U postgres -d terraso_backend

connect_soil_id_db:
	docker compose $(DC_FILE_ARG) exec soil-id-db psql -U postgres -d soil_id

bash:
	$(DC_RUN_CMD) bash

# Download data files needed for soil ID
# They're stored in Google Drive here: https://drive.google.com/drive/folders/1s1jNPyYCHy7FfWAhqmOBDliklzvfnKO_
# We'd like to remove the need for this step, which is tracked upstream here: https://github.com/techmatters/soil-id-algorithm/issues/51
# List of files:
#   1tN23iVe6X1fcomcfveVp4w3Pwd0HJuTe: LandPKS_munsell_rgb_lab.csv
#   1WUa9e3vTWPi6G8h4OI3CBUZP5y7tf1Li: gsmsoilmu_a_us.shx
#   1l9MxC0xENGmI_NmGlBY74EtlD6SZid_a: gsmsoilmu_a_us.shp
#   1asGnnqe0zI2v8xuOszlsNmZkOSl7cJ2n: gsmsoilmu_a_us.sbx
#   185Qjb9pJJn4AzOissiTz283tINrDqgI0: gsmsoilmu_a_us.sbn
#   1P3xl1YRlfcMjfO_4PM39tkrrlL3hoLzv: gsmsoilmu_a_us.prj
#   1K0GkqxhZiVUND6yfFmaI7tYanLktekyp: gsmsoilmu_a_us.dbf
#   1z7foFFHv_mTsuxMYnfOQRvXT5LKYlYFN: SoilID_US_Areas.shz
download-soil-data:
	mkdir -p Data
	cd Data; \
	gdown 1tN23iVe6X1fcomcfveVp4w3Pwd0HJuTe; \
	gdown 1WUa9e3vTWPi6G8h4OI3CBUZP5y7tf1Li; \
	gdown 1l9MxC0xENGmI_NmGlBY74EtlD6SZid_a; \
	gdown 1asGnnqe0zI2v8xuOszlsNmZkOSl7cJ2n; \
	gdown 185Qjb9pJJn4AzOissiTz283tINrDqgI0; \
	gdown 1P3xl1YRlfcMjfO_4PM39tkrrlL3hoLzv; \
	gdown 1K0GkqxhZiVUND6yfFmaI7tYanLktekyp; \
	gdown 1z7foFFHv_mTsuxMYnfOQRvXT5LKYlYFN \

${VIRTUAL_ENV}/scripts/ruff:
	uv pip install ruff
