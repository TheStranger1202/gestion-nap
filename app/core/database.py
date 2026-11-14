"""
Configuración del motor de base de datos SQLite y gestión de sesiones SQLModel.

Este módulo pertenece a la capa base reutilizable (`app/core/`) y permanece
desacoplado de los modelos específicos del dominio para facilitar su portabilidad.
"""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./gestion_nap.db")

# check_same_thread=False es obligatorio en SQLite para peticiones concurrentes en FastAPI
connect_args: dict[str, bool] = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine: Engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)


@event.listens_for(Engine, "connect")
def activar_llaves_foraneas_sqlite(dbapi_connection, connection_record) -> None:
    """Habilita la integridad referencial (PRAGMA foreign_keys=ON) en cada conexión SQLite."""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


def create_db_and_tables() -> None:
    """Crea en la base de datos todas las tablas registradas en SQLModel.metadata."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Generador de sesiones SQLModel para inyección de dependencias en FastAPI."""
    with Session(engine) as session:
        yield session
