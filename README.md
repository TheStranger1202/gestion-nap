# Gestión NAP | Plataforma GIS y Telemetría Óptica FTTH-GPON

Sistema web georreferenciado para el inventario, monitoreo óptico en tiempo real y auditoría técnica de **Cajas de Acceso Terminal (NAP)** en redes FTTH-GPON del **Municipio Plaza (Guarenas, Estado Miranda, Venezuela)**.

---

## Características Principales

* **Mapa Interactivo GIS (Leaflet.js + OpenStreetMap):** Visualización georreferenciada (WGS84) de cajas NAP con marcadores SVG dinámicos según estado operativo (`OPTIMO`, `ADVERTENCIA`, `CRITICO`) y alertas visuales pulsantes.
* **Motor de Diagnóstico Óptico ITU-T G.984.2:** Clasificación automática de lecturas downstream ($1490\text{ nm}$) y upstream ($1310\text{ nm}$) para módulos transceptores SFP **Clase B+** y **Clase C+**, incluyendo detección de saturación óptica ($> -8.0\text{ dBm}$).
* **Nomenclatura Territorial Normalizada:** Validación estricta del estándar municipal `PLZ-Z0[1-8]-[SECTOR]-D000-000-[A|F|S]`, coherencia entre Zonas Operativas de Distribución (`Z01`–`Z08`), tipo de montaje, relación de *splitter* (`1:8` / `1:16`) y código de colores de fibra **TIA/EIA-598**.
* **Arquitectura Endurecida:** Autenticación **JWT (HS256)**, hashing PBKDF2 en tiempo constante, control de acceso basado en roles (`admin` / `operador`), limitación de tasa (*rate limiting*), validación de cabecera `Host`, CORS estricto y sanitización XSS en el cliente.
* **Auditoría Técnica y Dashboard Analítico:** Inspección puerto por puerto (`SC/APC`) y panel de KPIs consolidados con **Chart.js**.

---

## Stack Tecnológico

* **Backend:** Python 3.13+, FastAPI, Uvicorn, SQLModel, SQLite (`PRAGMA foreign_keys=ON`).
* **Frontend:** HTML5, JavaScript ES6+ modular (sin frameworks pesados), Tailwind CSS, Leaflet.js 1.9.4, Chart.js 4.4.1.
* **Testing & QA:** Pytest, FastAPI `TestClient`, Playwright (pruebas E2E en Chromium).

---

## Estructura del Proyecto

```text
gestion-nap/
├── app/
│   ├── api/v1/
│   │   ├── auth.py              # Autenticación JWT, PBKDF2 y rate limiting
│   │   └── naps.py              # Endpoints REST de cajas NAP, telemetría y KPIs
│   ├── core/
│   │   └── database.py          # Motor SQLite, sesiones SQLModel y PRAGMA FK
│   ├── models/
│   │   ├── nap.py               # Entidades NAP, Puerto, LecturaPotencia, Auditoria
│   │   └── user.py              # Entidad User y esquemas de lectura segura
│   ├── services/
│   │   └── nap_service.py       # Reglas de dominio FTTH-GPON e ITU-T G.984.2
│   └── main.py                  # Aplicación FastAPI y middlewares de seguridad
├── frontend/
│   ├── assets/
│   │   ├── css/custom.css       # Estilos GIS y animaciones de alerta crítica
│   │   └── js/
│   │       ├── api.js           # Cliente HTTP centralizado y guardia JWT
│   │       ├── components.js    # Pines SVG y popups Leaflet sanitizados
│   │       ├── map.js           # Controlador principal del mapa GIS
│   │       └── telemetry.js     # Validación e ingesta de telemetría en campo
│   ├── login.html               # Vista de inicio de sesión
│   ├── index.html               # Mapa GIS operativo y modal de auditoría
│   └── dashboard.html           # Dashboard ejecutivo de KPIs y alertas
├── tests/
│   ├── test_models.py           # Pruebas de validación de modelos e integridad BD
│   ├── test_naps.py             # Pruebas unitarias de matriz óptica ITU-T G.984
│   ├── test_backend_api.py      # Pruebas de integración API + SQLite
│   ├── test_frontend_map.py     # Pruebas E2E Playwright del mapa y sesión JWT
│   └── test_frontend_telemetry.py # Pruebas E2E Playwright del formulario de campo
├── seed_db.py                   # Carga idempotente de 5 cajas NAP piloto en Guarenas
├── emulador_telemetria.py       # Simulador CLI de telemetría GPON autenticado
├── MANUAL_DE_USUARIO.md         # Guía operativa para técnicos y supervisores
└── TAREAS_PENDIENTES_EQUIPO.md  # Hoja de ruta de cierre para el equipo
```

---

## Instalación y Puesta en Marcha

### 1. Clonar el repositorio y activar el entorno virtual

```bash
git clone <URL_DEL_REPOSITORIO>
cd gestion-nap
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Poblar la base de datos SQLite con datos piloto

```bash
python3 seed_db.py
```

Este comando crea `gestion_nap.db` (si no existe) e inserta 5 Cajas NAP georreferenciadas en Guarenas junto con sus puertos `SC/APC` y lecturas ópticas iniciales.

### 3. Ejecutar el Backend y el Frontend

En una terminal, levante la API FastAPI:

```bash
uvicorn app.main:app --reload --port 8000
```

En una segunda terminal, sirva los archivos estáticos del frontend:

```bash
python3 -m http.server 8080 -d frontend
```

Acceda desde su navegador a **`http://localhost:8080/login.html`**.

---

## Credenciales de Prueba

| Rol | Usuario | Contraseña | Permisos |
| :--- | :--- | :--- | :--- |
| **Operador** | `operador@gestionnap.ve` | `plaza2026` | Consulta de mapa, dashboard, auditoría y registro de telemetría |
| **Administrador** | `admin` | `admin123` | Todos los permisos de operador + alta de nuevas cajas NAP (`POST /api/v1/naps/`) |

---

## Ejecución de Pruebas Automatizadas

El proyecto cuenta con **48 pruebas automatizadas** (unitarias, de seguridad, integración SQLite y E2E en navegador):

```bash
pytest -v
```

Para simular inyección continua de telemetría óptica en tiempo real sobre un puerto existente (con `uvicorn` activo):

```bash
python3 emulador_telemetria.py --puerto 2 --modo critico --ciclos 3
```