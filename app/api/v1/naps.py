"""
Controladores API REST para la gestión de Cajas NAP y telemetría de puertos ópticos.

Ruta base: /api/v1/naps
Conectado a la base de datos SQLite (gestion_nap.db) mediante SQLModel y la capa
de servicios de dominio (`app/services/nap_service.py`).
"""

import math
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Field, Session, SQLModel, select

from app.api.v1.auth import get_current_user
from app.core.database import get_session
from app.models.nap import (
    ClaseSFP,
    EstadoFisicoNAP,
    EstadoPotencia,
    EstadoPuerto,
    FuenteDato,
    LecturaPotencia,
    LecturaPotenciaCreate,
    NAP,
    NAPCreate,
    Puerto,
)
from app.services.nap_service import (
    NAPDuplicadaError,
    NAPNoEncontradaError,
    NAPServiceError,
    PuertoNoEncontradoError,
    crear_nap_con_puertos,
    listar_puertos_por_nap,
    obtener_nap_por_id,
    registrar_lectura_potencia,
)

router = APIRouter(prefix="/api/v1/naps", tags=["Gestión NAP"])


# ==============================================================================
# Esquemas DTO de Entrada/Salida
# ==============================================================================


class LecturaTelemetriaIn(SQLModel):
    """Esquema flexible para ingesta desde formulario de campo (codigo_nap + puerto) o API (puerto_id)."""

    puerto_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Clave primaria del puerto físico en BD (opcional si se envía codigo_nap).",
    )
    codigo_nap: Optional[str] = Field(
        default=None,
        min_length=5,
        max_length=25,
        description="Código normalizado de la Caja NAP (ej. PLZ-Z04-NCA-D001-012-A).",
    )
    numero_puerto: Optional[int] = Field(
        default=None,
        ge=1,
        le=16,
        description="Número de puerto físico dentro de la Caja NAP (1 a 16).",
    )
    potencia_rx_1490_dbm: float = Field(
        ge=-50.0,
        le=10.0,
        description="Potencia óptica recibida downstream a 1490 nm en dBm.",
    )
    potencia_tx_1310_dbm: Optional[float] = Field(
        default=None,
        ge=-10.0,
        le=15.0,
        description="Potencia óptica transmitida upstream a 1310 nm en dBm.",
    )
    fuente_dato: str = Field(
        default="MANUAL",
        min_length=2,
        max_length=32,
        description="Origen de la telemetría (MANUAL, SIMULADOR, SNMP_OLT).",
    )
    clase_sfp: Optional[str] = Field(
        default="B+",
        max_length=16,
        description="Clase del módulo transceptor SFP óptico (B+ o C+).",
    )


# ==============================================================================
# Helpers de Consulta y Agregación
# ==============================================================================


def _obtener_ultima_lectura_puerto(
    session: Session, puerto_id: int
) -> Optional[LecturaPotencia]:
    stmt = (
        select(LecturaPotencia)
        .where(LecturaPotencia.puerto_id == puerto_id)
        .order_by(LecturaPotencia.timestamp.desc(), LecturaPotencia.id.desc())  # type: ignore[union-attr]
        .limit(1)
    )
    return session.exec(stmt).first()


def _calcular_estado_general_nap(
    session: Session, nap: NAP, puertos: list[Puerto]
) -> tuple[str, int]:
    """Determina (estado_general, puertos_disponibles) evaluando física y telemetría."""
    disponibles = sum(
        1 for p in puertos if p.estado_puerto == EstadoPuerto.DISPONIBLE
    )

    if nap.estado_fisico in (
        EstadoFisicoNAP.DETERIORADO,
        EstadoFisicoNAP.VANDALIZADO,
    ):
        return "CRITICO", disponibles

    for puerto in puertos:
        if puerto.estado_puerto in (
            EstadoPuerto.DANADO,
            EstadoPuerto.ATENUACION_ALTA,
        ):
            return "CRITICO", disponibles

        if puerto.id is not None:
            ultima = _obtener_ultima_lectura_puerto(session, puerto.id)
            if ultima and ultima.estado_calculado in (
                EstadoPotencia.CRITICO,
                EstadoPotencia.CAIDO,
            ):
                return "CRITICO", disponibles

    if nap.estado_fisico == EstadoFisicoNAP.MANTENIMIENTO:
        return "ADVERTENCIA", disponibles

    return "OPTIMO", disponibles


# ==============================================================================
# Endpoints de la API
# ==============================================================================


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una nueva Caja NAP en SQLite con sus puertos SC/APC",
)
def crear_caja_nap(
    caja: NAPCreate,
    session: Session = Depends(get_session),
    usuario: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if usuario.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden dar de alta nuevas Cajas NAP.",
        )

    try:
        nap_creada = crear_nap_con_puertos(session, caja)
    except NAPDuplicadaError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except NAPServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "mensaje": "Caja NAP registrada exitosamente en base de datos",
        "registrado_por": usuario["username"],
        "datos": {
            "id": nap_creada.id,
            "codigo_nap": nap_creada.codigo_nap,
            "id_nap": nap_creada.codigo_nap,
            "zona": nap_creada.zona.value,
            "sector": nap_creada.sector,
            "ubicacion_referencia": nap_creada.ubicacion_referencia,
            "latitud": nap_creada.latitud,
            "longitud": nap_creada.longitud,
            "capacidad_puertos": nap_creada.capacidad_puertos,
            "puertos_disponibles": nap_creada.capacidad_puertos,
            "estado_fisico": nap_creada.estado_fisico.value,
            "estado_general": "OPTIMO",
        },
    }


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Listar Cajas NAP georreferenciadas desde SQLite",
)
def listar_cajas_nap(
    session: Session = Depends(get_session),
    usuario: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    naps = session.exec(select(NAP).order_by(NAP.id.asc())).all()  # type: ignore[union-attr]
    resultado: list[dict[str, Any]] = []

    for nap in naps:
        if nap.id is None:
            continue
        puertos = list(listar_puertos_por_nap(session, nap.id))
        estado_general, disponibles = _calcular_estado_general_nap(
            session, nap, puertos
        )
        resultado.append(
            {
                "id": nap.id,
                "codigo_nap": nap.codigo_nap,
                "id_nap": nap.codigo_nap,
                "zona": nap.zona.value,
                "sector": nap.sector,
                "ubicacion_referencia": nap.ubicacion_referencia,
                "latitud": nap.latitud,
                "longitud": nap.longitud,
                "tipo_montaje": nap.tipo_montaje.value,
                "capacidad_puertos": nap.capacidad_puertos,
                "puertos_disponibles": disponibles,
                "splitter_ratio": nap.splitter_ratio.value,
                "estado_fisico": nap.estado_fisico.value,
                "estado_general": estado_general,
                "estado": estado_general,
            }
        )

    return resultado


@router.get(
    "/resumen/kpis",
    status_code=status.HTTP_200_OK,
    summary="Obtener KPIs agregados y alertas recientes para el Dashboard",
)
def obtener_resumen_kpis(
    session: Session = Depends(get_session),
    usuario: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    naps = session.exec(select(NAP)).all()
    puertos = session.exec(select(Puerto)).all()

    conectados = sum(1 for p in puertos if p.estado_puerto == EstadoPuerto.CONECTADO)
    disponibles = sum(1 for p in puertos if p.estado_puerto == EstadoPuerto.DISPONIBLE)
    reservados = sum(1 for p in puertos if p.estado_puerto == EstadoPuerto.RESERVADO)
    danados = sum(
        1
        for p in puertos
        if p.estado_puerto in (EstadoPuerto.DANADO, EstadoPuerto.ATENUACION_ALTA)
    )

    optimo = 0
    critico = 0
    caido = 0
    alertas_recientes: list[dict[str, Any]] = []

    naps_by_id = {n.id: n for n in naps if n.id is not None}

    for puerto in puertos:
        if puerto.id is None:
            continue
        ultima = _obtener_ultima_lectura_puerto(session, puerto.id)
        if not ultima:
            continue
        if ultima.estado_calculado == EstadoPotencia.OPTIMO:
            optimo += 1
        elif ultima.estado_calculado == EstadoPotencia.CRITICO:
            critico += 1
        elif ultima.estado_calculado == EstadoPotencia.CAIDO:
            caido += 1

        if ultima.estado_calculado in (EstadoPotencia.CRITICO, EstadoPotencia.CAIDO):
            nap_padre = naps_by_id.get(puerto.nap_id)
            alertas_recientes.append(
                {
                    "codigo_nap": nap_padre.codigo_nap if nap_padre else f"NAP-{puerto.nap_id}",
                    "puerto": puerto.numero_puerto,
                    "motivo": f"Potencia óptica fuera de umbral ({ultima.potencia_rx_1490_dbm:.2f} dBm)",
                    "nivel": ultima.estado_calculado.value,
                }
            )

    return {
        "inventario": {
            "total_cajas_nap": len(naps),
            "total_puertos": len(puertos),
        },
        "estado_puertos": {
            "conectados": conectados,
            "disponibles": disponibles,
            "reservados": reservados,
            "danados": danados,
        },
        "salud_optica": {
            "optimo": optimo,
            "critico": critico,
            "caido": caido,
        },
        "alertas_recientes": alertas_recientes[:15],
    }


@router.get(
    "/{nap_id}",
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle técnico y puertos de una Caja NAP para auditoría",
)
def obtener_detalle_nap(
    nap_id: int,
    session: Session = Depends(get_session),
    usuario: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        nap = obtener_nap_por_id(session, nap_id)
    except NAPNoEncontradaError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    puertos = listar_puertos_por_nap(session, nap_id)
    puertos_payload: list[dict[str, Any]] = []

    for puerto in puertos:
        ultima = (
            _obtener_ultima_lectura_puerto(session, puerto.id)
            if puerto.id is not None
            else None
        )
        puertos_payload.append(
            {
                "id": puerto.id,
                "numero_puerto": puerto.numero_puerto,
                "estado_puerto": puerto.estado_puerto.value,
                "tipo_conector": puerto.tipo_conector,
                "codigo_cliente": puerto.codigo_cliente,
                "ultima_lectura": (
                    {
                        "potencia_rx_1490_dbm": ultima.potencia_rx_1490_dbm,
                        "potencia_tx_1310_dbm": ultima.potencia_tx_1310_dbm,
                        "estado_calculado": ultima.estado_calculado.value,
                        "timestamp": ultima.timestamp.isoformat(),
                    }
                    if ultima
                    else None
                ),
            }
        )

    return {
        "id": nap.id,
        "codigo_nap": nap.codigo_nap,
        "zona": nap.zona.value,
        "sector": nap.sector,
        "ubicacion_referencia": nap.ubicacion_referencia,
        "capacidad_puertos": nap.capacidad_puertos,
        "splitter_ratio": nap.splitter_ratio.value,
        "tubo_color_tia598": nap.tubo_color_tia598.value,
        "hilo_color_tia598": nap.hilo_color_tia598.value,
        "estado_fisico": nap.estado_fisico.value,
        "puertos": puertos_payload,
    }


@router.post(
    "/lecturas",
    status_code=status.HTTP_201_CREATED,
    summary="Ingestar lectura de telemetría en SQLite y calcular diagnóstico ITU-T G.984",
)
def registrar_lectura(
    lectura: LecturaTelemetriaIn,
    session: Session = Depends(get_session),
    usuario: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if not math.isfinite(lectura.potencia_rx_1490_dbm) or (
        lectura.potencia_tx_1310_dbm is not None
        and not math.isfinite(lectura.potencia_tx_1310_dbm)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Los valores de potencia óptica deben ser números finitos.",
        )

    # Resolver el puerto destino (por codigo_nap + numero_puerto o por puerto_id directo)
    puerto_destino: Optional[Puerto] = None

    if lectura.codigo_nap:
        codigo_norm = lectura.codigo_nap.strip().upper()
        nap = session.exec(select(NAP).where(NAP.codigo_nap == codigo_norm)).first()
        if nap is None or nap.id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe una Caja NAP registrada con código '{codigo_norm}'.",
            )
        num_puerto = lectura.numero_puerto or lectura.puerto_id
        if num_puerto is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Debes indicar el número de puerto (1-16) junto al código NAP.",
            )
        puerto_destino = session.exec(
            select(Puerto).where(
                Puerto.nap_id == nap.id,
                Puerto.numero_puerto == num_puerto,
            )
        ).first()
        if puerto_destino is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El puerto #{num_puerto} no existe en la Caja NAP '{codigo_norm}'.",
            )
    elif lectura.puerto_id is not None:
        puerto_destino = session.get(Puerto, lectura.puerto_id)
        if puerto_destino is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe el puerto óptico con id={lectura.puerto_id}.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Debes enviar 'codigo_nap' y 'numero_puerto', o bien 'puerto_id'.",
        )

    assert puerto_destino.id is not None

    sfp_raw = (lectura.clase_sfp or "B+").strip().upper()
    try:
        clase_sfp_enum = ClaseSFP(sfp_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Clase SFP no soportada: '{lectura.clase_sfp}'. Valores permitidos: B+, C+.",
        ) from exc

    fuente_raw = (lectura.fuente_dato or "MANUAL").strip().upper()
    if fuente_raw == "API":
        fuente_raw = "MANUAL"
    try:
        fuente_enum = FuenteDato(fuente_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Fuente de dato no soportada: '{lectura.fuente_dato}'.",
        ) from exc

    lectura_in = LecturaPotenciaCreate(
        puerto_id=puerto_destino.id,
        potencia_rx_1490_dbm=lectura.potencia_rx_1490_dbm,
        potencia_tx_1310_dbm=lectura.potencia_tx_1310_dbm,
        clase_sfp=clase_sfp_enum,
        fuente_dato=fuente_enum,
    )

    try:
        lectura_guardada = registrar_lectura_potencia(session, lectura_in)
    except PuertoNoEncontradoError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NAPServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Sincronizar estado operativo del puerto en base al dictamen óptico
    if lectura_guardada.estado_calculado in (
        EstadoPotencia.CRITICO,
        EstadoPotencia.CAIDO,
    ):
        puerto_destino.estado_puerto = EstadoPuerto.ATENUACION_ALTA
    elif puerto_destino.estado_puerto in (
        EstadoPuerto.DISPONIBLE,
        EstadoPuerto.ATENUACION_ALTA,
    ):
        puerto_destino.estado_puerto = EstadoPuerto.CONECTADO

    session.add(puerto_destino)
    session.commit()

    return {
        "mensaje": "Lectura de telemetría registrada en base de datos",
        "registrado_por": usuario["username"],
        "lectura_id": lectura_guardada.id,
        "puerto_id": puerto_destino.id,
        "numero_puerto": puerto_destino.numero_puerto,
        "diagnostico": lectura_guardada.estado_calculado.value,
        "potencia_rx_1490_dbm": lectura_guardada.potencia_rx_1490_dbm,
        "clase_sfp": lectura_guardada.clase_sfp.value,
        "fuente_dato": lectura_guardada.fuente_dato.value,
    }
