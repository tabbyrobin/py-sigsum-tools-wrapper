# `sigsum-tools-wrapper`: Python wrapper for Sigsum command line tools

This is a Python wrapper around the [Sigsum](https://www.sigsum.org/) project's
[command line tools](https://git.glasklar.is/sigsum/core/sigsum-go/-/blob/main/doc/tools.md)
(`sigsum-key`, `sigsum-submit`, `sigsum-verify`, `sigsum-token`), so that they
can be used from Python code.

This wrapper provides a library/API-style interface -- with functions, Python
objects, strings, etc. When using this wrapper, you do not need to interact with
file objects or paths (unless you have some other reason for doing so).

Unlike when using the CLI tools directly, when using this wrapper, persistence
is *not* the default -- all data is ephemeral. You will need to handle saving
inputs and outputs yourself.

This is *not* a reimplementation in Python. It's just a wrapper. Internally, it
calls out to the Sigsum golang CLI tools. It aims to do so robustly. It uses the
CLI tools because as of time of writing (2025-03), the Sigsum golang API is not
necessarily stable.

## Quickstart

- Clone the repo, and `cd` into it
- `./dev-setup.sh` (installs stuff -- may want to run in a VM)
- `pipx install .`

<!-- > [!TIP] You can also do `pipx install GIT_REPO_URL`. -->

For examples of how to use the library in your code, see the automated
integration testing in `tests/test_sigsum.py`.

## Golang and `sigsum-go` dependencies

Installing this package will install the *Python* wrapper and any *Python*
dependencies, but to actually use this library, you will also need the Sigsum
CLI tools themselves, which are written in Go.

Golang toolchain can be a pain to install. A quickstart is provided in an
attached shell script. There is also an entrypoint script, `dev-setup.sh`, which
is intended to bootstrap everything needed, on a suitable system (tested on
Debian 12).

Note that these shell scripts are intended for a development setting; for
production setting you will probably want to choose more carefully how you
install the dependencies.

## Testing etc.

Tests and other automations are using Nox. You can just run: `nox` to run the
default suite. Use `nox -l` to view a list of available sessions/tasks.

To run specific sessions in order, do like so: `nox -s fmt lint`, `nox -s sdist
wheel`.

The sdist and wheel generation includes some extra steps to ensure that the
wheel is [bit-for-bit reproducible](https://reproducible-builds.org/).

## Notes

This project is licensed GPLv3.

Using this library, you will get decent autocomplete and linting in a suitable
editor. The code is typed, and checked with MyPy.

Basic testing (with pytest) is implemented. Nox is used as an orchestration
runner. Uv is used for various things.

This wrapper communicates with the CLI tools by writing everything into temp
files. If you are working with large data, you will probably want to first
calculate the checksum yourself, and then use `raw_hash=True` for the relevant
functions. In a future version of the wrapper, the API should be simplified and
offer only raw-hash mode (raw-file mode will be unavailable -- you must first
calculate the hash yourself).

The core code is all contained in single file, `sigsum.py`, so you can drop that
into your project if you want to "vendor" it.

Note that the automated tests use the Sigsum public testing server. To use
`submit_send` in a production application, Sigsum requires some further setup,
because the public production servers employ rate limiting.

See: [Sigsum log rate limiting](https://git.glasklar.is/sigsum/core/log-go/-/blob/main/doc/rate-limit.md).

## Future work / TODO

- Implement the remaining functions which are not complete:
  `key_to_vkey`, `key_sign`, `key_verify`, `token_record`, `token_create`,
  `token_verify`, `monitor`.

- Remove dependency on sarge. We mostly use sarge for its shellquoting safety,
  but since we control all parameters end-to-end (none are from user input), we
  don't really need this.

- Make the core functions always use `--raw_hash`, and provide convenience
  functions `hash_str()`, `hash_bytes()`, `hash_file()` etc. This will simplify
  the code and lead to a clearer API.

- Accept data not just as bytes|str, but also as bytes IO stream, and
  memoryview.
