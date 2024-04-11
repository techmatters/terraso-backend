# We need the ability to specify the base image for the app dockerfile for
# PR specific builds that are not yet merged into the main branch.
# ex: we build terraso_backend_base:PR-1234 for PR 1234 which contains
# the changes to the base image that we want to be sure to test.
ARG TERRASSO_BASE_IMAGE=techmatters/terraso_backend:latest-base
FROM $TERRASSO_BASE_IMAGE

# ==============================================================================
# This is the app dockerfile for deploys to Render and the base for Dockerfile.dev
# ==============================================================================
USER terraso
COPY --chown=terraso:terraso . /app

WORKDIR /app
RUN django-admin compilemessages --locale=es --locale=en