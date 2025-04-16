import os
import tarfile
from functools import partial
from pathlib import Path

import nox

PYPROJECT = nox.project.load_toml("pyproject.toml")
MODULE_NAME = str(PYPROJECT["project"]["name"]).replace("-", "_")
# Pulls from requires-python
PYTHON_VERSIONS = nox.project.python_versions(PYPROJECT, max_version="3.13")

dep_groups = partial(nox.project.dependency_groups, PYPROJECT)
nox.session = partial(nox.session, venv_backend="uv")


def sp(s: str) -> list[str]:
    """Convenience alias to split a string by whitespace."""
    return s.split()


@nox.session
def fmt(session):
    session.install(*dep_groups("fmt"))

    session.run(*sp("ruff check --select I --fix"))  # isort equivalent
    session.run("ssort")
    session.run("ruff", "format")

    # https://taplo.tamasfe.dev/cli/usage/formatting.html Consider also:
    # https://tombi-toml.github.io/tombi/docs
    session.run(*sp("taplo fmt pyproject.toml"))

    # shfmt -i 2 -w ./**.sh  # TODO
    # https://pypi.org/project/shfmt-py/


@nox.session(python=["3.13"])
def lint(session):
    session.install(*dep_groups("fmt", "lint"))
    session.run("ruff", "check")
    session.run(*sp("validate-pyproject pyproject.toml"))
    session.run(*sp("taplo fmt --check pyproject.toml"))

    session.install("--group=dev", "-e", ".")  # mypy needs to see everything
    session.run("mypy", ".")

    # shellcheck ./**.sh # TODO
    # https://github.com/shellcheck-py/shellcheck-py


@nox.session
@nox.parametrize("debug", ["true", "false"])
def test_locked(session: nox.Session, debug: str) -> None:
    """Run the tests with canonical config; a basic single pass."""
    session.run_install(
        *["uv", "sync", "--locked"],
        # "--extra=test",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    try:
        session.run(
            *["pytest", "--cov", "--cov-branch", *session.posargs],
            env={"DEBUG_STW": debug},
        )
    finally:
        session.notify("report")


@nox.session(default=False, python=[*reversed(PYTHON_VERSIONS), "pypy3.11"])
def test_matrix(session: nox.Session) -> None:
    """Run tests, across multiple Python versions."""
    session.install("--group=dev", "-e", ".")  # TODO consider renaming dev to test
    try:
        session.run(
            *["pytest", "--cov", "--cov-branch", *session.posargs],
            # env={"DEBUG_STW": "true"},
        )
    finally:
        session.notify("report")


@nox.session
def report(session: nox.Session) -> None:
    session.install("--group=dev", "-e", ".")
    session.run("coverage", "report")
    session.run("coverage", "html")


@nox.session(python=["3.10"])
def docs(session: nox.Session) -> None:
    session.install("--group=dev", "-e", ".")

    session.install("portray>=1.8.0", "legacy-cgi")
    # session.install("pdocs>=1.2.0")
    # session.install("pymdown-extensions>=9.0")
    # session.install("mkdocs-material>=5.2.0")

    session.run(*sp(f"portray as_html -m {MODULE_NAME} --overwrite"))

    session.install("pycco")
    session.run(
        *sp("pycco -d site/pycco"),
        *Path("src").rglob("*.py"),
        *Path("tests").rglob("*.py"),
    )

    # TODO https://stackoverflow.com/questions/64518816/readthedocs-publishing-pre-built-html-pages-to-readthedocs


@nox.session
def sdist(session: nox.Session) -> None:
    """Build an sdist from source, reproducibly."""
    # TODO Consider using a hatch build hook instead.

    # Q: Should the sdist include a timestamp file? Akin to yocto's
    # `__source-date-epoch.txt` See:
    # https://wiki.yoctoproject.org/wiki/Reproducible_Builds#Current_Development
    timestamp = str(
        session.run(*sp("git log -1 --pretty=%ct"), external=True, silent=True)
    ).strip()
    Path("__source-date-epoch.txt").write_text(timestamp)

    session.run("uvx", "hatch", "build", "-t", "sdist")

    _files = sorted(Path("dist").rglob("*.tar.gz"))
    for f in _files:
        session.run("tar", "tvf", f, external=True)
    session.run("sha256sum", *_files, external=True)


def get_timestamp_from_sdist(sdist_path: str | os.PathLike) -> int:
    """sdist_path can be a path to an sdist archive (tar.gz), or a directory."""
    if Path(sdist_path).is_file() and tarfile.is_tarfile(sdist_path):
        with tarfile.open(sdist_path, "r") as archive:
            _v = PYPROJECT["project"]["version"]
            _sde = f"{MODULE_NAME}-{_v}/__source-date-epoch.txt"
            _f = archive.extractfile(_sde)
            assert _f is not None
            _timestamp = str(_f.read(), "utf-8").strip()
    elif Path(sdist_path).is_dir():
        _timestamp = (Path(sdist_path) / "__source-date-epoch.txt").read_text().strip()

    timestamp = int(_timestamp)
    if timestamp < 315_532_800:
        print(
            f"WARN: {timestamp=} is less than 315532800. This may cause problems. "
            "ZIP/whl uses DOS timestamps, which cannot express times before that."
        )
    return timestamp


@nox.session
def wheel(session: nox.Session) -> None:
    """Build wheels, reproducibly.

    Build sdist from source. Build wheel from sdist. Ensure timestamps are
    deterministic."""
    _files = list(Path("dist").rglob("*.tar.gz"))
    assert len(_files) == 1
    sdist_path = _files[0]
    timestamp = str(get_timestamp_from_sdist(sdist_path))
    session.run(
        # *["uvx", "hatch", "build", "-t", "wheel", sdist_path],
        *["uv", "build", "--wheel", str(sdist_path)],
        env={"SOURCE_DATE_EPOCH": timestamp},
    )

    _files = sorted(Path("dist").rglob("*.whl"))
    for f in _files:
        session.run("unzip", "-l", f, external=True)
    session.run("sha256sum", *_files, external=True)


# TODO a session to update the inline script dependencies based on
# pyproject.toml.

# https://quentin.pradet.me/blog/migrating-a-python-library-to-uv.html
# https://nox.thea.codes/en/stable/usage.html
