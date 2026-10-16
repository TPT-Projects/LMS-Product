"""Encrypt secrets at rest (Meta access tokens), as spec section 11 requires."""

import base64
import hashlib
import logging
from functools import cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


@cache
def _fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        if not settings.DEBUG:
            raise RuntimeError("Set FIELD_ENCRYPTION_KEY to store Meta tokens.")
        # Development only: a stable key derived from SECRET_KEY.
        logger.warning("FIELD_ENCRYPTION_KEY is empty; deriving a development key.")
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        logger.error("Could not decrypt a stored secret (wrong FIELD_ENCRYPTION_KEY?)")
        return ""
