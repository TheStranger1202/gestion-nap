"""
Punto de entrada principal endurecido de la API REST - Gestión NAP (Municipio Plaza).
"""

import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import auth, naps

logger = logging.getLogger("gestion_nap.main")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

app = FastAPI(
    title="Gestión NAP | API FTTH-GPON",
    description="Backend para gestión georreferenciada, telemetría óptica y auditoría de cajas NAP en el Municipio Plaza.",
    version="1.0.0",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# 1. Validación de cabecera Host (anti Host-Header Injection)
DEFAULT_HOSTS = "localhost,127.0.0.1" if IS_PRODUCTION else "localhost,127.0.0.1,testserver"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("ALLOWED_HOSTS", DEFAULT_HOSTS).split(",")
    if h.strip()
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# 2. CORS estricto con orígenes explícitos (compatible con credenciales y fetch local)
DEFAULT_ORIGINS = (
    "http://localhost:8080,http://127.0.0.1:8080,"
    "http://localhost:5500,http://127.0.0.1:5500,"
    "http://localhost:8000,http://127.0.0.1:8000"
)
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", DEFAULT_ORIGINS).split(",")
    if o.strip() and o.strip() != "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,  # Se usa Authorization: Bearer (no cookies), mitigando CSRF
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=600,
)


# 3. Middleware de Cabeceras de Seguridad HTTP
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


# 4. Manejador Global de Errores (evita filtrar stack traces o rutas internas)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor. Contacta al administrador."},
    )


app.include_router(auth.router)
app.include_router(naps.router)


@app.get("/health", tags=["Sistema"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "gestion-nap-api"}
