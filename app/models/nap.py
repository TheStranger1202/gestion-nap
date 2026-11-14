"""
Modelos relacionales y esquemas SQLModel para la topología FTTH-GPON:
Cajas NAP, Puertos de distribución, Lecturas de potencia óptica y Auditorías.
"""

import re
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from pydantic import field_validator, model_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.user import User


# Expresión regular oficial para nomenclatura de Cajas NAP en el Municipio Plaza
REGEX_CODIGO_NAP: str = r"^PLZ-Z0[1-8]-[A-Z]{3}-D\d{3}-\d{3}-[AFS]$"

# Catálogo oficial de sectores permitidos por Zona Operativa de Distribución (ZOD)
SECTORES_POR_ZONA: dict[str, set[str]] = {
    "Z01": {"CEN", "PAR", "LLA", "COM"},  # Casco Histórico y Centro
    "Z02": {"CLA", "CUR", "TAM", "GUA"},  # Eje Norte (Clavellinas - Curupao)
    "Z03": {"TRA", "RUI", "ORO"},         # Eje Trapichito - Ruiz Pineda
    "Z04": {"NCA", "GRI", "NAR"},         # Gran Casarapa - La Guairita
    "Z05": {"CCA", "TDE", "SPC"},         # Ciudad Casarapa - Terrazas
    "Z06": {"MEN", "VES", "TOR"},         # Eje 27 de Febrero - Sojo
    "Z07": {"ZIG", "ZIC", "ZSC"},         # Polígono Industrial Guarenas
    "Z08": {"VVE", "GIR", "BVT"},         # Corredor Intercomunal
}


class ZonaOperativa(str, Enum):
    """Zonas Operativas de Distribución (ZOD) del Municipio Plaza."""

    Z01 = "Z01"
    Z02 = "Z02"
    Z03 = "Z03"
    Z04 = "Z04"
    Z05 = "Z05"
    Z06 = "Z06"
    Z07 = "Z07"
    Z08 = "Z08"


class TipoMontaje(str, Enum):
    """Tipo de instalación física de la caja terminal NAP."""

    AEREO = "A"       # Poste
    FACHADA = "F"     # Pared / Edificación
    SUBTERRANEO = "S" # Cámara / Tanquilla


class SplitterRatio(str, Enum):
    """Relación de división óptica del splitter pasivo PLC."""

    RATIO_1_8 = "1:8"
    RATIO_1_16 = "1:16"


class EstadoFisicoNAP(str, Enum):
    """Condición física estructural de la caja NAP en planta externa."""

    OPERATIVO = "OPERATIVO"
    DETERIORADO = "DETERIORADO"
    VANDALIZADO = "VANDALIZADO"
    MANTENIMIENTO = "MANTENIMIENTO"


class ColorTIA598(str, Enum):
    """Código estándar de 12 colores de fibra óptica (TIA/EIA-598)."""

    AZUL = "Azul"
    NARANJA = "Naranja"
    VERDE = "Verde"
    MARRON = "Marrón"
    GRIS = "Gris"
    BLANCO = "Blanco"
    ROJO = "Rojo"
    NEGRO = "Negro"
    AMARILLO = "Amarillo"
    VIOLETA = "Violeta"
    ROSA = "Rosa"
    AQUA = "Aqua"


class EstadoPuerto(str, Enum):
    """Estado operativo de cada salida física SC/APC de la caja NAP."""

    DISPONIBLE = "DISPONIBLE"
    CONECTADO = "CONECTADO"
    RESERVADO = "RESERVADO"
    DANADO = "DANADO"
    ATENUACION_ALTA = "ATENUACION_ALTA"


class ClaseSFP(str, Enum):
    """Clase de módulo transceptor óptico GPON en la OLT (ITU-T G.984.2)."""

    B_PLUS = "B+"
    C_PLUS = "C+"


class EstadoPotencia(str, Enum):
    """Clasificación de salud óptica calculada según umbrales ITU-T G.984."""

    OPTIMO = "OPTIMO"
    CRITICO = "CRITICO"
    CAIDO = "CAIDO"


class FuenteDato(str, Enum):
    """Origen de la medición óptica registrada."""

    MANUAL = "MANUAL"
    SIMULADOR = "SIMULADOR"
    SNMP_OLT = "SNMP_OLT"


class DiagnosticoAuditoria(str, Enum):
    """Dictamen técnico levantado durante inspecciones en terreno."""

    OPTIMO = "OPTIMO"
    FUERA_DE_RANGO = "FUERA_DE_RANGO"
    CONECTOR_SUCIO = "CONECTOR_SUCIO"
    MACROCURVATURA = "MACROCURVATURA"
    DANO_FISICO = "DANO_FISICO"


# ==============================================================================
# 1. ENTIDAD: NAPS (Cajas de Acceso Terminal)
# ==============================================================================


class NAPBase(SQLModel):
    """Atributos base y reglas de validación territorial/óptica de una Caja NAP."""

    codigo_nap: str = Field(
        max_length=25,
        unique=True,
        index=True,
        description="Código normalizado (ej. PLZ-Z04-NCA-D001-012-A).",
    )
    zona: ZonaOperativa = Field(
        description="Código de Zona Operativa de Distribución (Z01 a Z08).",
    )
    sector: str = Field(
        min_length=3,
        max_length=3,
        description="Acrónimo de 3 letras del sector según catálogo territorial.",
    )
    ubicacion_referencia: str = Field(
        min_length=5,
        max_length=255,
        description="Dirección física, urbanismo o poste de referencia.",
    )
    latitud: float = Field(
        ge=-90.0,
        le=90.0,
        description="Latitud geográfica en formato decimal WGS84.",
    )
    longitud: float = Field(
        ge=-180.0,
        le=180.0,
        description="Longitud geográfica en formato decimal WGS84.",
    )
    tipo_montaje: TipoMontaje = Field(
        description="Tipo de montaje: A (Aéreo), F (Fachada) o S (Subterráneo).",
    )
    capacidad_puertos: int = Field(
        default=8,
        description="Cantidad total de puertos de salida de la NAP (8 o 16).",
    )
    splitter_ratio: SplitterRatio = Field(
        default=SplitterRatio.RATIO_1_8,
        description="Relación del splitter óptico interno (1:8 o 1:16).",
    )
    atenuacion_splitter_db: float = Field(
        default=10.2,
        gt=0.0,
        le=20.0,
        description="Atenuación nominal de inserción del splitter en dB.",
    )
    cable_distribucion: str = Field(
        min_length=3,
        max_length=50,
        description="Identificador del cable alimentador de distribución (ej. DIST-NCA-01).",
    )
    tubo_color_tia598: ColorTIA598 = Field(
        description="Color del tubo búfer según estándar TIA/EIA-598.",
    )
    hilo_color_tia598: ColorTIA598 = Field(
        description="Color del hilo de fibra fusionado según estándar TIA/EIA-598.",
    )
    olt_origen: str | None = Field(
        default=None,
        max_length=50,
        description="Identificador de cabecera OLT para integración futura.",
    )
    puerto_pon_olt: str | None = Field(
        default=None,
        max_length=20,
        description="Tarjeta y puerto PON de origen en la OLT (ej. 0/1/4).",
    )
    snmp_oid_base: str | None = Field(
        default=None,
        max_length=120,
        description="Rama OID SNMP del puerto PON en la OLT.",
    )
    estado_fisico: EstadoFisicoNAP = Field(
        default=EstadoFisicoNAP.OPERATIVO,
        description="Estado físico general de la caja en planta externa.",
    )

    @field_validator("codigo_nap")
    @classmethod
    def validar_formato_codigo_nap(cls, valor: str) -> str:
        """Verifica que el código NAP cumpla la expresión regular oficial."""
        codigo = valor.strip().upper()
        if not re.match(REGEX_CODIGO_NAP, codigo):
            raise ValueError(
                f"El código NAP '{codigo}' no cumple el estándar "
                "PLZ-Z0[1-8]-[SECTOR]-D000-000-[A|F|S]."
            )
        return codigo

    @field_validator("sector")
    @classmethod
    def normalizar_sector(cls, valor: str) -> str:
        """Normaliza el código de sector a 3 letras mayúsculas."""
        sector = valor.strip().upper()
        if not re.match(r"^[A-Z]{3}$", sector):
            raise ValueError("El sector debe estar compuesto exactamente por 3 letras.")
        return sector

    @field_validator("capacidad_puertos")
    @classmethod
    def validar_capacidad_puertos(cls, valor: int) -> int:
        """Restringe la capacidad física de la NAP a 8 o 16 puertos."""
        if valor not in (8, 16):
            raise ValueError("La capacidad de puertos de una caja NAP debe ser 8 o 16.")
        return valor

    @model_validator(mode="after")
    def validar_coherencia_territorial_y_optica(self) -> "NAPBase":
        """Valida consistencia entre código NAP, catálogo ZOD y splitter PLC."""
        sectores_validos = SECTORES_POR_ZONA.get(self.zona.value, set())
        if self.sector not in sectores_validos:
            raise ValueError(
                f"El sector '{self.sector}' no pertenece a la zona '{self.zona.value}'. "
                f"Sectores permitidos: {sorted(sectores_validos)}."
            )

        # Descomponer PLZ-[ZONA]-[SECTOR]-[DIST]-[CONS]-[MONTAJE]
        _, cod_zona, cod_sector, _, _, cod_montaje = self.codigo_nap.split("-")
        if cod_zona != self.zona.value:
            raise ValueError(
                f"Inconsistencia territorial: codigo_nap indica zona '{cod_zona}', "
                f"pero el campo zona es '{self.zona.value}'."
            )
        if cod_sector != self.sector:
            raise ValueError(
                f"Inconsistencia territorial: codigo_nap indica sector '{cod_sector}', "
                f"pero el campo sector es '{self.sector}'."
            )
        if cod_montaje != self.tipo_montaje.value:
            raise ValueError(
                f"Inconsistencia física: codigo_nap indica montaje '{cod_montaje}', "
                f"pero tipo_montaje es '{self.tipo_montaje.value}'."
            )

        # Verificar correspondencia capacidad <-> ratio de splitter
        esperado = SplitterRatio.RATIO_1_8 if self.capacidad_puertos == 8 else SplitterRatio.RATIO_1_16
        if self.splitter_ratio != esperado:
            raise ValueError(
                f"Una NAP de {self.capacidad_puertos} puertos requiere splitter '{esperado.value}', "
                f"no '{self.splitter_ratio.value}'."
            )

        return self


class NAP(NAPBase, table=True):
    """Tabla relacional `naps` en SQLite."""

    __tablename__ = "naps"

    id: int | None = Field(default=None, primary_key=True)
    creado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Marca de tiempo UTC de alta en inventario.",
    )

    puertos: list["Puerto"] = Relationship(
        back_populates="nap",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    auditorias: list["Auditoria"] = Relationship(back_populates="nap")


class NAPCreate(NAPBase):
    """Esquema de entrada para registrar una nueva Caja NAP."""


class NAPRead(NAPBase):
    """Esquema de salida con los datos completos de una Caja NAP."""

    id: int
    creado_en: datetime


class NAPUpdate(SQLModel):
    """Esquema de entrada para actualización parcial de una Caja NAP."""

    ubicacion_referencia: str | None = Field(default=None, min_length=5, max_length=255)
    latitud: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitud: float | None = Field(default=None, ge=-180.0, le=180.0)
    cable_distribucion: str | None = Field(default=None, min_length=3, max_length=50)
    tubo_color_tia598: ColorTIA598 | None = None
    hilo_color_tia598: ColorTIA598 | None = None
    olt_origen: str | None = Field(default=None, max_length=50)
    puerto_pon_olt: str | None = Field(default=None, max_length=20)
    snmp_oid_base: str | None = Field(default=None, max_length=120)
    estado_fisico: EstadoFisicoNAP | None = None


# ==============================================================================
# 2. ENTIDAD: PUERTOS (Salidas Ópticas de la NAP)
# ==============================================================================


class PuertoBase(SQLModel):
    """Atributos base de un puerto óptico de salida en una Caja NAP."""

    nap_id: int = Field(
        foreign_key="naps.id",
        index=True,
        description="Identificador de la Caja NAP propietaria.",
    )
    numero_puerto: int = Field(
        ge=1,
        le=16,
        description="Número físico del puerto dentro de la caja (1 a 16).",
    )
    tipo_conector: str = Field(
        default="SC/APC",
        max_length=15,
        description="Estándar de conector óptico (por defecto SC/APC).",
    )
    estado_puerto: EstadoPuerto = Field(
        default=EstadoPuerto.DISPONIBLE,
        description="Estado de asignación u operatividad del puerto.",
    )
    codigo_cliente: str | None = Field(
        default=None,
        max_length=50,
        description="Código de contrato o suscriptor en sistema CRM/Inventario.",
    )
    serial_ont: str | None = Field(
        default=None,
        max_length=32,
        description="Número de serie físico de la ONT del suscriptor.",
    )
    snmp_oid_puerto: str | None = Field(
        default=None,
        max_length=150,
        description="OID SNMP específico del puerto/ONT para monitoreo automático.",
    )


class Puerto(PuertoBase, table=True):
    """Tabla relacional `puertos` con restricción de unicidad por caja NAP."""

    __tablename__ = "puertos"
    __table_args__ = (
        UniqueConstraint("nap_id", "numero_puerto", name="uq_puertos_nap_numero"),
    )

    id: int | None = Field(default=None, primary_key=True)
    actualizado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Última modificación de estado o asignación del puerto.",
    )

    nap: Optional["NAP"] = Relationship(back_populates="puertos")
    lecturas: list["LecturaPotencia"] = Relationship(
        back_populates="puerto",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    auditorias: list["Auditoria"] = Relationship(back_populates="puerto")


class PuertoCreate(PuertoBase):
    """Esquema de entrada para crear un puerto óptico."""


class PuertoRead(PuertoBase):
    """Esquema de salida con los datos del puerto óptico."""

    id: int
    actualizado_en: datetime


class PuertoUpdate(SQLModel):
    """Esquema de entrada para actualizar asignación o estado de un puerto."""

    tipo_conector: str | None = Field(default=None, max_length=15)
    estado_puerto: EstadoPuerto | None = None
    codigo_cliente: str | None = Field(default=None, max_length=50)
    serial_ont: str | None = Field(default=None, max_length=32)
    snmp_oid_puerto: str | None = Field(default=None, max_length=150)


# ==============================================================================
# 3. ENTIDAD: LECTURAS_POTENCIA (Telemetría Óptica ITU-T G.984)
# ==============================================================================


class LecturaPotenciaBase(SQLModel):
    """Atributos base de una medición de potencia óptica en un puerto GPON."""

    puerto_id: int = Field(
        foreign_key="puertos.id",
        index=True,
        description="Puerto óptico donde se realiza la medición.",
    )
    potencia_rx_1490_dbm: float = Field(
        ge=-50.0,
        le=10.0,
        description="Potencia óptica recibida downstream a 1490 nm (en dBm).",
    )
    potencia_tx_1310_dbm: float | None = Field(
        default=None,
        ge=-10.0,
        le=15.0,
        description="Potencia óptica transmitida upstream a 1310 nm (en dBm).",
    )
    clase_sfp: ClaseSFP = Field(
        default=ClaseSFP.B_PLUS,
        description="Clase del módulo SFP de la OLT (B+ o C+).",
    )
    fuente_dato: FuenteDato = Field(
        default=FuenteDato.MANUAL,
        description="Origen de la lectura: MANUAL, SIMULADOR o SNMP_OLT.",
    )


class LecturaPotencia(LecturaPotenciaBase, table=True):
    """Tabla relacional `lecturas_potencia` para historial de telemetría óptica."""

    __tablename__ = "lecturas_potencia"

    id: int | None = Field(default=None, primary_key=True)
    delta_atenuacion_db: float | None = Field(
        default=None,
        description="Desviación en dB respecto al presupuesto óptico teórico.",
    )
    estado_calculado: EstadoPotencia = Field(
        description="Estado normalizado ITU-T G.984: OPTIMO, CRITICO o CAIDO.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
        description="Marca de tiempo UTC de captura de la lectura.",
    )

    puerto: Optional["Puerto"] = Relationship(back_populates="lecturas")


class LecturaPotenciaCreate(LecturaPotenciaBase):
    """Esquema de entrada para ingestar una lectura óptica (el estado se calcula en servicio)."""


class LecturaPotenciaRead(LecturaPotenciaBase):
    """Esquema de salida con el diagnóstico óptico calculado."""

    id: int
    delta_atenuacion_db: float | None
    estado_calculado: EstadoPotencia
    timestamp: datetime


# ==============================================================================
# 4. ENTIDAD: AUDITORIAS (Inspecciones Técnicas en Campo)
# ==============================================================================


class AuditoriaBase(SQLModel):
    """Atributos base de un acta de inspección o fiscalización técnica."""

    nap_id: int = Field(
        foreign_key="naps.id",
        index=True,
        description="Caja NAP inspeccionada.",
    )
    puerto_id: int | None = Field(
        default=None,
        foreign_key="puertos.id",
        description="Puerto específico auditado (opcional si la auditoría es general a la caja).",
    )
    diagnostico: DiagnosticoAuditoria = Field(
        description="Dictamen técnico estandarizado de la inspección.",
    )
    observaciones: str = Field(
        min_length=5,
        max_length=1000,
        description="Detalle técnico de hallazgos, empalmes o acciones correctivas.",
    )
    evidencia_url: str | None = Field(
        default=None,
        max_length=255,
        description="Ruta relativa o URL de respaldo fotográfico.",
    )


class Auditoria(AuditoriaBase, table=True):
    """Tabla relacional `auditorias` en SQLite."""

    __tablename__ = "auditorias"

    id: int | None = Field(default=None, primary_key=True)
    usuario_id: int = Field(
        foreign_key="users.id",
        description="Usuario auditor o técnico que ejecuta la inspección.",
    )
    fecha_auditoria: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Fecha y hora UTC de registro de la auditoría.",
    )

    nap: Optional["NAP"] = Relationship(back_populates="auditorias")
    puerto: Optional["Puerto"] = Relationship(back_populates="auditorias")
    usuario: Optional["User"] = Relationship(back_populates="auditorias")


class AuditoriaCreate(AuditoriaBase):
    """Esquema de entrada para registrar una auditoría (usuario_id proviene del token JWT)."""


class AuditoriaRead(AuditoriaBase):
    """Esquema de salida con los datos completos de la auditoría."""

    id: int
    usuario_id: int
    fecha_auditoria: datetime


class AuditoriaUpdate(SQLModel):
    """Esquema de entrada para complementar observaciones o evidencia de una auditoría."""

    diagnostico: DiagnosticoAuditoria | None = None
    observaciones: str | None = Field(default=None, min_length=5, max_length=1000)
    evidencia_url: str | None = Field(default=None, max_length=255)
