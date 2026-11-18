"""
Suite de pruebas unitarias y de integración para el dominio NAP:
- Lógica de negocio y evaluación óptica ITU-T G.984 (`app/services/nap_service.py`).
- Futuros endpoints REST (`app/api/v1/naps.py`).
"""

from unittest.mock import patch

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.models.nap import (
    ClaseSFP,
    ColorTIA598,
    EstadoPotencia,
    EstadoPuerto,
    FuenteDato,
    LecturaPotenciaCreate,
    NAPCreate,
    SplitterRatio,
    TipoMontaje,
    ZonaOperativa,
)
from app.services.nap_service import (
    NAPDuplicadaError,
    NAPNoEncontradaError,
    NAPServiceError,
    PuertoNoEncontradoError,
    crear_nap_con_puertos,
    evaluar_salud_optica,
    listar_puertos_por_nap,
    obtener_nap_por_id,
    registrar_lectura_potencia,
)


@pytest.fixture(name="session")
def session_fixture():
    """
    Crea una base de datos SQLite limpia en memoria para cada prueba,
    garantizando aislamiento total y llaves foráneas activas.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_engine, "connect")
    def _activar_fk(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session


def _construir_nap_create_8_puertos(
    codigo_nap: str = "PLZ-Z04-NCA-D001-012-A",
) -> NAPCreate:
    """Fábrica auxiliar de una Caja NAP válida de 8 puertos (1:8)."""
    return NAPCreate(
        codigo_nap=codigo_nap,
        zona=ZonaOperativa.Z04,
        sector="NCA",
        ubicacion_referencia="Nueva Casarapa, Sector Los Cántaros, Poste 32",
        latitud=10.457890,
        longitud=-66.589410,
        tipo_montaje=TipoMontaje.AEREO,
        capacidad_puertos=8,
        splitter_ratio=SplitterRatio.RATIO_1_8,
        atenuacion_splitter_db=10.2,
        cable_distribucion="DIST-NCA-01",
        tubo_color_tia598=ColorTIA598.AZUL,
        hilo_color_tia598=ColorTIA598.NARANJA,
    )


def _construir_nap_create_16_puertos(
    codigo_nap: str = "PLZ-Z01-CEN-D002-005-F",
) -> NAPCreate:
    """Fábrica auxiliar de una Caja NAP válida de 16 puertos (1:16)."""
    return NAPCreate(
        codigo_nap=codigo_nap,
        zona=ZonaOperativa.Z01,
        sector="CEN",
        ubicacion_referencia="Calle Comercio, Edificio Plaza, Fachada Norte",
        latitud=10.467812,
        longitud=-66.613955,
        tipo_montaje=TipoMontaje.FACHADA,
        capacidad_puertos=16,
        splitter_ratio=SplitterRatio.RATIO_1_16,
        atenuacion_splitter_db=13.5,
        cable_distribucion="DIST-CEN-02",
        tubo_color_tia598=ColorTIA598.VERDE,
        hilo_color_tia598=ColorTIA598.BLANCO,
    )


# ==============================================================================
# 1. PRUEBAS DE MATRIZ ÓPTICA ITU-T G.984 (CASOS LÍMITE Y NOMINALES)
# ==============================================================================


@pytest.mark.parametrize(
    ("clase_sfp", "potencia_dbm", "estado_esperado"),
    [
        # --- Clase B+ ---
        (ClaseSFP.B_PLUS, 5.0, EstadoPotencia.CAIDO),      # Saturación alta
        (ClaseSFP.B_PLUS, -7.99, EstadoPotencia.CAIDO),    # Frontera saturación
        (ClaseSFP.B_PLUS, -8.0, EstadoPotencia.OPTIMO),    # Límite superior óptimo
        (ClaseSFP.B_PLUS, -18.5, EstadoPotencia.OPTIMO),   # Nominal óptimo
        (ClaseSFP.B_PLUS, -24.0, EstadoPotencia.OPTIMO),   # Límite inferior óptimo
        (ClaseSFP.B_PLUS, -24.01, EstadoPotencia.CRITICO), # Frontera crítico
        (ClaseSFP.B_PLUS, -26.5, EstadoPotencia.CRITICO),  # Margen degradado
        (ClaseSFP.B_PLUS, -27.0, EstadoPotencia.CRITICO),  # Límite inferior crítico
        (ClaseSFP.B_PLUS, -27.01, EstadoPotencia.CAIDO),   # Falla / pérdida señal
        (ClaseSFP.B_PLUS, -42.0, EstadoPotencia.CAIDO),    # Corte de fibra
        # --- Clase C+ ---
        (ClaseSFP.C_PLUS, -7.99, EstadoPotencia.CAIDO),    # Frontera saturación
        (ClaseSFP.C_PLUS, -8.0, EstadoPotencia.OPTIMO),    # Límite superior óptimo
        (ClaseSFP.C_PLUS, -25.0, EstadoPotencia.OPTIMO),   # Óptimo en C+ (crítico en B+)
        (ClaseSFP.C_PLUS, -26.0, EstadoPotencia.OPTIMO),   # Límite inferior óptimo C+
        (ClaseSFP.C_PLUS, -26.01, EstadoPotencia.CRITICO), # Frontera crítico C+
        (ClaseSFP.C_PLUS, -29.0, EstadoPotencia.CRITICO),  # Límite inferior crítico C+
        (ClaseSFP.C_PLUS, -29.01, EstadoPotencia.CAIDO),   # Falla / pérdida señal C+
    ],
)
def test_evaluar_salud_optica_matriz_itu_g984(
    clase_sfp: ClaseSFP,
    potencia_dbm: float,
    estado_esperado: EstadoPotencia,
) -> None:
    """Verifica todos los rangos y fronteras exactas de ITU-T G.984 para B+ y C+."""
    resultado = evaluar_salud_optica(
        potencia_rx_1490_dbm=potencia_dbm,
        clase_sfp=clase_sfp,
    )
    assert resultado == estado_esperado


@pytest.mark.parametrize("valor_invalido", [float("nan"), float("inf"), float("-inf")])
def test_evaluar_salud_optica_rechaza_valores_no_finitos(valor_invalido: float) -> None:
    """Garantiza que valores IEEE 754 no finitos lancen ValueError."""
    with pytest.raises(ValueError, match="valor finito"):
        evaluar_salud_optica(valor_invalido, ClaseSFP.B_PLUS)


# ==============================================================================
# 2. PRUEBAS DE INGESTA DE MEDICIONES DE POTENCIA
# ==============================================================================


@pytest.mark.parametrize(
    "fuente",
    [FuenteDato.MANUAL, FuenteDato.SIMULADOR, FuenteDato.SNMP_OLT],
)
def test_registrar_lectura_potencia_independiente_de_fuente(
    session: Session,
    fuente: FuenteDato,
) -> None:
    """El estado calculado debe ser idéntico sin importar el origen del dato."""
    nap = crear_nap_con_puertos(session, _construir_nap_create_8_puertos())
    puertos = listar_puertos_por_nap(session, nap.id)  # type: ignore[arg-type]
    puerto_1 = puertos[0]

    lectura_in = LecturaPotenciaCreate(
        puerto_id=puerto_1.id,  # type: ignore[arg-type]
        potencia_rx_1490_dbm=-21.4,
        potencia_tx_1310_dbm=2.1,
        clase_sfp=ClaseSFP.B_PLUS,
        fuente_dato=fuente,
    )

    lectura_db = registrar_lectura_potencia(session, lectura_in)

    assert lectura_db.id is not None
    assert lectura_db.puerto_id == puerto_1.id
    assert lectura_db.fuente_dato == fuente
    assert lectura_db.estado_calculado == EstadoPotencia.OPTIMO
    assert lectura_db.timestamp is not None


def test_registrar_lectura_en_puerto_inexistente_lanza_error(session: Session) -> None:
    """Impide registrar telemetría sobre un puerto_id que no existe en BD."""
    lectura_in = LecturaPotenciaCreate(
        puerto_id=9999,
        potencia_rx_1490_dbm=-19.0,
        clase_sfp=ClaseSFP.B_PLUS,
        fuente_dato=FuenteDato.MANUAL,
    )

    with pytest.raises(PuertoNoEncontradoError):
        registrar_lectura_potencia(session, lectura_in)


# ==============================================================================
# 3. PRUEBAS DE CREACIÓN DE NAP Y GENERACIÓN AUTOMÁTICA DE PUERTOS
# ==============================================================================


def test_crear_nap_8_puertos_genera_puertos_disponibles_en_orden(session: Session) -> None:
    """Al registrar una NAP 1:8 se deben crear exactamente 8 puertos SC/APC."""
    nap = crear_nap_con_puertos(session, _construir_nap_create_8_puertos())
    assert nap.id is not None

    puertos = listar_puertos_por_nap(session, nap.id)
    assert len(puertos) == 8
    assert [p.numero_puerto for p in puertos] == list(range(1, 9))
    assert all(p.nap_id == nap.id for p in puertos)
    assert all(p.tipo_conector == "SC/APC" for p in puertos)
    assert all(p.estado_puerto == EstadoPuerto.DISPONIBLE for p in puertos)


def test_crear_nap_16_puertos_genera_16_puertos(session: Session) -> None:
    """Al registrar una NAP 1:16 se deben crear exactamente 16 puertos."""
    nap = crear_nap_con_puertos(session, _construir_nap_create_16_puertos())
    assert nap.id is not None

    puertos = listar_puertos_por_nap(session, nap.id)
    assert len(puertos) == 16
    assert [p.numero_puerto for p in puertos] == list(range(1, 17))


def test_crear_nap_duplicada_lanza_excepcion_dominio(session: Session) -> None:
    """Rechaza códigos NAP duplicados manteniendo intactos los puertos originales."""
    payload = _construir_nap_create_8_puertos()
    nap_original = crear_nap_con_puertos(session, payload)

    with pytest.raises(NAPDuplicadaError):
        crear_nap_con_puertos(session, payload)

    puertos = listar_puertos_por_nap(session, nap_original.id)  # type: ignore[arg-type]
    assert len(puertos) == 8


def test_crear_nap_hace_rollback_si_falla_creacion_de_puertos(session: Session) -> None:
    """Verifica atomicidad: si falla la inserción de puertos no queda NAP huérfana."""
    payload = _construir_nap_create_8_puertos("PLZ-Z04-NCA-D001-099-A")

    with patch.object(session, "add_all", side_effect=RuntimeError("Fallo simulado de BD")):
        with pytest.raises(NAPServiceError):
            crear_nap_con_puertos(session, payload)

    with pytest.raises(NAPNoEncontradaError):
        obtener_nap_por_id(session, 1)


# ==============================================================================
# 4. PRUEBAS DE ENDPOINTS REST (`app/api/v1/naps.py`)
# ==============================================================================
# (Se incorporarán tras implementar los controladores HTTP de la API)
