#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "sarge",
# ]
# ///
"""Python wrapper for Sigsum CLI tools.

Wrapper around [Sigsum](https://www.sigsum.org/) CLI tools (sigsum-key,
sigsum-submit, sigsum-verify, sigsum-token, ...) so that they can be used from
Python code.

This file/module is the core implementation code for the wrapper.

This wrapper provides a library/API interface -- with functions, Python
objects, strings, etc. When using this wrapper, you do not need to interact
with file objects or paths (unless you have some other reason for doing so). A
few things to note:

- Unlike when using the CLI tools directly, when using this wrapper,
  persistence is *not* the default -- all data is ephemeral. You will need to
  handle saving inputs and outputs yourself.

- This wrapper communicates with the CLI tools by writing everything into temp
  files. If you are working with large data, you will probably want to first
  calculate the checksum yourself, and then use `raw_hash=True` for the
  relevant functions.

Upstream Sigsum CLI tools docs:
https://git.glasklar.is/sigsum/core/sigsum-go/-/blob/main/doc/tools.md

"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

# from io import IOBase
# from typing import IO, Annotated, Iterable, Literal, TypeAlias, Union
from typing import Iterable, Literal, Optional, Sequence, TypeAlias

from sarge import (  # type: ignore[import-untyped]
    Capture,
    run,
    shell_format,
    shell_quote,
)

_DEBUG = os.getenv("DEBUG_STW")
if _DEBUG and _DEBUG.lower() == "true":
    from devtools import debug as _debug

try:
    _debug
except NameError:

    def _debug(*args, **kwargs):  # type: ignore[misc]
        pass


_TmpDir = tempfile.TemporaryDirectory

# TODO consider using typing.Annotated and pydantic.types.StringConstraints

SigsumPrivSecKey: TypeAlias = str

SigsumPubKey: TypeAlias = str
SigsumKeyHash: TypeAlias = str
SigsumHexKey: TypeAlias = str
SigsumVKey: TypeAlias = str

SigsumSignature: TypeAlias = str

SigsumReq: TypeAlias = str
SigsumPolicy: TypeAlias = str
SigsumProof: TypeAlias = str

SigsumDnsTxtRecord: TypeAlias = str
SigsumHttpHeader: TypeAlias = str

StdOutAndErrTuple: TypeAlias = tuple[str, str]

MessageType: TypeAlias = Literal["text", "bytes"]


@dataclass(frozen=True)
class SigsumKeyPair:
    secret: SigsumPrivSecKey
    pub: SigsumPubKey


@dataclass(frozen=True)
class SigsumSubmitTokenSignSpec:
    sign_seckey: SigsumPrivSecKey  # private key used for signing submit tokens
    domain: str  # domain where the corresponding public key is registered


def _item_type_str(m: object):
    return isinstance(m, str)


def _item_type_bytes(m: object):
    return isinstance(m, bytes)


def _gen_indexes(n: int) -> list[str]:
    pad = len(str(n))
    file_names = [str(_).zfill(pad) for _ in range(n)]
    return file_names


def _paths_where_written(
    items: Iterable, root: str | os.PathLike | Path, type_: MessageType
) -> Iterable[Path]:
    """Accepts an iterable of data items; writes each to a file under the root
    and yields each path.

    TODO use a method of generating fpaths that does not require len(), and
    thus does not require exhausting the iterator upfront.

    """
    items = list(items)
    fpaths = [Path(root).resolve() / f"data{idx}" for idx in _gen_indexes(len(items))]

    _item_type_fn = _item_type_str if type_ == "text" else _item_type_bytes

    for fp, item in zip(fpaths, items):
        assert _item_type_fn(item)
        if type_ == "text":
            fp.write_text(item)
        elif type_ == "bytes":
            fp.write_bytes(item)

        yield fp


def _cmd_str(
    executable: str | os.PathLike | Path,
    /,
    flags: list[str] = [],  # Options that do not take arguments.
    *,
    opt_args: Sequence[
        tuple[str, str | os.PathLike | Path]
    ] = [],  # Options that require arguments.
    pos_args: Sequence[
        str | os.PathLike | Path
    ] = [],  # Positional arguments/parameters.
):
    __cmd = " ".join(
        [
            shell_quote(executable),
            *[shell_quote(str(o)) for o in filter(None, flags)],
            *[
                f"{shell_quote(str(o))} {shell_quote(str(arg))}"
                for (o, arg) in filter(None, opt_args)
            ],
            *[shell_quote(str(p)) for p in filter(None, pos_args)],
        ]
    )
    return __cmd


def key_generate() -> SigsumKeyPair:
    """Create a new signing key pair.

    Generates an Ed25519 key pair. The private key is in OpenSSH format.
    """
    # $ sigsum-key gen -o submit-key ==> "You should see that two files,
    # submit-key and submit-key.pub, were created. These files follow the SSH
    # key-file format."
    with Capture() as out, Capture() as err, _TmpDir() as temp_dir:
        privseckey_fp = Path(temp_dir).resolve() / "seckey"
        p = run(
            # NOTE: sigsum-key v0.9.1 does not accept 'generate', only 'gen'.
            shell_format("sigsum-key gen -o {0}", privseckey_fp),
            stdout=out,
            stderr=err,
            cwd=temp_dir,  # Redundant, but might as well.
        )
        if p.returncode == 0:
            pubkey_fp = Path(f"{privseckey_fp}.pub")
            return SigsumKeyPair(
                secret=privseckey_fp.read_text(),
                pub=pubkey_fp.read_text(),
                # (out.read(), err.read()),
            )
        else:
            raise RuntimeError("Subprocess returned non-zero exit code")


_PubKeySubCmd: TypeAlias = Literal[
    "to-hash",
    "to-hex",
    "from-hex",
    "from-vkey",
    "to-vkey",
]


def _key_pubkey_op(
    pubkey: SigsumPubKey | SigsumHexKey,
    cmd: _PubKeySubCmd,
    # *args,
    # **kwargs,
):
    """Non-public meta-function for implementing related commands `sigsum-key`
    hash/hex etc. in fewer lines of code.

    Note that this is compatible with v0.10.1 (and not v0.9.1). In the older
    version, subcommands are named differently.

    """
    with Capture() as out, _TmpDir() as temp_dir:
        pubkey_fp = Path(temp_dir).resolve() / "pubkey"
        pubkey_fp.write_text(pubkey)
        p = run(
            shell_format("sigsum-key {0} -k {1}", cmd, pubkey_fp),
            stdout=out,
            cwd=temp_dir,  # Redundant, but might as well.
        )
        if p.returncode == 0:
            return out.read().decode().strip()
        else:
            raise RuntimeError("Subprocess returned non-zero exit code")


def key_to_hash(pubkey: SigsumPubKey) -> SigsumKeyHash:
    """Receives public key and returns key hash."""
    return _key_pubkey_op(pubkey, cmd="to-hash")


def key_to_hex(pubkey: SigsumPubKey) -> SigsumHexKey:
    """Receives public key and returns hex key."""
    return _key_pubkey_op(pubkey, cmd="to-hex")


def key_from_hex(hexkey: SigsumHexKey) -> SigsumPubKey:
    """Receives hex public key and returns OpenSSH format public key."""
    return _key_pubkey_op(hexkey, cmd="from-hex")


def key_from_vkey(vkey: SigsumVKey) -> SigsumPubKey:
    """Receives a vkey and returns OpenSSH format public key."""
    return _key_pubkey_op(vkey, cmd="from-vkey")


def key_to_vkey(pubkey: SigsumPubKey) -> SigsumVKey:
    """NOT YET IMPLEMENTED.

    TODO (different invocation from the others...). Receives public key ...
    writes a signed note verifier line. By default, creates a vkey for a Sigsum
    log.

    sigsum-key to-vkey [-n name] [-k file] [-t type] [-o output]

    """
    raise NotImplementedError()


def key_sign(msg: bytes, seckey: SigsumPrivSecKey) -> SigsumSignature:
    """NOT YET IMPLEMENTED"""
    raise NotImplementedError()


def key_verify(msg: bytes, pubkey: SigsumPubKey, sig: SigsumSignature) -> bool:
    """NOT YET IMPLEMENTED"""
    raise NotImplementedError()


def submit_prepare(
    seckey: SigsumPrivSecKey,
    messages: Iterable[bytes] | Iterable[str],
    raw_hash: bool,
) -> list[SigsumReq]:
    """Prepare (create and sign) a Sigsum add-leaf request.

    Create and sign -- entirely locally -- a Sigsum add-leaf request, such that
    it is fully prepared for later submission (via `submit_send` function) to a
    Sigsum log server.

    TODO: Remove `raw_hash: bool` param. Make raw-hash mode the default and
    only mode.

    """
    raw_hash_arg = "--raw-hash" if raw_hash else ""
    msg_type: MessageType = "text" if raw_hash else "bytes"

    with _TmpDir() as _temp_dir:
        temp_dir = Path(_temp_dir).resolve()
        seckey_fp = temp_dir / "seckey"
        seckey_fp.write_text(seckey)

        msg_fpaths = list(
            _paths_where_written(items=messages, type_=msg_type, root=temp_dir)
        )
        req_fpaths = [Path(f"{fp}.req") for fp in msg_fpaths]

        __cmd = _cmd_str(
            "sigsum-submit",
            flags=[raw_hash_arg],
            opt_args=[("-k", seckey_fp)],
            pos_args=msg_fpaths,
        )
        _debug(__cmd)

        p = run(
            __cmd,
            cwd=temp_dir,  # Redundant, but might as well.
        )

        if p.returncode == 0:
            return [fp.read_text() for fp in req_fpaths]
        else:
            raise RuntimeError("Subprocess returned non-zero exit code")


def submit_send(
    policy: SigsumPolicy,
    requests: Iterable[SigsumReq],
    # token_spec: SigsumSubmitTokenSignSpec | None = None,
) -> list[SigsumProof]:
    """Submit one or more already-prepared leaf request(s) to a Sigsum log.

    This command accepts leaf requests as output by `submit_prepare` function.

    TODO: Implement `-a` and `-d` options to support submitting to production
    servers that apply domain-based rate limiting. Currently this function
    supports only test servers that have no rate-limiting.

    See:

        'If the log(s) used are configured to apply domain-based rate limiting
        (as publicly accessible logs are expected to do), the -a option must be
        used to specify the private key used for signing a submit token, and
        the -d option specifies the domain (without the special "_sigsum_v1"
        label) where the corresponding public key is registered. An appropriate
        "sigsum-token:" header is created and attached to each add-leaf
        request.'

    """
    with _TmpDir() as _temp_dir:
        temp_dir = Path(_temp_dir).resolve()
        policy_fp = temp_dir / "policy"
        policy_fp.write_text(policy)

        req_fpaths = list(
            _paths_where_written(items=requests, type_="text", root=temp_dir)
        )
        proof_fpaths = [fp.with_suffix(".proof") for fp in req_fpaths]

        __cmd = _cmd_str(
            "sigsum-submit", opt_args=[("-p", policy_fp)], pos_args=req_fpaths
        )

        p = run(
            __cmd,
            cwd=temp_dir,  # Redundant, but might as well.
        )
        if p.returncode == 0:
            return [fp.read_text() for fp in proof_fpaths]
        else:
            raise RuntimeError("Subprocess returned non-zero exit code")


def verify(
    policy: SigsumPolicy,
    pubkey: SigsumPubKey,
    proof: SigsumProof,
    message: bytes | str,  # TODO accept only raw hash
    raw_hash: bool,  # TODO remove
) -> bool:
    """Verify a Sigsum proof against the submitter public key(s) and a trust policy.

    TODO: Allow multiple submitter keys. `sigsum-verify` can accept multiple
    submitter keys, not just one. Currently this function accepts just one key.

    TODO: Remove `raw_hash: bool` param. Make raw-hash mode the default and
    only mode.

    """
    raw_hash_arg = "--raw-hash" if raw_hash else ""
    # msg_type = "text" if raw_hash else "bytes"
    _item_type_fn = _item_type_str if raw_hash else _item_type_bytes
    assert _item_type_fn(message)

    with _TmpDir() as _temp_dir:
        temp_dir = Path(_temp_dir).resolve()

        pubkey_fp = temp_dir / "pubkey"
        pubkey_fp.write_text(pubkey)

        policy_fp = temp_dir / "policy"
        policy_fp.write_text(policy)

        proof_fp = temp_dir / "proof"
        proof_fp.write_text(proof)

        __cmd = _cmd_str(
            "sigsum-verify",
            [raw_hash_arg],
            opt_args=[("-k", pubkey_fp), ("-p", policy_fp)],
            pos_args=[proof_fp],
        )
        _debug(__cmd)

        p = run(
            __cmd,
            input=message,
            cwd=temp_dir,  # Redundant, but might as well.
        )

        if p.returncode == 0:
            return True
        elif p.returncode == 1:
            return False

        raise RuntimeError("Undefined problem with pipeline or subprocess")


def token_record(pubkey: SigsumPubKey) -> SigsumDnsTxtRecord:
    """NOT YET IMPLEMENTED.

    "The record sub command is useful when setting up the DNS record that is
    required for submitting to a log server with rate limits."

    "Creating a DNS record for a key To use submit tokens, the corresponding
    public key must be registered in DNS. The sigsum-token record sub command
    formats an appropriate TXT record, in zone file format. There's one
    mandatory argument, -k, specifying the public key to use. The TXT record is
    written to standard output, or to the file specified with the -o option."

    See: https://git.glasklar.is/sigsum/core/log-go/-/blob/main/doc/rate-limit.md#enabling-public-access

    Example output:

    $ sigsum-token record -k example.key.pub

    _sigsum_v1 IN TXT "e0863b18794d2150f3999590e0e508c09068b9883f05ea65f58cfc0827130e92"

    """
    raise NotImplementedError()


def token_create(
    seckey: SigsumPrivSecKey, log_key: SigsumPubKey, domain: Optional[str] = None
) -> SigsumHttpHeader:
    """NOT YET IMPLEMENTED."""
    raise NotImplementedError()


def token_verify(TODO):
    """NOT YET IMPLEMENTED."""
    raise NotImplementedError()


def monitor(policy: SigsumPolicy, pubkey: SigsumPubKey, interval_seconds: int = 30):
    """NOT YET IMPLEMENTED.

    > A monitor downloads signed checksums from the logs listed in our trust policy.
    > Start the monitor and print all signed checksums for your public key:

    $ sigsum-monitor --interval 10s -p ~/.config/sigsum/trust_policy submit-key.pub

    > This launches a long-lived process that will give continual updates. Output
    > will be something like: New <log> leaves, count 0, total processed <N>

    TODO this fn will need to yield lines from the output.
    """
    raise NotImplementedError()
