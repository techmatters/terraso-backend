IMAGE_ORG ?= techmatters
IMAGE_NAME ?= terraso-backend
IMAGE ?= $(IMAGE_ORG)/$(IMAGE_NAME)

IMAGE_TAG ?= latest

APP_IMAGE_TAG ?= $(IMAGE_TAG)
APP_IMAGE ?= $(IMAGE):$(APP_IMAGE_TAG)
APP_BUILD_ARGS ?= --build-arg TERRASSO_BASE_IMAGE=$(BASE_IMAGE)
APP_ARGS ?= -t $(APP_IMAGE) $(APP_BUILD_ARGS) -f ./Dockerfile ./
APP_PUSH_ARGS ?= $(APP_ARGS)

BASE_IMAGE_TAG ?= $(IMAGE_TAG)-base
BASE_IMAGE ?= $(IMAGE):$(BASE_IMAGE_TAG)
BASE_ARGS ?= -t $(BASE_IMAGE) -f ./Dockerfile.base ./
BASE_PUSH_ARGS ?= $(BASE_ARGS)

DEV_IMAGE_TAG ?= $(IMAGE_TAG)-dev
DEV_IMAGE = $(IMAGE):$(DEV_IMAGE_TAG)
DEV_BUILD_ARGS ?= --build-arg TERRASSO_APP_IMAGE=$(APP_IMAGE)
DEV_ARGS ?= -t $(DEV_IMAGE) $(DEV_BUILD_ARGS) -f ./Dockerfile.dev ./
DEV_PUSH_ARGS ?= $(DEV_ARGS)

PLATFORMS ?= linux/amd64,linux/arm64
PLATFORM_ARG = --platform $(PLATFORMS)

DOCKER_BUILD_CMD = DOCKER_BUILDKIT=1 docker build
DOCKER_PUSH_CMD = docker buildx build --push $(PLATFORM_ARG)

build_app:
	$(DOCKER_BUILD_CMD) $(APP_ARGS)

build_base:
	 $(DOCKER_BUILD_CMD) $(BASE_ARGS)

build_dev:
	$(DOCKER_BUILD_CMD) $(DEV_ARGS)

build: build_base build_app build_dev

push_app:
	$(DOCKER_PUSH_CMD) $(APP_PUSH_ARGS)

push_base:
	$(DOCKER_PUSH_CMD) $(BASE_PUSH_ARGS)

push_dev:
	$(DOCKER_PUSH_CMD) $(DEV_PUSH_ARGS)

push: push_base push_app push_dev