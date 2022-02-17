# Terraso Backend

Terraso backend is a Django project that powers the backend of the Terraso
platform.

## Running locally with Docker

Set up your environment file

```sh
$ cp .env.sample .env
```

In the `.env` file

* set values for `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`based on what you have set up in console.cloud.google.com > APIs & Services > Credentials.

* set values for `APPLE_CLIENT_ID`, `APPLE_KEY_ID`, `APPLE_TEAM_ID`, `APPLE_PRIVATE_KEY` and based on what you have set up on developer.apple.com > Certificates, Identifiers & Profiles > Keys.

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
$ ./scripts/run.sh bash
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

```sh
# List the running containers
$ docker ps
# Get the id of the web container before next step
$ docker attach <web-container-id>
# This will give you access to the web running container
```

Make the application request call that will pass on brak point, like
calling an API or clicking in some button. As soon as the process get to
the break point, the attached shell should open the Python debugger. To
continue the application request processing, just release the debugger.

## Loading sample data

Import sample landscape data (names, descriptions, links):

```sh
$ python terraso_backend/manage.py loaddata sampledata.json
```

Import landscape boundaries geodata:

```sh
$ python terraso_backend/manage.py load_landscapes_geojson --airtable_api_key xxxxx
```

## Reset the database

You can reset the database back to its default state:

```sh
$ python terraso_backend/manage.py flush
```


## Contributing

Before contributing to the project, it's recommended that you set up
your local git running the following command:

```sh
$ make setup-git-hooks
```

This will activate two git hooks to automatically check Python code
style and commit message structure before each commit.

## Dealing with dependencies

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

Enjoy! `;-)`
