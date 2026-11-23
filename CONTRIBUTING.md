# Contributing

Contributions are welcome. Please open an issue first for anything beyond a
small fix, so we can agree on the approach.

## Development

Install [Poetry](https://python-poetry.org/), then:

```console
$ poetry install
$ poetry run pre-commit install
$ poetry run pytest
```

The tests run against a fake BlueZ on a fake system bus, so they need no
Bluetooth hardware.

## Commits

Releases are made automatically from the commit messages, which follow
[Conventional Commits](https://www.conventionalcommits.org/): `feat:` for a
new feature, `fix:` for a bug fix, `docs:`, `test:`, `chore:` and so on. A
`feat:` makes a minor release and a `fix:` a patch release.
