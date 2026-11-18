"""
Controlador y dependencias de autenticación JWT endurecidas - Gestión NAP.
Ruta base: /api/v1/auth
"""

import base64
from collections import deque
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import unicodedata
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import SQLModel

logger = logging.getLogger("gestion_nap.auth")

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ==============================================================================
# Configuración Criptográfica y Políticas de Seguridad
# ==============================================================================

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
_ENV_SECRET = os.getenv("JWT_SECRET_KEY", "").strip()

if ENVIRONMENT == "production":
    if len(_ENV_SECRET) < 32:
        raise RuntimeError(
            "CRÍTICO: En producción JWT_SECRET_KEY debe estar definida y tener al menos 32 caracteres."
        )
    SECRET_KEY = _ENV_SECRET
else:
    if len(_ENV_SECRET) >= 32:
        SECRET_KEY = _ENV_SECRET
    else:
        SECRET_KEY = secrets.token_urlsafe(48)
        logger.warning(
            "JWT_SECRET_KEY no configurada o débil; usando clave efímera para desarrollo."
        )

JWT_ISSUER = "gestion-nap-plaza-api"
JWT_AUDIENCE = "gestion-nap-frontend"
ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60 * 4  # 4 horas

MAX_USERNAME_LEN = 128
MAX_PASSWORD_LEN = 128
PBKDF2_ITERATIONS = 210_000


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt_bytes = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt_bytes.hex()}${dk.hex()}"


def _verify_password(plain_password: str, stored_hash: str) -> bool:
    try:
        algorithm, iter_str, salt_hex, hash_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iter_str)
        salt_bytes = bytes.fromhex(salt_hex)
        expected_dk = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False

    computed_dk = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        salt_bytes,
        iterations,
    )
    return hmac.compare_digest(computed_dk, expected_dk)


# Hash ficticio precalculado para igualar latencia cuando el usuario no existe
_DUMMY_PASSWORD_HASH = _hash_password("dummy-timing-equalizer-secret")

# Almacén de usuarios con hashes salados (reemplazar por consulta SQLite en producción)
USERS_DB: dict[str, dict[str, Any]] = {
    "operador@gestionnap.ve": {
        "username": "operador@gestionnap.ve",
        "role": "operador",
        "disabled": False,
        "password_hash": _hash_password("plaza2026"),
    },
    "admin": {
        "username": "admin",
        "role": "admin",
        "disabled": False,
        "password_hash": _hash_password("admin123"),
    },
}


# ==============================================================================
# Rate Limiter Acotado en Memoria (Protección contra Fuerza Bruta y OOM DoS)
# ==============================================================================

RATE_LIMIT_WINDOW_SEC = 60
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_MAX_KEYS = 5000
_failed_attempts: dict[str, deque[float]] = {}


def _get_client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _check_rate_limit(key: str) -> None:
    now = time.monotonic()
    bucket = _failed_attempts.get(key)
    if not bucket:
        return
    while bucket and (now - bucket[0]) > RATE_LIMIT_WINDOW_SEC:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Espera 60 segundos antes de reintentar.",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW_SEC)},
        )
    if not bucket:
        _failed_attempts.pop(key, None)


def _record_failed_attempt(key: str) -> None:
    now = time.monotonic()
    if key not in _failed_attempts and len(_failed_attempts) >= RATE_LIMIT_MAX_KEYS:
        # Evicción FIFO para evitar agotamiento de RAM bajo ataque distribuido
        oldest_key = next(iter(_failed_attempts))
        _failed_attempts.pop(oldest_key, None)
    bucket = _failed_attempts.setdefault(key, deque())
    bucket.append(now)


def _clear_failed_attempts(key: str) -> None:
    _failed_attempts.pop(key, None)


# ==============================================================================
# Esquemas DTO y Utilidades JWT (HS256 estricto)
# ==============================================================================


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(
    subject: str,
    role: str = "operador",
    expires_in: int = ACCESS_TOKEN_EXPIRE_SECONDS,
) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": subject,
        "role": role,
        "iat": now,
        "nbf": now,
        "exp": now + expires_in,
        "jti": secrets.token_hex(16),
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def decode_and_verify_token(token: str) -> dict[str, Any]:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token de sesión inválido o expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise credentials_exc

        header_b64, payload_b64, sig_b64 = parts
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        # Fijar algoritmo para prevenir ataques 'alg: none' o confusión de clave
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise credentials_exc

        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = hmac.new(
            SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256
        ).digest()
        provided_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, provided_sig):
            raise credentials_exc

        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except HTTPException:
        raise
    except Exception:
        raise credentials_exc

    now = int(time.time())
    if payload.get("iss") != JWT_ISSUER or payload.get("aud") != JWT_AUDIENCE:
        raise credentials_exc
    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        raise credentials_exc
    if not isinstance(payload.get("exp"), int) or payload["exp"] <= now:
        raise credentials_exc
    if isinstance(payload.get("nbf"), int) and payload["nbf"] > (now + 30):
        raise credentials_exc

    return payload


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """Dependencia FastAPI para proteger endpoints que requieran sesión válida."""
    payload = decode_and_verify_token(token)
    user = USERS_DB.get(payload["sub"])
    if not user or user.get("disabled"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autorizado o deshabilitado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": user["username"], "role": user["role"]}


# ==============================================================================
# Endpoint de Autenticación
# ==============================================================================


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Autenticar operador y emitir token JWT",
)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> dict[str, Any]:
    client_ip = _get_client_ip(request)
    raw_username = unicodedata.normalize("NFKC", form_data.username).strip().lower()
    raw_password = form_data.password

    # Rechazar entradas malformadas o gigantes antes de ejecutar PBKDF2 (anti-DoS)
    if (
        not raw_username
        or not raw_password
        or "\x00" in raw_username
        or "\x00" in raw_password
        or len(raw_username) > MAX_USERNAME_LEN
        or len(raw_password) > MAX_PASSWORD_LEN
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    rate_key = f"{client_ip}:{raw_username}"
    _check_rate_limit(rate_key)

    user = USERS_DB.get(raw_username)
    target_hash = user["password_hash"] if user else _DUMMY_PASSWORD_HASH
    password_ok = _verify_password(raw_password, target_hash)

    if not user or user.get("disabled") or not password_ok:
        _record_failed_attempt(rate_key)
        logger.warning("Intento de acceso fallido para '%s' desde %s", raw_username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _clear_failed_attempts(rate_key)
    token = create_access_token(subject=user["username"], role=user["role"])
    return {"access_token": token, "token_type": "bearer"}
