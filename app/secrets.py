import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


class SecretDecryptionError(RuntimeError):
    pass


def _cipher_from_value(value, context):
    derived_key = hashlib.sha256(context + value.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived_key))


def _credential_cipher():
    return _cipher_from_value(current_app.config["CREDENTIAL_ENCRYPTION_KEY"], b"research-assistant-credential-key:")


def _legacy_cipher():
    return _cipher_from_value(current_app.config["SECRET_KEY"], b"research-assistant-api-key:")


def encrypt_secret(value):
    if not value:
        return ""
    return _credential_cipher().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value):
    if not value:
        return ""
    encoded = value.encode("ascii")
    for cipher in (_credential_cipher(), _legacy_cipher()):
        try:
            return cipher.decrypt(encoded).decode("utf-8")
        except (InvalidToken, ValueError):
            continue
    raise SecretDecryptionError("无法解密已保存的 API Key，请重新输入并保存。")
