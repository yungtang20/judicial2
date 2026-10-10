from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(RuntimeError):
    pass


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> tuple[_Blob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(data)
    return _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _dpapi(data: bytes, decrypt: bool) -> bytes:
    if os.name != "nt":
        raise EncryptionError("案件持久化只支援 Windows DPAPI")
    in_blob, keepalive = _blob(data)
    out_blob = _Blob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if decrypt:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
        )
    else:
        ok = crypt32.CryptProtectData(
            ctypes.byref(in_blob), "JUDICIAL1 local case", None, None, None, 0,
            ctypes.byref(out_blob),
        )
    del keepalive
    if not ok:
        raise EncryptionError(f"DPAPI 作業失敗：{ctypes.GetLastError()}")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def protect_json(payload: dict[str, Any]) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _dpapi(raw, decrypt=False)


def unprotect_json(ciphertext: bytes) -> dict[str, Any]:
    try:
        return json.loads(_dpapi(ciphertext, decrypt=True).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EncryptionError("案件資料解密後格式錯誤") from exc


def test_fernet_protect_json(payload: dict[str, Any], key: bytes) -> bytes:
    """Portable test helper. Production storage never calls this function."""
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return Fernet(key).encrypt(raw)


def test_fernet_unprotect_json(ciphertext: bytes, key: bytes) -> dict[str, Any]:
    try:
        return json.loads(Fernet(key).decrypt(ciphertext).decode("utf-8"))
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EncryptionError("測試資料無法解密") from exc

