# Terraso Backend

Terraso backend is a Django project that powers the backend of the Terraso
platform.

## Requirements

-   Docker: version 24 or better
-   Python: 3.12 or better

## Running locally with Docker

Set up your environment file

```sh
$ cp .env.sample .env
```

In the `.env` file

-   set values for `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`based on what you have set up in console.cloud.google.com > APIs & Services > Credentials.

-   set values for `APPLE_CLIENT_ID`, `APPLE_KEY_ID`, `APPLE_TEAM_ID`, `APPLE_PRIVATE_KEY` and based on what you have set up on developer.apple.com > Certificates, Identifiers & Profiles > Keys.

-   set values for `MICROSOFT_CLIENT_ID` and either `MICROSOFT_CLIENT_SECRET` (less secure) or both `MICROSOFT_PRIVATE_KEY` and `MICROSOFT_CERTIFICATE_THUMBPRINT` based on what you have set up on portal.azure.com > App Registrations > [App Name] > Certificates & Secrets

Start building the Docker images (make sure there's `requirements.txt`
file created before building the images):

```sh
$ make build
```

Run the database migrations before the first run:

```sh
$ make migrate
```

Than the run command can be executed:

```sh
$ make run
```

If you want to have a user to access the admin panel, you need to create
it:

```sh
$ make bash
# (inside the web container)
$ python terraso_backend/manage.py createsuperuser
$ exit
```

## Debugging locally with Docker

To debug while running tests, just use regular Python `breakpoint()` and
run the tests normally. Pytest will stop properly on break point giving
you access to the Python debugger.

To debug while using the application locally, it's also possible to use
Python `breakpoint()`. To have access to the Python debugger, you'll
need to attach to the application running container.

So, assuming that the application is running with `make run`:

List the running containers

```sh
$ docker ps
```

Get the id of the web container before next step

```sh
$ docker attach <web-container-id>
```

This will give you access to the web running container

Make the application request call that will pass on breakpoint, like
calling an API or clicking in some button. As soon as the process get to
the break point, the attached shell should open the Python debugger. To
continue the application request processing, just release the debugger.

# Interacting with the database

## Connect to the database

While the database is running (e.g. via `make run`), use:

```sh
make connect_db
```

## Run or rollback a specific migration

You can tell the database to migrate a specific app to a specific number with:

```sh
APP_MIGRATION_NAME="{app_name} {migration_number}" make migrate
```

So to e.g. rollback migration `0014` of the `soil_id` app, you could run:

```sh
APP_MIGRATION_NAME="soil_id 0014" make migrate
```

## Loading sample data

Import sample landscape data (names, descriptions, links):

```sh
$ python terraso_backend/manage.py loaddata sampledata.json
```

Import landscape boundaries geodata:

```sh
$ python terraso_backend/manage.py load_landscapes_geojson --airtable_api_key xxxxx
```

Download Soil ID data:

```sh
$ make download-soil-data
```

## Reset the database

You can reset the database back to its default state:

```sh
$ python terraso_backend/manage.py flush
```

## Backup the database

The contents of the database can be dumped to a JSON file for backup. Optionally, they can also be uploaded to a S3 bucket. This can be activated to be triggered from a button in the Django admin console. See the relevant [README.md](terraso_backend/apps/core/management/README.md) for more details.

## Print migration SQL

You can view the SQL commands that a migration will issue by running

```sh
$ python terraso_backend/manage.py sqlmigrate {app_name} {migration_name}
```

or in Docker using the `make` command

```sh
$ APP_MIGRATION_NAME="{app_name} {migration_name}" make print_migration_sql
```

For example:

```sh
$ APP_MIGRATION_NAME="story_map 0001_initial" make print_migration_sql
```

# Contributing

Before contributing to the project, it's recommended that you set up
your local git running the following command:

```sh
$ make setup-git-hooks
```

This will activate two git hooks to automatically check Python code
style and commit message structure before each commit.

# Dealing with dependencies

It is possible to lock the dependencies to run the project with the
following command

```sh
$ make lock
```

It is also possible to lock development dependencies with:

```sh
$ make lock-dev
```

The lock process creates/updates the files `requirements.txt` and
`requirements-dev.txt`. With these files in place it's possible to
install dependencies running:

```sh
$ make install
```

To install development dependencies run:

```sh
$ make install-dev
```

# Local development

Your local machine needs:

-   Docker
-   Python

`make lock` requires GDAL and Cython:

```sh
$ brew install gdal
```

```sh
$ apt install gdal
```

### cython

```sh
$ pip3 install cython
```

# Generating GraphQL public documentation

The API docs are generated by
[SpectaQL](https://github.com/anvilco/spectaql). So, make sure you
followed their README to have it installed before proceding. Run the
following command to generate the documentation:

```sh
$ make api_doc
```

Enjoy! `;-)`
