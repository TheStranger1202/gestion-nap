"""
Controladores API REST para la gestión de Cajas NAP y telemetría de puertos ópticos.

Ruta base: /api/v1/naps
Este módulo implementa los endpoints requeridos para la interacción entre el frontend
(Leaflet + JS nativo), los scripts de simulación y el motor de evaluación de señal ITU-T G.984.
Respeta la regla de arquitectura del proyecto: uso exclusivo de SQLModel para esquemas DTO.
"""

import math
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Field, SQLModel

# Dependencia de autenticación JWT
from app.api.v1.auth import get_current_user

# Importación del dominio y servicio desacoplado existente
from app.models.nap import ClaseSFP
from app.services.nap_service import evaluar_salud_optica

# Instanciación del router con prefijo y tag para documentación Swagger / OpenAPI
router = APIRouter(prefix="/api/v1/naps", tags=["Gestión NAP"])


# ==============================================================================
# Esquemas DTO (SQLModel - Cumplimiento Estrategia de Blindaje)
# ==============================================================================


class CajaNAPCreate(SQLModel):
    """Esquema de entrada para el registro de una nueva Caja NAP."""

    id_nap: str = Field(
        min_length=5,
        max_length=32,
        description="Identificador único o código normalizado de la Caja NAP",
    )
    sector: str = Field(
        min_length=2,
        max_length=16,
        description="Acrónimo o nombre del sector territorial",
    )
    latitud: float = Field(
        ge=-90.0,
        le=90.0,
        description="Latitud geográfica en formato decimal WGS84",
    )
    longitud: float = Field(
        ge=-180.0,
        le=180.0,
        description="Longitud geográfica en formato decimal WGS84",
    )
    capacidad_puertos: int = Field(
        ge=1,
        le=64,
        description="Cantidad total de puertos de salida física (ej. 8 o 16)",
    )


class LecturaTelemetria(SQLModel):
    """Esquema de entrada para la ingesta de telemetría de potencia óptica."""

    puerto_id: int = Field(
        ge=1,
        description="Identificador del puerto físico evaluado",
    )
    potencia_rx_1490_dbm: float = Field(
        ge=-60.0,
        le=10.0,
        description="Potencia óptica recibida downstream a 1490 nm en dBm",
    )
    potencia_tx_1310_dbm: float = Field(
        ge=-20.0,
        le=15.0,
        description="Potencia óptica transmitida upstream a 1310 nm en dBm",
    )
    fuente_dato: str = Field(
        default="API",
        min_length=2,
        max_length=32,
        description="Origen de la telemetría (ej. API, SIMULADOR)",
    )
    clase_sfp: Optional[str] = Field(
        default="B+",
        max_length=16,
        description="Clase del módulo transceptor SFP óptico (B+ o C+)",
    )


# ==============================================================================
# Endpoints de la API
# ==============================================================================


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una nueva Caja NAP (Simulación)",
    description="Recibe los parámetros de una Caja NAP y simula su creación exitosa en el sistema.",
)
def crear_caja_nap(
    caja: CajaNAPCreate,
    usuario: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Endpoint para dar de alta una Caja NAP.

    Retorna una confirmación simulada con los datos recibidos y código HTTP 201.
    """
    return {
        "mensaje": "Caja NAP registrada exitosamente (simulado)",
        "registrado_por": usuario["username"],
        "datos": caja.model_dump(),
    }


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Listar Cajas NAP de prueba",
    description="Devuelve una lista preconfigurada de Cajas NAP para renderizado en frontend o mapas.",
)
def listar_cajas_nap(
    usuario: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """
    Endpoint para consultar el catálogo de Cajas NAP activas.

    Retorna registros con coordenadas geográficas y capacidades
    para alimentar la capa visual (Leaflet).
    """
    return [
        {
            "id_nap": "PLZ-Z04-NCA-D001-012-A",
            "sector": "NCA",
            "ubicacion_referencia": "Av. Principal Nueva Casarapa, Poste 12",
            "latitud": 10.4682,
            "longitud": -66.6125,
            "capacidad_puertos": 8,
            "puertos_disponibles": 5,
            "estado": "OPERATIVO",
        },
        {
            "id_nap": "PLZ-Z01-CEN-D002-005-F",
            "sector": "CEN",
            "ubicacion_referencia": "Calle Comercio, Casco Histórico, Fachada Edf. Sucre",
            "latitud": 10.4735,
            "longitud": -66.6080,
            "capacidad_puertos": 16,
            "puertos_disponibles": 2,
            "estado": "CRITICO",
        },
    ]


@router.post(
    "/lecturas",
    status_code=status.HTTP_201_CREATED,
    summary="Ingestar lectura de telemetría y calcular diagnóstico",
    description="Recibe los datos de potencia óptica de un puerto, calcula su estado mediante el servicio ITU-T G.984 y retorna el dictamen.",
)
def registrar_lectura(
    lectura: LecturaTelemetria,
    usuario: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Endpoint para ingesta de telemetría de red GPON.

    Ejecuta `evaluar_salud_optica` del servicio desacoplado y retorna
    el diagnóstico calculado para el puerto indicado.
    """
    if not math.isfinite(lectura.potencia_rx_1490_dbm) or not math.isfinite(
        lectura.potencia_tx_1310_dbm
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Los valores de potencia óptica deben ser números finitos.",
        )

    sfp_raw = (lectura.clase_sfp or "B+").strip().upper()
    try:
        clase_sfp_enum = ClaseSFP(sfp_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Clase SFP no soportada: '{lectura.clase_sfp}'. Valores permitidos: B+, C+.",
        ) from exc

    try:
        estado_optico = evaluar_salud_optica(
            potencia_rx_1490_dbm=lectura.potencia_rx_1490_dbm,
            clase_sfp=clase_sfp_enum,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return {
        "mensaje": "Lectura de telemetría procesada exitosamente",
        "registrado_por": usuario["username"],
        "puerto_id": lectura.puerto_id,
        "diagnostico": estado_optico.value,
        "potencia_rx_1490_dbm": lectura.potencia_rx_1490_dbm,
        "clase_sfp": clase_sfp_enum.value,
        "fuente_dato": lectura.fuente_dato,
    }
