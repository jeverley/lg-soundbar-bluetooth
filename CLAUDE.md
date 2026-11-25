# CLAUDE.md

`lg-soundbar-bluetooth`: control LG soundbars over Bluetooth Classic
(RFCOMM, the Serial Port Profile), speaking the soundbar's Bluetooth serial
protocol, as LG's Sound Bar app uses it. The Bluetooth link comes
from `bluetooth-classic` (its `RfcommClient`, made by the client's link
factory and connected with `establish_rfcomm_connection()`); everything
about the soundbar lives here.
It follows the layout and tooling of Home Assistant's Bluetooth libraries
(the Bluetooth-Devices organisation): Poetry, `src/` layout, typed, pytest,
mypy, ruff, pre-commit, python-semantic-release, Read the Docs.

## Rules

- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`,
  `test:`, `chore:`); releases are made from them. Do not bump the version
  by hand.
- Commit as `jeverley <46714706+jeverley@users.noreply.github.com>`.
- Work on a feature branch; ask before merging anything more than trivial.
- Follow LG's app: what it sends, in what order, gated by which flags. No
  model-specific special cases; derive behaviour from what the soundbar
  reports. Mark deliberate differences from the app, and say why.
- `docs/protocol.md` is the protocol reference: every function the app uses,
  with a "Used here" column, and findings from real soundbars. Mark what is
  unconfirmed.
- `testing.FakeSoundbar` behaves like a real LG G1; when a real soundbar is
  found to behave differently, update it to match.
- Docs, comments and tests use example addresses only (such as
  `00:11:22:33:44:55`), never real ones.
- Before committing: `ruff check .`, `ruff format --check .`, `mypy src
  tests`, `pytest`. Timing tests can be flaky: run the suite a few times
  after connection changes.
- Describe the protocol and what the soundbar does; never how the protocol
  was worked out (no app internals or version numbers).
- No em dashes, and no `--` in their place.
