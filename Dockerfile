ARG TERRASSO_BASE_IMAGE=techmatters/terraso_backend_base:latest
FROM $TERRASSO_BASE_IMAGE

# ==============================================================================
# This is the base dockerfile for deploys to Render and as a base for Dockerfile.dev
# ==============================================================================

# There isn't a great way to DRY this out becuase of the way Render deploys,
# any changes here should be duplicated in ./Dockerfile.staging

USER terraso
COPY --chown=terraso:terraso . /app

WORKDIR /app
RUN django-admin compilemessages --locale=es --locale=en