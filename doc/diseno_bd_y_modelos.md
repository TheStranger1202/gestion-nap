# Documentación Técnica: Diseño de Base de Datos Relacional y Capa de Persistencia (FTTH-GPON)

**Proyecto:** Gestión NAP — Sistema de Inventario, Telemetría Óptica y Auditoría de Planta Externa  
**Módulo Documentado:** Capa de Persistencia (`app/core/database.py`), Modelos Relacionales (`app/models/`), Modelado ER (`doc/diagrama/`) y Pruebas TDD (`tests/test_models.py`)  
**Stack Tecnológico:** Python 3 + FastAPI + SQLModel (SQLAlchemy + Pydantic v2) + SQLite + Pytest  

---

## 1. Principio de Ingeniería: "Si no está documentado, no existe"

En ingeniería de software formal (alineada con los procesos de trazabilidad de la norma **ISO/IEC/IEEE 12207**), el código fuente expresa *cómo* funciona un sistema, pero solo la documentación técnica demuestra *por qué* fue diseñado de esa manera, bajo qué restricciones opera y cómo puede evolucionar sin romperse.

Para el proyecto **Gestión NAP**, esta documentación cumple cuatro objetivos críticos:

1. **Trazabilidad y Evidencia Académica:** Demuestra que el esquema de base de datos no es una colección improvisada de tablas, sino la traducción directa de estándares reales de telecomunicaciones (**ITU-T G.984**, **TIA/EIA-598**, **TM Forum SID**) y reglas territoriales del Municipio Plaza (Guarenas).
2. **Contrato de Integración Futura (OLT/SNMP y CRM):** Establece las llaves naturales, coordenadas jerárquicas PON y campos OID necesarios para conectar recolectores SNMP reales (Huawei/ZTE) sin tener que rediseñar ni migrar destructivamente la base de datos.
3. **Blindaje de Seguridad e Integridad:** Documenta las defensas activas contra corrupción de datos (llaves foráneas forzadas en SQLite, restricciones compuestas `UNIQUE`, validaciones cruzadas de dominio) y las responsabilidades delegadas a las capas superiores.
---

## 2. Estándares de la Industria Aplicados al Diseño

El modelo relacional se fundamenta en cuatro marcos normativos de la industria telecom y de ingeniería de software:

| Estándar / Marco | Aplicación en el Modelo Relacional | Tablas y Campos Impactados |
| :--- | :--- | :--- |
| **TM Forum SID** *(Physical Resource)* | Separa los activos físicos estáticos de la telemetría de alta frecuencia y de las actas de fiscalización operativa, evitando bloqueos de escritura y redundancia (3FN). | Separación entre `naps`/`puertos`, `lecturas_potencia` y `auditorias`. |
| **ITU-T G.984.2 / G.988** *(GPON)* | Modela las longitudes de onda estándar ($1490\text{ nm}$ downstream y $1310\text{ nm}$ upstream), las clases de transceptores ópticos (`B+` y `C+`) y la desviación respecto al presupuesto óptico. | `lecturas_potencia` (`potencia_rx_1490_dbm`, `potencia_tx_1310_dbm`, `clase_sfp`, `delta_atenuacion_db`). |
| **TIA/EIA-598 e IEC 61754-4** *(Planta Externa)* | Estandariza el código de 12 colores para identificar tubo búfer e hilo fusionado, los conectores angulares `SC/APC` y las pérdidas típicas de splitters PLC (`1:8` $\approx 10.2\text{ dB}$, `1:16` $\approx 13.5\text{ dB}$). | `naps` (`tubo_color_tia598`, `hilo_color_tia598`, `splitter_ratio`, `atenuacion_splitter_db`) y `puertos` (`tipo_conector`). |
| **RFC 2578 (SMIv2 / SNMP) y OSS/CRM** | Incorpora identificadores físicos y jerárquicos para descubrimiento automático de ONTs y sondeo MIB en equipos OLT reales. | `naps` (`olt_origen`, `puerto_pon_olt`, `snmp_oid_base`) y `puertos` (`codigo_cliente`, `serial_ont`, `snmp_oid_puerto`). |

---

## 3. Arquitectura del Modelo Relacional (5 Tablas)

El diagrama entidad-relación formal reside en `doc/diagrama/modelo_relacional_nap.puml`. A nivel lógico, la topología se organiza mediante una jerarquía estricta de integridad referencial:

```text
┌──────────────┐       1:N       ┌────────────────────┐
│    users     │────────────────►│     auditorias     │
└──────────────┘                 └─────────┬──────────┘
                                           │ N:1 (Opcional: NULL si es auditoría general)
┌──────────────┐       1:N       ┌─────────▼──────────┐
│     naps     │────────────────►│      puertos       │
└──────┬───────┘                 └─────────┬──────────┘
       │                                   │ 1:N (Historial inmutable)
       │ 1:N (Auditoría de caja)           ▼
       └────────────────────────►┌────────────────────┐
                                 │ lecturas_potencia  │
                                 └────────────────────┘
```

### Diccionario de Entidades y Decisiones de Diseño

#### 3.1. Tabla `users` (`app/models/user.py`)
* **Propósito:** Gestionar credenciales cifradas y el Control de Acceso Basado en Roles (**RBAC**: `ADMIN`, `TECNICO`, `AUDITOR`).
* **Claves e Índices:** `id` (PK), `username` (`UNIQUE`, `INDEX`), `email` (`UNIQUE`).
* **Seguridad:** Almacena únicamente `hashed_password` (cifrado con `bcrypt`), nunca contraseñas en texto plano.

#### 3.2. Tabla `naps` (`app/models/nap.py`)
* **Propósito:** Inventario georreferenciado (WGS84) de las Cajas de Acceso Terminal en el Municipio Plaza, incluyendo su trazabilidad de fibra óptica y anclaje hacia cabecera OLT.
* **Clave de Negocio:** `codigo_nap` (`UNIQUE`, `INDEX`), validado sintácticamente mediante la expresión regular:
  ```regex
  ^PLZ-Z0[1-8]-[A-Z]{3}-D\d{3}-\d{3}-[AFS]$
  ```
* **Preparación OLT/SNMP:** Los campos opcionales `olt_origen` (ej. `OLT-GUA-01`), `puerto_pon_olt` (ej. `0/1/4`) y `snmp_oid_base` vinculan la caja pasiva con el puerto activo de la OLT.

#### 3.3. Tabla `puertos` (`app/models/nap.py`)
* **Propósito:** Representar cada salida física individual (`1` a `16`) de una caja NAP hacia la acometida del suscriptor.
* **Restricción Crítica:** `UniqueConstraint("nap_id", "numero_puerto")`. Garantiza que una misma caja no pueda tener dos puertos número `1`, mientras permite que distintas cajas tengan su propio puerto `1`.
* **Preparación CRM/SNMP:** `codigo_cliente` enlaza el puerto con el contrato comercial; `serial_ont` y `snmp_oid_puerto` permiten que un recolector SNMP identifique la ONT del cliente incluso si la OLT reasigna índices dinámicos (`ONT-ID`).

#### 3.4. Tabla `lecturas_potencia` (`app/models/nap.py`)
* **Propósito:** Almacenar el historial de mediciones ópticas (*append-only*) provenientes de carga manual, simulador o sondeo SNMP (`fuente_dato`).
* **Índices de Rendimiento:** `puerto_id` (`FK -> puertos.id`, `INDEX`) y `timestamp` (`INDEX`) para recuperar rápidamente la última medición vigente de cada puerto sin escanear toda la tabla.
* **Clasificación ITU-T G.984:** Persiste `estado_calculado` (`OPTIMO`, `CRITICO`, `CAIDO`) evaluado según los umbrales de sensibilidad del módulo SFP (`B+` o `C+`).

#### 3.5. Tabla `auditorias` (`app/models/nap.py`)
* **Propósito:** Registrar actas de inspección técnica en terreno con trazabilidad de autoría (`usuario_id -> users.id`).
* **Doble Granularidad:** `nap_id` es obligatorio (`NOT NULL`), mientras que `puerto_id` es opcional (`NULLABLE`). Si la inspección evalúa la carcasa, sellado o bandeja general de la caja (`DANO_FISICO`, `MACROCURVATURA`), `puerto_id` queda en `NULL`; si evalúa una acometida puntual (`CONECTOR_SUCIO`), referencia al puerto específico.

---

## 4. Anatomía y Funcionamiento del Código Implementado

### 4.1. `app/core/database.py` (Motor SQLite y Gestión de Sesiones)
Este archivo pertenece a la capa base reutilizable (`app/core/`) y está completamente desacoplado de los modelos de dominio:

1. **Concurrencia en FastAPI (`connect_args={"check_same_thread": False}`):** Por defecto, el driver `sqlite3` de Python bloquea el uso de una conexión desde hilos distintos al que la creó. Como FastAPI atiende peticiones concurrentes en múltiples hilos, esta bandera permite compartir el motor de forma segura.
2. **Activación Forzada de Llaves Foráneas (`@event.listens_for(Engine, "connect")`):** SQLite, por compatibilidad histórica, ignora las restricciones `FOREIGN KEY` a menos que se ejecute `PRAGMA foreign_keys=ON;` en cada nueva conexión. El *listener* de SQLAlchemy automatiza este comando cada vez que se abre una conexión.
3. **Inyección de Dependencias (`get_session()`):** Función generadora (`yield Session(engine)`) que abre una transacción limpia por cada petición HTTP y garantiza el cierre automático de la sesión al finalizar, incluso si ocurre una excepción.

### 4.2. `app/models/user.py` y `app/models/nap.py` (El Patrón de 4 Clases de `SQLModel`)
`SQLModel` unifica **SQLAlchemy** (persistencia relacional) y **Pydantic v2** (validación de esquemas JSON) en una misma jerarquía de clases. Cada entidad sigue exactamente el mismo patrón:

```text
  [*Base]  ──► Define campos compartidos, tipos, rangos y validadores Pydantic.
     │
     ├──► [*] (table=True)  ──► Agrega llave primaria (id), Relaciones ORM y crea la tabla SQLite.
     ├──► [*Create]         ──► Esquema de entrada para POST (ej. UserCreate recibe password plano).
     └──► [*Read]           ──► Esquema de salida para GET (ej. UserRead oculta hashed_password).
  [*Update]                 ──► Esquema independiente con todos los campos opcionales (PATCH/PUT).
```

* **Enumeraciones estrictas (`str, Enum`):** Impiden valores arbitrarios en campos críticos (`ZonaOperativa`, `TipoMontaje`, `ColorTIA598`, `EstadoPuerto`, `ClaseSFP`, `EstadoPotencia`, `DiagnosticoAuditoria`) y generan automáticamente listas desplegables en la documentación Swagger (`/docs`).
* **Validadores de Dominio (`@field_validator` y `@model_validator`):**
  * Verifica la sintaxis del `codigo_nap` mediante Regex.
  * Cruza `zona` contra el diccionario territorial `SECTORES_POR_ZONA` (ej. impide registrar el sector `NCA` de Nueva Casarapa dentro de la zona `Z01` del Casco Histórico).
  * Verifica que los segmentos del `codigo_nap` (`ZONA`, `SECTOR`, `MONTAJE`) coincidan con los atributos individuales del objeto.
  * Exige coherencia física entre `capacidad_puertos` (`8` o `16`) y `splitter_ratio` (`1:8` o `1:16`).

### 4.3. `app/models/__init__.py` (Resolución de Relaciones Bidireccionales)
Importa y reexporta en un único punto todas las clases de `user.py` y `nap.py`. Esto evita errores de importación circular (`User` referencia a `Auditoria` y `Auditoria` referencia a `User`) y asegura que `SQLModel.metadata.create_all(engine)` registre simultáneamente las 5 tablas.

---

## 5. Seguridad, Auditoría OWASP y Análisis de Edge Cases

### Controles de Seguridad Implementados
* **Prevención de Inyección SQL (OWASP A03):** Todas las operaciones sobre SQLite se realizan mediante el ORM parametrizado de SQLModel/SQLAlchemy, eliminando la concatenación de cadenas SQL.
* **Prevención de Exposición de Datos Sensibles (OWASP A02):** `UserRead` omite `hashed_password` para evitar fugas de hashes en respuestas JSON. Asimismo, `echo=False` en `create_engine` evita imprimir consultas con datos sensibles en los logs del servidor.
* **Inmutabilidad de Telemetría:** `LecturaPotencia` carece intencionalmente de esquema `LecturaPotenciaUpdate`; las mediciones ópticas son registros históricos auditables y no deben alterarse tras su captura.

### Edge Cases Analizados (Cubiertos y Delegados)
1. **Incoherencia Territorial Sintácticamente Válida:** Un código como `PLZ-Z01-NCA-D001-001-A` cumple la expresión regular, pero `NCA` pertenece a `Z04`. **Estado:** Bloqueado en `NAPBase` mediante `@model_validator`.
2. **Desajuste Capacidad vs. Splitter:** Intentar registrar una caja de 8 puertos con splitter `1:16`. **Estado:** Bloqueado en `NAPBase`.
3. **La Trampa de `table=True` en SQLModel:** En Pydantic v2 / SQLModel, instanciar directamente una clase con `table=True` (ej. `NAP(...)`) omite los validadores de Pydantic; la validación se ejecuta al validar contra `NAPCreate` o invocar `NAP.model_validate()`. **Mitigación:** Los endpoints y scripts (`seed.py`) siempre validarán entradas mediante `*Create` antes de persistir.
4. **Desbordamiento de Puertos por Capacidad y Auditorías Cruzadas:** SQLite valida `1 <= numero_puerto <= 16` y que `puerto_id` exista, pero no verifica si el puerto `9` pertenece a una NAP de capacidad `8` ni si `auditoria.puerto_id` pertenece realmente a `auditoria.nap_id`. **Mitigación:** Validación explícita en la capa de servicios (`app/services/nap_service.py`).

---

## 6. Guía Paso a Paso de Ejecución y Verificación (TDD)

Para reproducir o auditar todo el trabajo realizado hasta este punto desde cero:

1. **Activar el entorno virtual aislado e instalar dependencias:**
   ```bash
   cd ~/proyectos/universidad/gestion-nap
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Renderizar el diagrama Entidad-Relación (opcional para visualización PNG/SVG):**
   ```bash
   plantuml doc/diagrama/modelo_relacional_nap.puml
   ```
3. **Ejecutar la suite de pruebas unitarias TDD (`tests/test_models.py`):**
   Las pruebas levantan una base de datos SQLite efímera en memoria (`sqlite:///:memory:`) con `PRAGMA foreign_keys=ON` para validar sin alterar `gestion_nap.db`:
   ```bash
   pytest -v
   ```
4. **Verificar el historial de trazabilidad en Git (Conventional Commits):**
   ```bash
   git log --oneline
   ```

---

