# 🌐 Documentación de API REST: Gestión de Cajas NAP y Telemetría

**Módulo:** Controladores de API (`app/api/v1/naps.py`) y Capa de Servicios (`app/services/nap_service.py`)
**Arquitectura:** FastAPI + SQLModel (DTOs) + Arquitectura Desacoplada.

## 1. Descripción General
Esta capa del backend expone los endpoints HTTP necesarios para que cualquier cliente (visor web Leaflet.js, aplicación móvil o emulador CLI) pueda consultar el inventario físico de la red GPON y reportar los niveles de potencia óptica, abstrayendo por completo la lógica de base de datos.

## 2. Esquemas de Datos (DTOs con SQLModel)

Para cumplir con la *Estrategia de Blindaje Tecnológico*, se utiliza **SQLModel** en lugar de Pydantic puro, estandarizando los contratos de entrada:

### `CajaNAPCreate`
Esquema utilizado para dar de alta una nueva caja terminal en la base de datos.
*   **id_nap** (str): Código normalizado (Ej. `PLZ-Z04-NCA-D001-012-A`).
*   **sector** (str): Acrónimo del sector territorial (Ej. `NCA`).
*   **latitud** (float): Coordenada decimal WGS84.
*   **longitud** (float): Coordenada decimal WGS84.
*   **capacidad_puertos** (int): Cantidad de salidas (Ej. `8` o `16`).

### `LecturaTelemetria`
Esquema utilizado por el emulador o dispositivos de medición (OPMs) para reportar atenuación.
*   **puerto_id** (int): ID del puerto evaluado.
*   **potencia_rx_1490_dbm** (float): Nivel de luz recibido (Downstream).
*   **potencia_tx_1310_dbm** (float): Nivel de luz transmitido (Upstream).
*   **fuente_dato** (str): Origen (`API`, `SIMULADOR`). Default: `API`.
*   **clase_sfp** (str): Módulo óptico evaluado. Default: `B+`.

## 3. Endpoints Disponibles (`/api/v1/naps`)

| Método | Ruta | Descripción | Payload Esperado | Respuesta HTTP |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/` | Registra una nueva Caja NAP en el sistema. | `CajaNAPCreate` | `201 Created` |
| **GET** | `/` | Retorna el catálogo de NAPs activas (usado por el mapa Leaflet). | *Ninguno* | `200 OK` (Array de objetos) |
| **POST** | `/lecturas` | Ingesta de potencia óptica y evaluación de estado. | `LecturaTelemetria` | `201 Created` (Con diagnóstico) |

## 4. Lógica de Negocio Desacoplada (Servicio de Ingesta)

El endpoint `POST /lecturas` no realiza cálculos matemáticos ni consultas SQL. Delega la responsabilidad de evaluación al módulo `app/services/nap_service.py` llamando a la función `evaluar_estado_senal()`.

Esta función aplica estrictamente la matriz de umbrales **ITU-T G.984**:
*   `> -8.0 dBm`: **CAIDO** (Por saturación).
*   `-8.0 dBm` a `-24.0 dBm`: **OPTIMO** (Operación nominal).
*   `-24.1 dBm` a `-27.0 dBm`: **CRITICO** (Degradación).
*   `< -27.0 dBm`: **CAIDO** (Pérdida de enlace o corte).

## 5. Pruebas y Validación
Toda la API cuenta con especificación OpenAPI. Para probar los endpoints de forma visual sin necesidad de clientes externos como Postman:
1. Levantar el servidor: `uvicorn app.main:app --reload`
2. Navegar a: `http://127.0.0.1:8000/docs`