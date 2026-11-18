"""
Controladores API REST para la gestión de Cajas NAP y telemetría de puertos ópticos.

Ruta base: /api/v1/naps
Este módulo implementa los endpoints requeridos para la interacción entre el frontend
(Alpine.js + mapas Leaflet), los scripts de simulación y el motor de evaluación de señal.
Respeta la regla de arquitectura del proyecto: uso exclusivo de SQLModel para esquemas DTO.
"""

from typing import Any, Optional
from fastapi import APIRouter, status
from sqlmodel import Field, SQLModel

# Importación de la lógica de evaluación (servicio desacoplado)
from app.services.nap_service import evaluar_estado_senal

# Instanciación del router con prefijo y tag para documentación Swagger / OpenAPI
router = APIRouter(prefix="/api/v1/naps", tags=["Gestión NAP"])


# ==============================================================================
# Esquemas DTO (SQLModel - Cumplimiento Estrategia de Blindaje)
# ==============================================================================


class CajaNAPCreate(SQLModel):
    """Esquema de entrada para el registro de una nueva Caja NAP."""

    id_nap: str = Field(
        description="Identificador único o código normalizado de la Caja NAP",
    )
    sector: str = Field(
        description="Acrónimo o nombre del sector territorial",
    )
    latitud: float = Field(
        description="Latitud geográfica en formato decimal WGS84",
    )
    longitud: float = Field(
        description="Longitud geográfica en formato decimal WGS84",
    )
    capacidad_puertos: int = Field(
        description="Cantidad total de puertos de salida física (ej. 8 o 16)",
    )


class LecturaTelemetria(SQLModel):
    """Esquema de entrada para la ingesta de telemetría de potencia óptica."""

    puerto_id: int = Field(
        description="Identificador del puerto físico evaluado",
    )
    potencia_rx_1490_dbm: float = Field(
        description="Potencia óptica recibida downstream a 1490 nm en dBm",
    )
    potencia_tx_1310_dbm: float = Field(
        description="Potencia óptica transmitida upstream a 1310 nm en dBm",
    )
    fuente_dato: str = Field(
        default="API",
        description="Origen de la telemetría (ej. API, SIMULADOR)",
    )
    clase_sfp: Optional[str] = Field(
        default="B+",
        description="Clase del módulo transceptor SFP óptico (opcional)",
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
def crear_caja_nap(caja: CajaNAPCreate) -> dict[str, Any]:
    """
    Endpoint para dar de alta una Caja NAP.

    Retorna una confirmación simulada con los datos recibidos y código HTTP 201.
    """
    return {
        "mensaje": "Caja NAP registrada exitosamente (simulado)",
        "datos": caja.model_dump(),
    }


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Listar Cajas NAP de prueba",
    description="Devuelve una lista preconfigurada de Cajas NAP para renderizado en frontend o mapas.",
)
def listar_cajas_nap() -> list[dict[str, Any]]:
    """
    Endpoint para consultar el catálogo de Cajas NAP activas.

    Retorna registros con coordenadas geográficas y capacidades
    para alimentar la capa visual (Alpine.js / Leaflet).
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
    description="Recibe los datos de potencia óptica de un puerto, calcula su estado mediante el servicio y retorna el dictamen.",
)
def registrar_lectura(lectura: LecturaTelemetria) -> dict[str, Any]:
    """
    Endpoint para ingesta de telemetría de red GPON.

    Ejecuta la función `evaluar_estado_senal` del servicio desacoplado y retorna
    el diagnóstico calculado para el puerto indicado compatible con `emulador_telemetria.py`.
    """
    diagnostico = evaluar_estado_senal(lectura.potencia_rx_1490_dbm)

    return {
        "mensaje": "Lectura de telemetría procesada exitosamente",
        "puerto_id": lectura.puerto_id,
        "diagnostico": diagnostico,
        "potencia_rx_1490_dbm": lectura.potencia_rx_1490_dbm,
        "fuente_dato": lectura.fuente_dato,
    }
