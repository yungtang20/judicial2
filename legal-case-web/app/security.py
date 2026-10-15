from __future__ import annotations

import ctypes
import json
import os
from ctypes import wintypes
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(RuntimeError):
    pass


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))] if os.name == "nt" else []


def _blob(data: bytes) -> tuple[_Blob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(data)
    return _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


_LINUX_KEY_ENV = "JUDICIAL_ENCRYPTION_KEY"
_PERSISTENT_KEY_FILE = os.path.join(os.path.dirname(__file__), "..", "data", ".encryption_key")


def _get_linux_fernet_key() -> bytes:
    """取得或產生 Linux 容器環境下的對稱加密金鑰。"""
    env_key = os.environ.get(_LINUX_KEY_ENV, "").strip()
    if env_key:
        try:
            Fernet(env_key.encode("ascii"))
            return env_key.encode("ascii")
        except Exception:
            pass
    try:
        if os.path.isfile(_PERSISTENT_KEY_FILE):
            key_data = open(_PERSISTENT_KEY_FILE, "rb").read().strip()
            if key_data:
                Fernet(key_data)
                return key_data
    except Exception:
        pass
    new_key = Fernet.generate_key()
    try:
        os.makedirs(os.path.dirname(_PERSISTENT_KEY_FILE), exist_ok=True)
        open(_PERSISTENT_KEY_FILE, "wb").write(new_key)
    except Exception:
        pass
    return new_key


def _use_linux_crypto() -> bool:
    return os.name != "nt"


def _dpapi(data: bytes, decrypt: bool) -> bytes:
    if _use_linux_crypto():
        fernet = Fernet(_get_linux_fernet_key())
        if decrypt:
            try:
                return fernet.decrypt(data)
            except Exception as exc:
                raise EncryptionError("資料解密失敗") from exc
        return fernet.encrypt(data)

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

