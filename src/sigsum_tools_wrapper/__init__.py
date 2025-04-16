import hashlib
from typing import TypeAlias

Sha256HexStr: TypeAlias = str


def hash_str(s: str) -> Sha256HexStr:
    """Given an input string, returns a checksum suitable for use in Sigsum.

    This is a convenience function. The algorithm is SHA256, but the caller
    doesn't necessarily need to concern themselves with such details.

    The Sigsum CLI tools allow to pass in a raw file path (by leaving off the
    option `--raw-hash`). The wrapper does not -- it accepts *only* raw hashes.

    """
    assert isinstance(s, str)
    hash_object = hashlib.sha256(s.encode())
    hex_dig = hash_object.hexdigest()
    return hex_dig


# def hash_bytes(b: bytes) -> Sha256HexStr:
#     """NOT YET IMPLEMENTED."""
#     ...
