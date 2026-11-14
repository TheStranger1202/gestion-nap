"""
Suite de pruebas unitarias y de integridad relacional (TDD) para la capa de
persistencia (`app/core/database.py`) y los modelos (`app/models/`).
"""

import pytest
from pydantic import ValidationError
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from app.models import (
    Auditoria,
    ClaseSFP,
    ColorTIA598,
    DiagnosticoAuditoria,
    EstadoPuerto,
    FuenteDato,
    LecturaPotenciaCreate,
    NAP,
    NAPCreate,
    Puerto,
    RolUsuario,
    SplitterRatio,
    TipoMontaje,
    User,
    UserCreate,
    UserRead,
    ZonaOperativa,
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


# ==============================================================================
# 1. PRUEBAS DE VALIDACIÓN TERRITORIAL Y ÓPTICA (PYDANTIC / REGEX)
# ==============================================================================


def test_creacion_nap_valida_punto_piloto() -> None:
    """Verifica que un punto piloto oficial del Municipio Plaza pase todas las reglas."""
    nap_in = NAPCreate(
        codigo_nap="PLZ-Z04-NCA-D001-012-A",
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
    assert nap_in.codigo_nap == "PLZ-Z04-NCA-D001-012-A"
    assert nap_in.zona == ZonaOperativa.Z04


@pytest.mark.parametrize(
    "codigo_invalido",
    [
        "PLZ-Z09-NCA-D001-012-A",  # Zona Z09 fuera de rango (Z01-Z08)
        "GUA-Z04-NCA-D001-012-A",  # Prefijo municipal incorrecto (debe ser PLZ)
        "PLZ-Z04-NCA-001-012-A",   # Falta letra 'D' en distribuidor
        "PLZ-Z04-NCA-D001-012-X",  # Tipo de montaje 'X' no permitido (solo A, F, S)
    ],
)
def test_rechazo_codigo_nap_regex_invalido(codigo_invalido: str) -> None:
    """Verifica que códigos NAP mal formados sean rechazados por la expresión regular."""
    with pytest.raises(ValidationError):
        NAPCreate(
            codigo_nap=codigo_invalido,
            zona=ZonaOperativa.Z04,
            sector="NCA",
            ubicacion_referencia="Referencia de prueba válida",
            latitud=10.457890,
            longitud=-66.589410,
            tipo_montaje=TipoMontaje.AEREO,
            cable_distribucion="DIST-NCA-01",
            tubo_color_tia598=ColorTIA598.AZUL,
            hilo_color_tia598=ColorTIA598.VERDE,
        )


def test_rechazo_incoherencia_zona_y_sector() -> None:
    """Edge case: código sintácticamente válido pero sector 'NCA' no pertenece a 'Z01'."""
    with pytest.raises(ValidationError, match="no pertenece a la zona"):
        NAPCreate(
            codigo_nap="PLZ-Z01-NCA-D001-001-A",
            zona=ZonaOperativa.Z01,
            sector="NCA",
            ubicacion_referencia="Calle Comercio, Poste 12",
            latitud=10.467812,
            longitud=-66.613955,
            tipo_montaje=TipoMontaje.AEREO,
            cable_distribucion="DIST-CEN-01",
            tubo_color_tia598=ColorTIA598.AZUL,
            hilo_color_tia598=ColorTIA598.NARANJA,
        )


def test_rechazo_discrepancia_codigo_vs_montaje() -> None:
    """Edge case: codigo_nap termina en '-A' (Aéreo) pero tipo_montaje indica 'F' (Fachada)."""
    with pytest.raises(ValidationError, match="Inconsistencia física"):
        NAPCreate(
            codigo_nap="PLZ-Z01-CEN-D001-001-A",
            zona=ZonaOperativa.Z01,
            sector="CEN",
            ubicacion_referencia="Calle Comercio, Poste 12",
            latitud=10.467812,
            longitud=-66.613955,
            tipo_montaje=TipoMontaje.FACHADA,
            cable_distribucion="DIST-CEN-01",
            tubo_color_tia598=ColorTIA598.AZUL,
            hilo_color_tia598=ColorTIA598.NARANJA,
        )


def test_rechazo_capacidad_vs_splitter_inconsistente() -> None:
    """Edge case: caja de 8 puertos configurada erróneamente con splitter 1:16."""
    with pytest.raises(ValidationError, match="requiere splitter '1:8'"):
        NAPCreate(
            codigo_nap="PLZ-Z01-CEN-D001-001-A",
            zona=ZonaOperativa.Z01,
            sector="CEN",
            ubicacion_referencia="Calle Comercio, Poste 12",
            latitud=10.467812,
            longitud=-66.613955,
            tipo_montaje=TipoMontaje.AEREO,
            capacidad_puertos=8,
            splitter_ratio=SplitterRatio.RATIO_1_16,
            cable_distribucion="DIST-CEN-01",
            tubo_color_tia598=ColorTIA598.AZUL,
            hilo_color_tia598=ColorTIA598.NARANJA,
        )


# ==============================================================================
# 2. PRUEBAS DE INTEGRIDAD REFERENCIAL Y RESTRICCIONES EN SQLITE
# ==============================================================================


def test_pragma_foreign_keys_activo(session: Session) -> None:
    """Verifica que SQLite tenga habilitada la validación de llaves foráneas."""
    resultado = session.exec(text("PRAGMA foreign_keys;")).first()
    assert resultado[0] == 1


def test_integridad_referencial_bloquea_puerto_huerfano(session: Session) -> None:
    """Verifica que no se pueda insertar un puerto asociado a un nap_id inexistente."""
    puerto_huerfano = Puerto(
        nap_id=9999,
        numero_puerto=1,
        estado_puerto=EstadoPuerto.DISPONIBLE,
    )
    session.add(puerto_huerfano)
    with pytest.raises(IntegrityError):
        session.commit()


def test_unicidad_numero_puerto_dentro_de_misma_nap(session: Session) -> None:
    """Verifica que UniqueConstraint(nap_id, numero_puerto) impida duplicar el puerto 1."""
    nap_in = NAPCreate(
        codigo_nap="PLZ-Z01-CEN-D001-001-A",
        zona=ZonaOperativa.Z01,
        sector="CEN",
        ubicacion_referencia="Calle Comercio c/c Calle Real, Poste 12",
        latitud=10.467812,
        longitud=-66.613955,
        tipo_montaje=TipoMontaje.AEREO,
        cable_distribucion="DIST-CEN-01",
        tubo_color_tia598=ColorTIA598.AZUL,
        hilo_color_tia598=ColorTIA598.NARANJA,
    )
    nap_db = NAP.model_validate(nap_in)
    session.add(nap_db)
    session.commit()
    session.refresh(nap_db)

    puerto_1a = Puerto(nap_id=nap_db.id, numero_puerto=1)
    puerto_1b = Puerto(nap_id=nap_db.id, numero_puerto=1)
    session.add(puerto_1a)
    session.commit()

    session.add(puerto_1b)
    with pytest.raises(IntegrityError):
        session.commit()


def test_auditoria_general_y_puntual_en_bd(session: Session) -> None:
    """Verifica la relación 1:N de auditorías tanto a nivel de NAP como de puerto específico."""
    auditor = User(
        username="auditor_plaza",
        email="auditor@gestionnap.ve",
        hashed_password="$2b$12$hashsimuladoejemplo12345678901234567890",
        rol=RolUsuario.AUDITOR,
    )
    nap_in = NAPCreate(
        codigo_nap="PLZ-Z03-TRA-D002-005-F",
        zona=ZonaOperativa.Z03,
        sector="TRA",
        ubicacion_referencia="Urb. Trapichito, Bloque 7",
        latitud=10.463201,
        longitud=-66.609450,
        tipo_montaje=TipoMontaje.FACHADA,
        cable_distribucion="DIST-TRA-02",
        tubo_color_tia598=ColorTIA598.VERDE,
        hilo_color_tia598=ColorTIA598.MARRON,
    )
    nap_db = NAP.model_validate(nap_in)
    session.add(auditor)
    session.add(nap_db)
    session.commit()
    session.refresh(auditor)
    session.refresh(nap_db)

    puerto = Puerto(nap_id=nap_db.id, numero_puerto=3, estado_puerto=EstadoPuerto.CONECTADO)
    session.add(puerto)
    session.commit()
    session.refresh(puerto)

    # Auditoría general (puerto_id=None) y auditoría puntual (puerto_id=puerto.id)
    aud_general = Auditoria(
        nap_id=nap_db.id,
        puerto_id=None,
        usuario_id=auditor.id,
        diagnostico=DiagnosticoAuditoria.OPTIMO,
        observaciones="Envolvente sellada correctamente, sin humedad interna.",
    )
    aud_puerto = Auditoria(
        nap_id=nap_db.id,
        puerto_id=puerto.id,
        usuario_id=auditor.id,
        diagnostico=DiagnosticoAuditoria.CONECTOR_SUCIO,
        observaciones="Férula SC/APC contaminada, requiere limpieza con lápiz óptico.",
    )
    session.add(aud_general)
    session.add(aud_puerto)
    session.commit()

    assert aud_general.id is not None
    assert aud_puerto.id is not None


# ==============================================================================
# 3. PRUEBAS DE SEGURIDAD DE ESQUEMAS Y TELEMETRÍA
# ==============================================================================


def test_user_read_oculta_hashed_password(session: Session) -> None:
    """Seguridad (OWASP): garantiza que el esquema de salida UserRead nunca exponga el hash."""
    usuario = User(
        username="tecnico01",
        email="tecnico01@gestionnap.ve",
        hashed_password="$2b$12$secreto_bcrypt_que_no_debe_salir_en_json",
        rol=RolUsuario.TECNICO,
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)

    salida_api = UserRead.model_validate(usuario).model_dump()
    assert "hashed_password" not in salida_api
    assert salida_api["username"] == "tecnico01"


def test_lectura_potencia_fuera_de_rango_fisico() -> None:
    """Verifica que mediciones ópticas físicamente imposibles sean rechazadas."""
    with pytest.raises(ValidationError):
        LecturaPotenciaCreate(
            puerto_id=1,
            potencia_rx_1490_dbm=-65.0,  # Límite inferior físico permitido es -50.0 dBm
            clase_sfp=ClaseSFP.B_PLUS,
            fuente_dato=FuenteDato.MANUAL,
        )
