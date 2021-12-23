# Terraso Backend

Terraso backend is a Django project that powers the backend of Terraso
platform.

## Running locally with Docker

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

The repository has a file with sample data that can be imported to a new
installation of the project. The Django built-in command `loaddata` is
used for it:

```sh
$ python terraso_backend/manage.py loaddata sampledata.json
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
