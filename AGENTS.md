# AGENTS.md

WeeWX extension **MQTTReplicate**: replicates WeeWX archive data over MQTT v5 request/response.

## Role & boundaries

- `bin/user/mqttcommon.py` is the paho mqtt code shared with the other weewx-mqtt extensions,
  vendored **verbatim**: never edit this copy. Replicate uses `Logger`/`LoggerThread`; the
  throttle is unwired. Change it in the [mqttcommon](https://github.com/weewx-mqtt/mqttcommon)
  repository and sync; that repository's `AGENTS.md` has the procedure and the `MQTTCOMMON_API`
  bump ritual.
- `install.py` is the WeeWX `ExtensionInstaller`; it also carries the default `[MQTTReplicate]`
  config (Requester + Responder sections with full option docs). Its `files` list is what actually
  ships — any new file added under `bin/user` must be listed there or the installed extension will
  be missing it.

## Layout

- `bin/user/mqttreplicate.py` — almost all the code (~1100 lines): the Requester driver, the
  Responder service, the paho wrapper, the loop threads, and queued logging (see Architecture).
- `bin/user/tests/unit/` — the real test suite. `bin/user/tests/func/test_template.py` is an
  empty placeholder.
- `bin/user/run_mqttreplicate.py` — standalone runner (Requester/Responder) used from `tmp/`
  scripts; distinct from the module's own `__main__` CLI.
- `docs/` — Jekyll site; the project README is `docs/readme.md`, not a root `README.md`
  (docs-first). `docs/_site` is generated — don't hand-edit it.
- `tmp/` — local, gitignored configs and scripts; not part of the shipped extension.
- `.vscode/launch.json` — ready-made debug configs.

## Environment

Run everything from the repo root:

```bash
source .devenv
export PYTHONPATH="$WEEWX_PYTHONPATH"   # == bin, or bin:../weewx/src
```

- WeeWX must be importable. CI pip-installs it; locally `.devenv` uses the sibling checkout
  `../weewx` when WeeWX is not installed (WeeWX v5 uses `src/`). Prefix test/lint commands with
  `PYTHONPATH=bin:../weewx/src` and you get the same result without sourcing.
- `.devenv` defines `WEEWX_MODULE_NAME`, `WEEWX_PYENV_VERSION=3.10`, `WEEWX_TOOL_PATH`,
  `WEEWX_LINT_PATHS`, `WEEWX_TEST_SUITES`, and puts the helper scripts on `PATH`. It does **not**
  export `PYTHONPATH` itself, so `source .devenv` alone does not make bare `pytest` work — export
  it yourself or use the prefix above. (The helper scripts do `export
  PYTHONPATH=$WEEWX_PYTHONPATH`, so `source .devenv && unittests.sh` works as-is.)
- Python deps: `paho-mqtt` (2.x locally), `weewx`, `configobj`, `mock`, `pytest`, `coverage`,
  `pylint`.
- Shortcut scripts (`unittests.sh`, `lint.sh`, `coverage.sh`, `watchunittests.sh`, ...) come from
  `WEEWX_TOOL_PATH` = `~/weewx_dev/weewx-extensions/development-tools/tools`, a local clone of
  the repo the CI reusable workflows come from. They also assume pyenv. Note `lint.sh` lints all
  of `bin/user/`, a wider scope than CI. `verify.sh` is the full pre-commit gate.

## Commands

```sh
# all unit tests (currently 138, ~1s)
PYTHONPATH=bin:../weewx/src python3 -m pytest bin/user/tests/unit

# a single test / file
PYTHONPATH=bin:../weewx/src python3 -m pytest bin/user/tests/unit/test_mqttresponder.py::TestMQTTResponder::test_init

# lint — CI's exact scope (pylint 4.1.3, pinned in requirements.txt; CI requires
# zero messages and a score >= fail-under=10)
PYTHONPATH=bin:../weewx/src python3 -m pylint bin/user/mqttreplicate.py bin/user/mqttcommon.py

# coverage (same shape as CI)
PYTHONPATH=bin:../weewx/src coverage run --branch -m pytest bin/user/tests/unit
coverage html --include 'bin/user/*.py' --omit bin/user/__init__.py

# before committing: the full gate
source .devenv
~/weewx_dev/weewx-extensions/development-tools/tools/verify.sh
```

## Architecture / behavior

- `MQTTRequester` — WeeWX **driver** (secondary/copy side), loaded via `loader()`.
  Config key: `driver = user.mqttreplicate`. Its options are parsed by the module-level
  `parse_requester_config()` into an `MQTTRequesterConfig` dataclass (`self.config`).
- `MQTTResponder` — WeeWX **service** (primary side), registered in `install.py` as
  `restful_services = user.mqttreplicate.MQTTResponder`. It follows the same pattern:
  `parse_responder_config()` into an `MQTTResponderConfig` dataclass (`self.config`).
- `MQTTClient` — thin wrapper over paho-mqtt's v2 api. The reconnect delays are fixed at the
  paho defaults (1 to 128 seconds); they are not configurable.
- `*LoopThread`/`*Thread` classes run the MQTT loops; they must be joined on shutdown.
  They take the parsed config object rather than loose options; the Responder catchup
  thread also takes the raw `config_dict` (for `get_manager_dict_from_config`).
- **Config contract:** each side must have **exactly one** binding with `type = main`
  (0 or 2+ raise `ValueError` at construction). The Requester instance/binding names
  (e.g. `[[[weewx]]]`/`[[[[wx_binding]]]]`) must match the Responder's, but that pairing
  is **not** validated: a response with an unknown `data_binding` is silently dropped
  with only a log error, so misconfiguration shows up as missing data, not a crash.
- **Logging is queued, publish-style:** `Logger.trace/debug/info/error(msg_id, msg_text)` enqueue
  entries built by the single entry builder `Logger.create_entry(name, log_type, msg_id, msg_text, archive_timestamp=None)`
  -> `{'name', 'log_type', 'msg_id', 'msg_text', 'thread_id', 'archive_timestamp'}` (native id of the calling thread,
  captured at enqueue time — that is what the `(%s)` prefix shows; `archive_timestamp` is the archive
  record context the producer supplies — the same None here). Every application message passes
  `None` for the message id — replicate has no message ids (only the shared thread entries —
  start 122002, exit 122003, invalid 124003 — carry one). `Logger` and `LoggerThread` are
  `mqttcommon.Logger`/`mqttcommon.LoggerThread` — replicate has no local `Logger` name; the
  message format is the shared `"(%s) %s"`, and construction passes `log_name=__name__` only;
  the shared prefix — name, thread id, and the archive record when there is one — applies (the base
  `_format_args` builds it). The skeleton tests — including
  the converged default-format rendering — live in the shared `test_mqttcommon.py`; replicate has
  no local logging tests. `mqttcommon.Logger(<ClassName>, log_queue=..., log_name=...)` is built by
  `MQTTResponder`/`MQTTRequester` with a fresh `queue.Queue()`, named `<ClassName>` (the bare
  class name; the emitting thread's id renders from the stamped entry).
  A daemon `LoggerThread` drains the queue and dispatches through
  `Logger.log_entry()`, which skips `log_type: None` entries;
  `Logger.shutdown()` (sentinel + join, idempotent, `SHUTDOWN_TIMEOUT = 10`) is called
  from `MQTTResponder.shutDown()`'s `finally` (covers the disabled path) and from
  `MQTTRequester.closePort()`. Tests that assert on log output must drain first
  (shutdown) or call `log_entry` directly after a shutdown; never patch
  `user.mqttreplicate.threading` without also patching `user.mqttcommon.Logger` (real threads start
  in `Logger.__init__`).
- **paho-mqtt v2 only.** The wrapper implements only the v2 callback API
  (`MQTTClient.__init__()` raises `ValueError("paho mqtt v2 is required.")` for older
  versions), and the client is created with `protocol=MQTTv5`. The documented minimum is
  paho-mqtt 2.0.0 — v1 support never existed, so don't add untested code paths for it.

## Testing conventions and quirks

- Only `bin/user/tests/unit` is real; `bin/user/tests/func/test_template.py` is an empty
  placeholder. CI runs this repo with `function-test: false`, `integration-test: false`,
  `e2e-test: false` — do not add suites there expecting CI to run them.
- Tests mock `MQTTClient`; no MQTT broker is needed (mosquitto is installed
  in CI but unused by the unit suite).
- New tests: copy an existing test file's header — `# pylint: disable=missing-*-docstring`
  block and the standalone `import mock` package (not `unittest.mock`).
- `bin/user/tests/unit/helpers.py` provides `random_string()` and `run_tests()`; test
  files end with `if __name__ == '__main__': helpers.run_tests()`, which takes
  `ClassName methodName` as CLI args (exactly 1 or 3 argv entries, or it prints
  "Bad parameters").
- There is no `conftest.py`; tests import `user.mqttreplicate` and the sibling `helpers`
  module, which is why `bin` must be on `PYTHONPATH`. Single file/class/method selection
  works fine with pytest (`path::Class::method`); pytest puts the test file's own
  directory on `sys.path`, so `helpers` resolves.

## Config, versioning and release

- Config options live in the `[MQTTReplicate]` template in `install.py` (Requester + Responder
  sections with full option docs).
- `VERSION` is duplicated and must stay in sync in two files: `install.py` and
  `bin/user/mqttreplicate.py`.
- `changes.txt` is the changelog.
- Releases are tagged by `.github/workflows/versioning.yml` (Actions-Us/actions-tagger) on
  GitHub release publish.
- `run-fetch.yml` syncs this repo from `weewx-mqtt/replicate` upstream daily.
- Line length is 150 project-wide (`.flake8`, `.markdownlint.jsonc`); `.flake8` also sets
  `max-cognitive-complexity = 10`.

## Running standalone / debugging

- `python3 bin/user/run_mqttreplicate.py requester|responder --install-type git
  --config-file tmp/mqttreplicate.requester.conf` (see `tmp/*.sh`).
- `mqttreplicate.py` also has its own `__main__` CLI with different subcommands
  (`request`/`respond --conf ...`); don't confuse the two entry points.
- `.vscode/launch.json` has ready-made debug configs (requester, responder, run one
  test, `weectl extension install` via `../weewx/src/weectl.py`).
- To verify `install.py` changes without touching an install:
  `PYTHONPATH=bin:../weewx/src python3 ../weewx/src/weectl.py extension install . --dry-run --yes`.

## CI

- `.github/workflows/run-analyze-test.yml` → pushes to any branch **except** `master`.
  `.github/workflows/run-analyze-test-matrix.yml` → pushes to `master` (WeeWX/Python matrix).
  Both call reusable workflows in `weewx-extensions/development-tools@v6`.
- Lint step runs `pylint ./bin/user/mqttreplicate.py ./bin/user/mqttcommon.py ... | tee results/pylint.txt` and
  then checks pylint's exit status, so with `lint-fail: true` (the v6 default) any
  finding — or a score below `fail-under=10` — fails the job. It runs only on the latest
  matrix combo (ubuntu-24.04 / 3.13 / current WeeWX), and the flake8 step only runs if
  pylint passed.
- The development-tools workflows install pylint **unpinned**; this repo pins it to
  4.1.3 via `requirements.txt` (installed after the base list, so the pin wins). The pin
  is marker-guarded to Python >= 3.10 — the matrix's 3.9 job cannot install pylint 4.
  `.pylintrc`'s `suggestion-mode` option was removed: pylint 4 rejects it (E0015).
- The lint target is zero pylint messages. pylint 4-only checks to know about:
  R0917 (too-many-positional-arguments, mirrors R0913 on constructors) and R1737
  (use-yield-from). Classes with unavoidably many attributes carry a per-class
  `# pylint: disable=too-many-instance-attributes` comment — pylint does **not**
  exempt dataclasses from R0902, so config dataclasses get one too.

## Commits

Never commit, push, tag or release unless explicitly asked: stage the changes and stop. A
request to make a change is not permission to commit it, and "do it" does not include
committing. Propose the commit message and wait for the go-ahead.

## Cross-repo workflow

Single changes stay in this repository. Cross-repo work (a shared change, rename, wording pass)
starts in the workspace root (`weewx-mqtt`): see the workspace `AGENTS.md` for the order of a
cross-repo change and `./status-all.sh` to see every repository's state at once.