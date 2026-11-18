"""
Capa de servicios de dominio FTTH-GPON para la gestión de Cajas NAP,
aprovisionamiento automático de puertos ópticos e ingesta de telemetría
bajo umbrales normalizados ITU-T G.984.2.
"""

import math
from typing import Sequence

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.nap import (
    NAP,
    ClaseSFP,
    EstadoPotencia,
    EstadoPuerto,
    LecturaPotencia,
    LecturaPotenciaCreate,
    NAPCreate,
    Puerto,
)

# Umbrales ópticos downstream (1490 nm) según norma ITU-T G.984.2 (en dBm)
UMBRAL_SATURACION_DBM: float = -8.0

UMBRALES_POR_CLASE_SFP: dict[ClaseSFP, tuple[float, float]] = {
    # (limite_inferior_optimo_dbm, limite_inferior_critico_dbm)
    ClaseSFP.B_PLUS: (-24.0, -27.0),
    ClaseSFP.C_PLUS: (-26.0, -29.0),
}


# ==============================================================================
# EXCEPCIONES DE DOMINIO
# ==============================================================================


class NAPServiceError(Exception):
    """Excepción base para errores de reglas de negocio en el servicio NAP."""


class NAPDuplicadaError(NAPServiceError):
    """Se lanza cuando se intenta registrar una Caja NAP con código existente."""


class NAPNoEncontradaError(NAPServiceError):
    """Se lanza cuando el identificador de la Caja NAP no existe en inventario."""


class PuertoNoEncontradoError(NAPServiceError):
    """Se lanza cuando el puerto óptico destino no existe en base de datos."""


# ==============================================================================
# LÓGICA DE EVALUACIÓN ÓPTICA (ITU-T G.984)
# ==============================================================================


def evaluar_salud_optica(
    potencia_rx_1490_dbm: float,
    clase_sfp: ClaseSFP = ClaseSFP.B_PLUS,
) -> EstadoPotencia:
    """Evalúa la potencia óptica recibida (1490 nm) según ITU-T G.984.2.

    Matriz de clasificación aplicada:
    - Saturación (> -8.0 dBm) para cualquier clase: CAIDO.
    - Clase B+:
        * OPTIMO : -24.0 <= rx <= -8.0 dBm
        * CRITICO: -27.0 <= rx < -24.0 dBm
        * CAIDO  : rx < -27.0 dBm
    - Clase C+:
        * OPTIMO : -26.0 <= rx <= -8.0 dBm
        * CRITICO: -29.0 <= rx < -26.0 dBm
        * CAIDO  : rx < -29.0 dBm

    Args:
        potencia_rx_1490_dbm: Potencia downstream recibida en dBm.
        clase_sfp: Clase del módulo transceptor SFP en la OLT (B+ o C+).

    Returns:
        EstadoPotencia: Clasificación normalizada (OPTIMO, CRITICO o CAIDO).

    Raises:
        ValueError: Si la potencia no es un número finito o la clase SFP no es válida.
    """
    if not math.isfinite(potencia_rx_1490_dbm):
        raise ValueError(
            f"La potencia óptica recibida debe ser un valor finito en dBm, "
            f"se recibió: {potencia_rx_1490_dbm!r}."
        )

    if clase_sfp not in UMBRALES_POR_CLASE_SFP:
        raise ValueError(f"Clase de módulo SFP no soportada: {clase_sfp!r}.")

    limite_optimo_min, limite_critico_min = UMBRALES_POR_CLASE_SFP[clase_sfp]

    if potencia_rx_1490_dbm > UMBRAL_SATURACION_DBM:
        return EstadoPotencia.CAIDO

    if potencia_rx_1490_dbm >= limite_optimo_min:
        return EstadoPotencia.OPTIMO

    if potencia_rx_1490_dbm >= limite_critico_min:
        return EstadoPotencia.CRITICO

    return EstadoPotencia.CAIDO


# ==============================================================================
# INGESTA DE TELEMETRÍA ÓPTICA
# ==============================================================================


def registrar_lectura_potencia(
    session: Session,
    lectura_in: LecturaPotenciaCreate,
) -> LecturaPotencia:
    """Ingesta una medición de potencia óptica y calcula su estado ITU-T G.984.

    El cálculo de `estado_calculado` se ejecuta de manera uniforme sin importar
    el origen de la captura (`MANUAL`, `SIMULADOR` o `SNMP_OLT`).

    Args:
        session: Sesión activa de base de datos SQLModel.
        lectura_in: Esquema de entrada validado con los datos de la lectura.

    Returns:
        LecturaPotencia: Registro persistido con `id`, `timestamp` y `estado_calculado`.

    Raises:
        PuertoNoEncontradoError: Si `lectura_in.puerto_id` no existe en `puertos`.
    """
    puerto = session.get(Puerto, lectura_in.puerto_id)
    if puerto is None:
        raise PuertoNoEncontradoError(
            f"No existe el puerto óptico con id={lectura_in.puerto_id} para registrar la lectura."
        )

    estado_calculado = evaluar_salud_optica(
        potencia_rx_1490_dbm=lectura_in.potencia_rx_1490_dbm,
        clase_sfp=lectura_in.clase_sfp,
    )

    db_lectura = LecturaPotencia(
        puerto_id=lectura_in.puerto_id,
        potencia_rx_1490_dbm=lectura_in.potencia_rx_1490_dbm,
        potencia_tx_1310_dbm=lectura_in.potencia_tx_1310_dbm,
        clase_sfp=lectura_in.clase_sfp,
        fuente_dato=lectura_in.fuente_dato,
        estado_calculado=estado_calculado,
    )

    try:
        session.add(db_lectura)
        session.commit()
        session.refresh(db_lectura)
    except IntegrityError as exc:
        session.rollback()
        raise NAPServiceError(
            f"Error de integridad referencial al registrar lectura en puerto {lectura_in.puerto_id}."
        ) from exc

    return db_lectura


# ==============================================================================
# GESTIÓN DE CAJAS NAP Y APROVISIONAMIENTO DE PUERTOS
# ==============================================================================


def crear_nap_con_puertos(session: Session, nap_in: NAPCreate) -> NAP:
    """Registra una Caja NAP y genera atómicamente sus 8 o 16 puertos físicos.

    Utiliza una única transacción de base de datos (`flush` intermedio para
    obtener `nap.id` y un único `commit` final) para garantizar que nunca exista
    una Caja NAP sin su dotación completa de puertos físicos SC/APC.

    Args:
        session: Sesión activa de base de datos SQLModel.
        nap_in: Esquema de entrada con los datos territoriales y ópticos de la NAP.

    Returns:
        NAP: Entidad persistida con sus puertos asociados cargados.

    Raises:
        NAPDuplicadaError: Si `codigo_nap` ya se encuentra registrado.
        NAPServiceError: Si ocurre un fallo de integridad durante la transacción.
    """
    codigo_normalizado = nap_in.codigo_nap.strip().upper()
    nap_existente = session.exec(
        select(NAP).where(NAP.codigo_nap == codigo_normalizado)
    ).first()

    if nap_existente is not None:
        raise NAPDuplicadaError(
            f"Ya existe una Caja NAP registrada con el código '{codigo_normalizado}'."
        )

    db_nap = NAP.model_validate(nap_in)

    try:
        session.add(db_nap)
        session.flush()

        if db_nap.id is None:
            raise NAPServiceError(
                "No se pudo resolver la clave primaria de la Caja NAP tras flush()."
            )

        puertos_generados: list[Puerto] = [
            Puerto(
                nap_id=db_nap.id,
                numero_puerto=numero,
                tipo_conector="SC/APC",
                estado_puerto=EstadoPuerto.DISPONIBLE,
            )
            for numero in range(1, db_nap.capacidad_puertos + 1)
        ]

        session.add_all(puertos_generados)
        session.commit()
        session.refresh(db_nap)
    except IntegrityError as exc:
        session.rollback()
        raise NAPDuplicadaError(
            f"Conflicto de unicidad al persistir la Caja NAP '{codigo_normalizado}' o sus puertos."
        ) from exc
    except Exception as exc:
        session.rollback()
        if isinstance(exc, NAPServiceError):
            raise
        raise NAPServiceError(
            f"Error inesperado al aprovisionar la Caja NAP '{codigo_normalizado}'."
        ) from exc

    return db_nap


# ==============================================================================
# CONSULTAS DE SOPORTE
# ==============================================================================


def obtener_nap_por_id(session: Session, nap_id: int) -> NAP:
    """Recupera una Caja NAP por su identificador primario.

    Args:
        session: Sesión activa de base de datos SQLModel.
        nap_id: Identificador entero de la Caja NAP.

    Returns:
        NAP: Instancia encontrada en base de datos.

    Raises:
        NAPNoEncontradaError: Si no existe una Caja NAP con el `nap_id` indicado.
    """
    nap = session.get(NAP, nap_id)
    if nap is None:
        raise NAPNoEncontradaError(f"No se encontró la Caja NAP con id={nap_id}.")
    return nap


def listar_puertos_por_nap(session: Session, nap_id: int) -> Sequence[Puerto]:
    """Lista los puertos físicos de una Caja NAP ordenados por número de puerto.

    Args:
        session: Sesión activa de base de datos SQLModel.
        nap_id: Identificador entero de la Caja NAP.

    Returns:
        Sequence[Puerto]: Lista ordenada ascendentemente por `numero_puerto`.

    Raises:
        NAPNoEncontradaError: Si la Caja NAP solicitada no existe.
    """
    obtener_nap_por_id(session, nap_id)
    consulta = (
        select(Puerto)
        .where(Puerto.nap_id == nap_id)
        .order_by(Puerto.numero_puerto.asc())  # type: ignore[union-attr]
    )
    return session.exec(consulta).all()
