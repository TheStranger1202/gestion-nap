"""
Modelos relacionales y esquemas Pydantic/SQLModel para autenticación y roles (RBAC).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.nap import Auditoria


class RolUsuario(str, Enum):
    """Roles permitidos para el control de acceso basado en roles (RBAC)."""

    ADMIN = "ADMIN"
    TECNICO = "TECNICO"
    AUDITOR = "AUDITOR"


class UserBase(SQLModel):
    """Atributos compartidos de usuario para persistencia y validación en API."""

    username: str = Field(
        min_length=3,
        max_length=50,
        unique=True,
        index=True,
        description="Nombre de usuario único para inicio de sesión.",
    )
    email: EmailStr = Field(
        max_length=120,
        unique=True,
        description="Correo electrónico institucional del usuario.",
    )
    rol: RolUsuario = Field(
        default=RolUsuario.TECNICO,
        description="Rol operativo asignado al usuario.",
    )
    activo: bool = Field(
        default=True,
        description="Indica si la cuenta se encuentra habilitada para operar.",
    )


class User(UserBase, table=True):
    """Tabla relacional `users` en SQLite."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str = Field(
        max_length=255,
        description="Contraseña cifrada mediante algoritmo bcrypt.",
    )
    creado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Marca de tiempo UTC de creación del registro.",
    )

    auditorias: list["Auditoria"] = Relationship(back_populates="usuario")


class UserCreate(UserBase):
    """Esquema de entrada para el registro de nuevos usuarios."""

    password: str = Field(
        min_length=8,
        max_length=128,
        description="Contraseña en texto plano (se cifra antes de guardar).",
    )


class UserRead(UserBase):
    """Esquema de salida seguro que omite la contraseña cifrada."""

    id: int
    creado_en: datetime


class UserUpdate(SQLModel):
    """Esquema de entrada para actualización parcial de usuarios."""

    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    rol: RolUsuario | None = None
    activo: bool | None = None
