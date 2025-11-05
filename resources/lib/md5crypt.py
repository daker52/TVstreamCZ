"""Lightweight implementation of the MD5-CRYPT algorithm used by Webshare."""
from __future__ import annotations

import hashlib
from typing import Union

_ITOA64 = b"./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_MAGIC = b"$1$"


def _to64(value: int, length: int) -> str:
    """Encode ``value`` using the modified base64 alphabet employed by md5-crypt."""
    chars = []
    for _ in range(length):
        chars.append(chr(_ITOA64[value & 0x3F]))
        value >>= 6
    return "".join(chars)


def md5_crypt(password: Union[str, bytes], salt: Union[str, bytes]) -> str:
    """Return the MD5-CRYPT hash for ``password`` and ``salt``.

    The implementation follows the original reference from FreeBSD ``crypt(3)``
    so that the resulting digest is compatible with services that expect
    ``$1$salt$hash``.
    """
    if isinstance(password, str):
        password_bytes = password.encode("utf-8")
    else:
        password_bytes = password

    if isinstance(salt, str):
        salt_bytes = salt.encode("utf-8")
    else:
        salt_bytes = salt

    if salt_bytes.startswith(_MAGIC):
        salt_bytes = salt_bytes[len(_MAGIC) :]
    if b"$" in salt_bytes:
        salt_bytes = salt_bytes.split(b"$", 1)[0]
    salt_bytes = salt_bytes[:8]

    ctx = hashlib.md5()
    ctx.update(password_bytes)
    ctx.update(_MAGIC)
    ctx.update(salt_bytes)

    alt = hashlib.md5()
    alt.update(password_bytes)
    alt.update(salt_bytes)
    alt.update(password_bytes)
    alt_digest = alt.digest()

    pwd_len = len(password_bytes)
    for i in range(pwd_len):
        ctx.update(alt_digest[i % 16 : (i % 16) + 1])

    i = pwd_len
    while i > 0:
        if i & 1:
            ctx.update(b"\x00")
        else:
            ctx.update(password_bytes[:1])
        i >>= 1

    final = ctx.digest()

    for i in range(1000):
        ctx = hashlib.md5()
        if i % 2:
            ctx.update(password_bytes)
        else:
            ctx.update(final)
        if i % 3:
            ctx.update(salt_bytes)
        if i % 7:
            ctx.update(password_bytes)
        if i % 2:
            ctx.update(final)
        else:
            ctx.update(password_bytes)
        final = ctx.digest()

    result = _MAGIC + salt_bytes + b"$"
    result += _to64((final[0] << 16) | (final[6] << 8) | final[12], 4).encode("ascii")
    result += _to64((final[1] << 16) | (final[7] << 8) | final[13], 4).encode("ascii")
    result += _to64((final[2] << 16) | (final[8] << 8) | final[14], 4).encode("ascii")
    result += _to64((final[3] << 16) | (final[9] << 8) | final[15], 4).encode("ascii")
    result += _to64((final[4] << 16) | (final[10] << 8) | final[5], 4).encode("ascii")
    result += _to64(final[11], 2).encode("ascii")

    return result.decode("ascii")
