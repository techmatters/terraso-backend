# Terraso - Backend

Terraso backend is a Django project the empower the backend of Terraso
platform.

## Running locally with Docker

Start building the Docker images (make sure there's `requirements.txt`
file created before building the images):

```sh
$ make build
```

There's a shortcut to automatically lock and build Docker image:

```sh
$ make setup
```

Run the database migrations before the first run:

```sh
$ make run migrate
```

Than the run command can be executed:

```sh
$ make run
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
