# Especificación Técnica y Guía de Arquitectura: Vista Principal del Mapa Interactivo GIS (Gestión NAP)

* **Proyecto:** Sistema de Gestión y Telemetría de Red de Distribución Óptica FTTH — Municipio Plaza (Guarenas, Estado Miranda).
* **Actividad Atómica:** *Diseñar e integrar la vista principal con el mapa interactivo georreferenciado para visualizar la distribución de cajas NAP en el Municipio Plaza y su estado operativo en tiempo real.*
* **Módulo:** `frontend/` (Capa de Presentación GIS) y `tests/` (Aseguramiento de Calidad E2E).
* **Estándares Aplicados:** ISO/IEC/IEEE 12207 (Trazabilidad y Documentación), WGS84 / EPSG:4326 (Georreferenciación), Nomenclatura Oficial `PLZ` y Conventional Commits v1.0.0.

---

## 1. Propósito y Principio de Trazabilidad

En ingeniería de software rige una máxima fundamental: **"si no está documentado, no existe"**. Un código funcional sin especificación técnica pierde trazabilidad frente a los requerimientos del sistema, dificulta su mantenimiento por parte de otros desarrolladores y carece de respaldo formal ante una auditoría o defensa técnica.

Este documento formaliza el diseño, la arquitectura modular, las decisiones cartográficas, la integración con la API REST en FastAPI y el protocolo de pruebas automatizadas de la vista principal de **Gestión NAP**.

---

## 2. Arquitectura y Estructura del Frontend

Para garantizar tiempos de carga mínimos, cero sobrecarga de compilación (*zero-build*) y total compatibilidad con el servidor backend en Python, se adoptó una **arquitectura modular basada en componentes desacoplados sobre JavaScript nativo (ES6+)**, apoyada en **Tailwind CSS** para el sistema de diseño y **Leaflet.js** como motor cartográfico.

### 2.1 Distribución de Archivos

```text
gestion-nap/
├── frontend/
│   ├── login.html                  # Vista de autenticación JWT
│   ├── index.html                  # Mapa GIS operativo, formulario de telemetría y modal de auditoría
│   ├── dashboard.html              # Dashboard ejecutivo de KPIs con Chart.js
│   └── assets/
│       ├── css/
│       │   └── custom.css          # Reglas del lienzo cartográfico, popups y animaciones SVG
│       └── js/
│           ├── api.js              # Cliente HTTP centralizado y guardia de sesión JWT
│           ├── components.js       # Fábrica de componentes visuales (Pines SVG y Popups sanitizados)
│           ├── map.js              # Controlador GIS, capa base OSM, estado y eventos
│           └── telemetry.js        # Validación e ingesta de telemetría óptica en campo
└── tests/
    └── test_frontend_map.py        # Suite de pruebas automatizadas E2E (Playwright)
```

### 2.2 Responsabilidad por Componente

| Archivo | Patrón / Tecnología | Responsabilidad Principal |
| :--- | :--- | :--- |
| `frontend/index.html` | HTML5 + Tailwind CSS | Define el layout a pantalla completa (`h-screen overflow-hidden`), la barra superior de indicadores rápidos, el contenedor `#map`, la leyenda flotante y el modal de auditoría. |
| `frontend/assets/css/custom.css` | CSS3 + Keyframes | Limpia estilos por defecto de Leaflet (`divIcon`), estiliza el contenedor de popups y define la animación `@keyframes pulse-ring` para alertas críticas. |
| `frontend/assets/js/api.js` | Cliente HTTP / Guardia JWT | Centraliza las peticiones `fetch` hacia FastAPI, inyecta la cabecera `Authorization: Bearer <token>` desde `localStorage` y redirige a `login.html` ante respuestas `401 Unauthorized`. |
| `frontend/assets/js/components.js` | *Revealing Module Pattern* (`NapComponents`) | Encapsula la lógica visual pura: traduce `estado_general` a códigos hexadecimales, genera marcadores SVG dinámicos y construye popups sanitizados contra XSS. |
| `frontend/assets/js/map.js` | Controlador orientado a eventos | Inicializa el mapa centrado en Guarenas, consume `GET /api/v1/naps`, actualiza los contadores de estado y abre el modal de auditoría de puertos al pulsar **"Ver Detalles"**. |
| `tests/test_frontend_map.py` | `pytest` + `playwright` | Valida el inicio de sesión JWT, el renderizado de teselas, los marcadores y el flujo de inspección en Chromium. |

---

## 3. Diseño Cartográfico y Lógica de Funcionamiento

### 3.1 Georreferenciación y Encuadre del Municipio Plaza
El mapa se inicializa utilizando el sistema de coordenadas geográficas **WGS84 (EPSG:4326)**, proyectado internamente por Leaflet en **Web Mercator (EPSG:3857)**:

* **Centroide Operativo (`MUNICIPIO_PLAZA_CENTER`):** `[10.4635, -66.6010]`
* **Nivel de Zoom Inicial (`DEFAULT_ZOOM`):** `14`

Este encuadre permite visualizar simultáneamente el eje oeste —Casco Central de Guarenas (`Z01`)— y el eje este —Urbanización Nueva Casarapa (`Z04`)—, manteniendo una precisión de $6$ decimales en latitud y longitud (margen de error espacial inferior a $0.11\text{ m}$).

### 3.2 Capa Base Cartográfica (*Tile Layer*)
El mapa utiliza el servidor oficial de teselas raster de **OpenStreetMap**:
```javascript
L.tileLayer('[https://tile.openstreetmap.org/](https://tile.openstreetmap.org/){z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap contributors | Gestión NAP Plaza',
  maxZoom: 19
}).addTo(map);
```
**Justificación técnica:** Se descartaron proveedores comerciales con restricciones por clave (`API KEY REQUIRED`), garantizando visualización gratuita, sin marcas de agua y con alta densidad vial en el Estado Miranda.

### 3.3 Codificación Visual Condicional (`estado_general`) y Mapeo Óptico
En `components.js`, el diccionario `STATUS_CONFIG` desacopla las reglas visuales del controlador del mapa y refleja el consolidado de la telemetría ITU-T G.984.2 de los puertos de cada caja:

| `estado_general` (Mapa) | Origen en Telemetría (`EstadoPotencia`) | Color Hexadecimal | Representación Visual | Significado Operativo |
| :--- | :--- | :--- | :--- | :--- |
| **`OPTIMO`** | Puertos en `OPTIMO` | `#10b981` (Esmeralda) | Pin sólido estático | Potencia óptica nominal y operación estable. |
| **`ADVERTENCIA`** | Puertos en `CRITICO` (degradación) | `#f59e0b` (Ámbar) | Pin sólido estático | Atenuación leve o umbral preventivo cercano al límite. |
| **`CRITICO`** | Puertos en `CAIDO` (corte o saturación) | `#e11d48` (Carmesí) | Pin con halo pulsante (`nap-critical-pulse`) | Falla de enlace, pérdida de señal óptica o saturación. |

Para que la punta inferior del marcador SVG coincida exactamente con la coordenada del poste al hacer zoom, se calibró el anclaje en `L.divIcon`:
* `iconSize: [36, 44]`
* `iconAnchor: [18, 42]`
* `popupAnchor: [0, -38]`

### 3.4 Gestión de Popups y Delegación de Eventos
Dado que Leaflet reconstruye el DOM de cada popup al abrirlo, `map.js` evita atributos `onclick` en línea y delega la interacción mediante el evento nativo `popupopen`, enlazando el botón **"Ver Detalles"** con el flujo de inspección del modal de auditoría de puertos `SC/APC`.

---

## 4. Integración Activa con el Backend vía API REST

El frontend opera completamente conectado a la API FastAPI (`http://localhost:8000/api/v1`) a través de `frontend/assets/js/api.js`:

1. **Autenticación JWT:** El usuario inicia sesión en `frontend/login.html` contra `POST /api/v1/auth/login`. El token JWT recibido se almacena en `localStorage` bajo la clave `access_token` y es verificado al cargar `index.html` y `dashboard.html`.
2. **Carga Geográfica (`GET /api/v1/naps`):** Al iniciar el mapa, `map.js` solicita el inventario real almacenado en SQLite/SQLModel y ejecuta `renderNapMarkers(data)`, limpiando `napMarkersLayer` y dibujando los pines y contadores actualizados.
3. **Inspección de Puertos:** Al pulsar **"Ver Detalles"** en el popup de una caja, se consulta el detalle de sus puertos `SC/APC` y últimas lecturas ópticas en $\text{dBm}$ para desplegar el modal de auditoría técnica.
4. **Sincronización con Telemetría:** Cuando el técnico registra una nueva lectura desde `telemetry.js`, el mapa recarga los marcadores y contadores sin recargar la página ni perder el encuadre actual.