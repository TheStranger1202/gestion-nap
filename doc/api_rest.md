# 🌐 Documentación de API REST: Gestión de Cajas NAP y Telemetría

**Módulo:** Controladores de API (`app/api/v1/naps.py`, `app/api/v1/auth.py`) y Capa de Servicios (`app/services/nap_service.py`)  
**Arquitectura:** FastAPI + SQLModel (DTOs) + Autenticación JWT (HS256) + Arquitectura Desacoplada.

## 1. Descripción General
Esta capa del backend expone los endpoints HTTP necesarios para que cualquier cliente autorizado (visor web Leaflet.js, dashboard ejecutivo o emulador CLI) pueda consultar el inventario físico de la red GPON y reportar los niveles de potencia óptica, abstrayendo por completo la lógica de base de datos.

Todas las rutas de negocio están protegidas mediante **JWT (HS256)** enviado en la cabecera `Authorization: Bearer <token>` y control de acceso basado en roles (`admin` y `operador`).

## 2. Esquemas de Datos (DTOs con SQLModel)

Para cumplir con la *Estrategia de Blindaje Tecnológico*, se utiliza **SQLModel** en lugar de Pydantic puro, estandarizando los contratos de entrada con los modelos relacionales en `app/models/nap.py`:

### `NAPCreate`
Esquema utilizado para dar de alta una nueva caja terminal en la base de datos.
* **codigo_nap** (`str`): Código normalizado del Municipio Plaza (Ej. `PLZ-Z04-NCA-D001-012-A`).
* **zona** (`str`): Zona Operativa de Distribución (`Z01`–`Z08`).
* **sector** (`str`): Acrónimo del sector territorial (Ej. `NCA`).
* **latitud** (`float`): Coordenada decimal WGS84.
* **longitud** (`float`): Coordenada decimal WGS84.
* **capacidad_puertos** (`int`): Cantidad de salidas (`8` o `16`), coherente con `splitter_ratio` (`1:8` o `1:16`).

### `LecturaPotenciaCreate`
Esquema utilizado por el formulario web, el emulador CLI o dispositivos de medición (OPMs) para reportar atenuación óptica.
* **puerto_id** (`int`): ID del puerto `SC/APC` evaluado.
* **potencia_rx_1490_dbm** (`float`): Nivel de luz recibido (Downstream, $1490\text{ nm}$).
* **potencia_tx_1310_dbm** (`float`): Nivel de luz transmitido (Upstream, $1310\text{ nm}$).
* **fuente_dato** (`str`): Origen del dato (`MANUAL`, `SIMULADOR`, `SNMP_OLT`).
* **clase_sfp** (`str`): Módulo óptico evaluado (`B+` o `C+`). Default: `B+`.

## 3. Endpoints Disponibles (`/api/v1/naps`)

| Método | Ruta | Rol Requerido | Descripción | Payload Esperado | Respuesta HTTP |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **POST** | `/` | `admin` | Registra una nueva Caja NAP y aprovisiona sus puertos `SC/APC` atómicamente. | `NAPCreate` | `201 Created` |
| **GET** | `/` | `operador` / `admin` | Retorna el catálogo de NAPs activas con su estado general (usado por el mapa Leaflet). | *Ninguno* | `200 OK` |
| **POST** | `/lecturas` | `operador` / `admin` | Ingesta de potencia óptica y evaluación automática de estado. | `LecturaPotenciaCreate` | `201 Created` |

## 4. Lógica de Negocio Desacoplada y Mapeo de Estados

El endpoint `POST /lecturas` no realiza cálculos matemáticos ni consultas SQL directas. Delega la evaluación al módulo `app/services/nap_service.py` llamando a la función `evaluar_salud_optica()`.

Esta función aplica estrictamente la matriz de umbrales **ITU-T G.984.2** (para SFP Clase `B+`):
* `> -8.0 dBm`: **`CAIDO`** (Saturación óptica).
* `-8.0 dBm` a `-24.0 dBm`: **`OPTIMO`** (Operación nominal).
* `-24.1 dBm` a `-27.0 dBm`: **`CRITICO`** (Degradación / margen bajo).
* `< -27.0 dBm`: **`CAIDO`** (Pérdida de enlace o corte de fibra).

*(Para módulos SFP Clase `C+`, el rango `OPTIMO` se extiende hasta `-26.0 dBm` y `CRITICO` hasta `-29.0 dBm`).*

### Equivalencia entre Telemetría de Puerto y Estado Visual del Mapa GIS
* Puertos con lecturas **`OPTIMO`** $\rightarrow$ Caja NAP en estado **`OPTIMO`** (marcador verde).
* Puertos en degradación (**`CRITICO`**) o alta ocupación $\rightarrow$ Caja NAP en estado **`ADVERTENCIA`** (marcador ámbar).
* Puertos con pérdida de enlace o saturación (**`CAIDO`**) $\rightarrow$ Caja NAP en estado **`CRITICO`** (marcador rojo pulsante).

## 5. Pruebas y Validación
Toda la API cuenta con especificación OpenAPI interactiva:
1. Levantar el servidor: `uvicorn app.main:app --reload --port 8000`
2. Navegar a: `http://127.0.0.1:8000/docs`
3. Autenticarse mediante el botón **Authorize** usando credenciales válidas (`admin` u `operador@gestionnap.ve`).