"""
Script idempotente de inicialización y carga de datos piloto en gestion_nap.db.
Uso: python3 seed_db.py
"""

from sqlmodel import Session, select

import app.models.user  # noqa: F401  # Registra tabla 'users' en SQLModel.metadata
from app.core.database import create_db_and_tables, engine
from app.models.nap import (
    ClaseSFP,
    ColorTIA598,
    EstadoFisicoNAP,
    EstadoPuerto,
    FuenteDato,
    LecturaPotenciaCreate,
    NAP,
    NAPCreate,
    Puerto,
    SplitterRatio,
    TipoMontaje,
    ZonaOperativa,
)
from app.services.nap_service import (
    crear_nap_con_puertos,
    registrar_lectura_potencia,
)

NAPS_PILOTO: list[dict] = [
    {
        "nap": NAPCreate(
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
            olt_origen="OLT-PLAZA-01",
            puerto_pon_olt="0/1/1",
            estado_fisico=EstadoFisicoNAP.OPERATIVO,
        ),
        "puertos_config": [
            (1, EstadoPuerto.CONECTADO, "CUS-88392", -19.40),
            (2, EstadoPuerto.CONECTADO, "CUS-11209", -21.80),
            (3, EstadoPuerto.RESERVADO, "CUS-11900", None),
        ],
    },
    {
        "nap": NAPCreate(
            codigo_nap="PLZ-Z01-CEN-D001-001-A",
            zona=ZonaOperativa.Z01,
            sector="CEN",
            ubicacion_referencia="Calle Comercio c/c Calle Real, Casco Histórico, Poste 12",
            latitud=10.467812,
            longitud=-66.613955,
            tipo_montaje=TipoMontaje.AEREO,
            capacidad_puertos=16,
            splitter_ratio=SplitterRatio.RATIO_1_16,
            atenuacion_splitter_db=13.5,
            cable_distribucion="DIST-CEN-01",
            tubo_color_tia598=ColorTIA598.AZUL,
            hilo_color_tia598=ColorTIA598.VERDE,
            olt_origen="OLT-PLAZA-01",
            puerto_pon_olt="0/1/2",
            estado_fisico=EstadoFisicoNAP.OPERATIVO,
        ),
        "puertos_config": [
            (1, EstadoPuerto.CONECTADO, "CUS-44102", -18.90),
            (2, EstadoPuerto.ATENUACION_ALTA, "CUS-55910", -28.50),
            (3, EstadoPuerto.ATENUACION_ALTA, "CUS-60124", -25.80),
            (4, EstadoPuerto.CONECTADO, "CUS-71903", -20.10),
        ],
    },
    {
        "nap": NAPCreate(
            codigo_nap="PLZ-Z02-CLA-D002-004-F",
            zona=ZonaOperativa.Z02,
            sector="CLA",
            ubicacion_referencia="Av. Principal Las Clavellinas, Edif. Mirador, Fachada",
            latitud=10.474210,
            longitud=-66.605420,
            tipo_montaje=TipoMontaje.FACHADA,
            capacidad_puertos=8,
            splitter_ratio=SplitterRatio.RATIO_1_8,
            atenuacion_splitter_db=10.2,
            cable_distribucion="DIST-CLA-02",
            tubo_color_tia598=ColorTIA598.NARANJA,
            hilo_color_tia598=ColorTIA598.AZUL,
            olt_origen="OLT-PLAZA-01",
            puerto_pon_olt="0/2/1",
            estado_fisico=EstadoFisicoNAP.OPERATIVO,
        ),
        "puertos_config": [
            (1, EstadoPuerto.CONECTADO, "CUS-30112", -17.50),
            (2, EstadoPuerto.CONECTADO, "CUS-30115", -19.20),
        ],
    },
    {
        "nap": NAPCreate(
            codigo_nap="PLZ-Z03-TRA-D003-007-A",
            zona=ZonaOperativa.Z03,
            sector="TRA",
            ubicacion_referencia="Urb. Trapichito, Manzana 4, Poste 07",
            latitud=10.456120,
            longitud=-66.603840,
            tipo_montaje=TipoMontaje.AEREO,
            capacidad_puertos=16,
            splitter_ratio=SplitterRatio.RATIO_1_16,
            atenuacion_splitter_db=13.5,
            cable_distribucion="DIST-TRA-03",
            tubo_color_tia598=ColorTIA598.VERDE,
            hilo_color_tia598=ColorTIA598.MARRON,
            olt_origen="OLT-PLAZA-02",
            puerto_pon_olt="0/1/0",
            estado_fisico=EstadoFisicoNAP.MANTENIMIENTO,
        ),
        "puertos_config": [
            (1, EstadoPuerto.CONECTADO, "CUS-91001", -22.10),
            (2, EstadoPuerto.DANADO, None, None),
        ],
    },
    {
        "nap": NAPCreate(
            codigo_nap="PLZ-Z06-MEN-D004-010-S",
            zona=ZonaOperativa.Z06,
            sector="MEN",
            ubicacion_referencia="Av. Intercomunal, Sector Menca de Leoni, Tanquilla 10",
            latitud=10.464980,
            longitud=-66.596150,
            tipo_montaje=TipoMontaje.SUBTERRANEO,
            capacidad_puertos=8,
            splitter_ratio=SplitterRatio.RATIO_1_8,
            atenuacion_splitter_db=10.2,
            cable_distribucion="DIST-MEN-04",
            tubo_color_tia598=ColorTIA598.GRIS,
            hilo_color_tia598=ColorTIA598.BLANCO,
            olt_origen="OLT-PLAZA-02",
            puerto_pon_olt="0/1/3",
            estado_fisico=EstadoFisicoNAP.OPERATIVO,
        ),
        "puertos_config": [
            (1, EstadoPuerto.CONECTADO, "CUS-77410", -16.80),
            (2, EstadoPuerto.CONECTADO, "CUS-77411", -20.45),
            (3, EstadoPuerto.CONECTADO, "CUS-77412", -23.10),
        ],
    },
]


def seed() -> None:
    create_db_and_tables()
    creadas = 0
    omitidas = 0

    with Session(engine) as session:
        for item in NAPS_PILOTO:
            nap_in: NAPCreate = item["nap"]
            existente = session.exec(
                select(NAP).where(NAP.codigo_nap == nap_in.codigo_nap)
            ).first()

            if existente is not None:
                omitidas += 1
                continue

            nap_db = crear_nap_con_puertos(session, nap_in)
            assert nap_db.id is not None

            for num_puerto, estado_puerto, cod_cliente, rx_dbm in item["puertos_config"]:
                puerto = session.exec(
                    select(Puerto).where(
                        Puerto.nap_id == nap_db.id,
                        Puerto.numero_puerto == num_puerto,
                    )
                ).first()
                if puerto is None or puerto.id is None:
                    continue

                puerto.estado_puerto = estado_puerto
                puerto.codigo_cliente = cod_cliente
                session.add(puerto)
                session.commit()

                if rx_dbm is not None:
                    registrar_lectura_potencia(
                        session,
                        LecturaPotenciaCreate(
                            puerto_id=puerto.id,
                            potencia_rx_1490_dbm=rx_dbm,
                            potencia_tx_1310_dbm=2.1,
                            clase_sfp=ClaseSFP.B_PLUS,
                            fuente_dato=FuenteDato.MANUAL,
                        ),
                    )

            creadas += 1

        total_naps = len(session.exec(select(NAP)).all())
        total_puertos = len(session.exec(select(Puerto)).all())

    print(
        f"Seed completado -> NAPs creadas: {creadas}, omitidas: {omitidas} | "
        f"Total en BD: {total_naps} NAPs, {total_puertos} puertos."
    )


if __name__ == "__main__":
    seed()
