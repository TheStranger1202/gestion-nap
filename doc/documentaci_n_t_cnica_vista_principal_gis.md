# Especificación Técnica y Guía de Arquitectura: Vista Principal del Mapa Interactivo GIS (Gestión NAP)

* **Proyecto:** Sistema de Gestión y Telemetría de Red de Distribución Óptica FTTH — Municipio Plaza (Guarenas, Estado Miranda).
* **Actividad Atómica:** *Diseñar la vista principal con el mapa interactivo georreferenciado para visualizar la distribución de cajas NAP en el Municipio Plaza y su estado según el color del marcador.*
* **Módulo:** `frontend/` (Capa de Presentación GIS) y `tests/` (Aseguramiento de Calidad E2E).
* **Estándares Aplicados:** ISO/IEC/IEEE 12207 (Trazabilidad y Documentación), WGS84 / EPSG:4326 (Georreferenciación), Nomenclatura Oficial `PLZ` y Conventional Commits v1.0.0.

---

## 1. Propósito y Principio de Trazabilidad

En ingeniería de software rige una máxima fundamental: **"si no está documentado, no existe"**. Un código funcional sin especificación técnica pierde trazabilidad frente a los requerimientos del sistema, dificulta su mantenimiento por parte de otros desarrolladores y carece de respaldo formal ante una auditoría o defensa técnica.

Este documento formaliza el diseño, la arquitectura modular, las decisiones cartográficas y el protocolo de pruebas automatizadas de la vista principal de **Gestión NAP**. Asimismo, establece el contrato de integración para migrar de los datos simulados (`MOCK_NAPS`) al consumo en tiempo real de la API REST construida en FastAPI.

---

## 2. Arquitectura y Estructura del Frontend

Para garantizar tiempos de carga mínimos, cero sobrecarga de compilación (*zero-build*) y total compatibilidad con el servidor backend en Python, se adoptó una **arquitectura modular basada en componentes desacoplados sobre JavaScript nativo (ES6+)**, apoyada en **Tailwind CSS** para el sistema de diseño y **Leaflet.js** como motor cartográfico.

### 2.1 Distribución de Archivos

```text
gestion-nap/
├── frontend/
│   ├── index.html                  # Contenedor estructural, barra de telemetría y leyenda GIS
│   └── assets/
│       ├── css/
│       │   └── custom.css          # Reglas del lienzo cartográfico, popups y animaciones SVG
│       └── js/
│           ├── components.js       # Fábrica de componentes visuales (Pines SVG y Popups)
│           └── map.js              # Controlador GIS, capa base OSM, estado y eventos
└── tests/
    └── test_frontend_map.py        # Suite de pruebas automatizadas Cross-Browser (Playwright)
```

### 2.2 Responsabilidad por Componente

| Archivo | Patrón / Tecnología | Responsabilidad Principal |
| :--- | :--- | :--- |
| `frontend/index.html` | HTML5 + Tailwind CSS | Define el layout a pantalla completa (`h-screen overflow-hidden`), la barra superior de indicadores rápidos, el contenedor `#map` y la leyenda flotante de estados. |
| `frontend/assets/css/custom.css` | CSS3 + Keyframes | Limpia estilos por defecto de Leaflet (`divIcon`), estiliza el contenedor de popups y define la animación `@keyframes pulse-ring` para alertas críticas. |
| `frontend/assets/js/components.js` | *Revealing Module Pattern* (`NapComponents`) | Encapsula la lógica visual pura: traduce `estado_general` a códigos hexadecimales, genera marcadores SVG dinámicos y construye las plantillas HTML de los popups. |
| `frontend/assets/js/map.js` | Controlador orientado a eventos | Inicializa el mapa centrado en Guarenas, carga las teselas de OpenStreetMap, itera los datos de las cajas NAP, actualiza contadores y captura clics en botones internos. |
| `tests/test_frontend_map.py` | `pytest` + `playwright` | Levanta un servidor HTTP aislado y verifica el renderizado, la carga de mapas, los marcadores y los eventos en **Chromium** y **Firefox**. |

---

## 3. Diseño Cartográfico y Lógica de Funcionamiento

### 3.1 Georreferenciación y Encuadre del Municipio Plaza
El mapa se inicializa utilizando el sistema de coordenadas geográficas **WGS84 (EPSG:4326)**, proyectado internamente por Leaflet en **Web Mercator (EPSG:3857)**:

* **Centroide Operativo (`MUNICIPIO_PLAZA_CENTER`):** `[10.4635, -66.6010]`
* **Nivel de Zoom Inicial (`DEFAULT_ZOOM`):** `14`

Este encuadre permite visualizar simultáneamente el eje oeste —Casco Central de Guarenas (`Z01`)— y el eje este —Urbanización Nueva Casarapa (`Z04`)—, manteniendo una precisión de $6$ decimales en latitud y longitud (equivalente a un margen de error espacial inferior a $0.11\text{ m}$, suficiente para identificar postes individuales en campo).

### 3.2 Capa Base Cartográfica (*Tile Layer*)
El mapa utiliza el servidor oficial de teselas raster de **OpenStreetMap**:
```javascript
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors | Gestión NAP Plaza',
  maxZoom: 19
}).addTo(map);
```
**Justificación técnica:** Durante la fase de prototipado se descartaron proveedores comerciales con marcas de agua por ausencia de credenciales (`API KEY REQUIRED`), garantizando visualización gratuita, sin restricciones de clave en desarrollo y con alta densidad de vialidad local en el Estado Miranda.

### 3.3 Codificación Visual Condicional (`estado_general`)
En `components.js`, el diccionario `STATUS_CONFIG` desacopla las reglas de negocio visuales del controlador del mapa:

| `estado_general` | Color Hexadecimal | Representación Visual | Significado Operativo |
| :--- | :--- | :--- | :--- |
| **`OPTIMO`** | `#10b981` (Esmeralda) | Pin sólido estático | Potencia óptica nominal y puertos disponibles. |
| **`ADVERTENCIA`** | `#f59e0b` (Ámbar) | Pin sólido estático | Atenuación leve o umbral de ocupación cercano al límite. |
| **`CRITICO`** | `#e11d48` (Carmesí) | Pin con halo pulsante (`nap-critical-pulse`) | Falla de enlace, pérdida de señal óptica o saturación total. |

Para lograr que la punta inferior del marcador SVG coincida exactamente con la coordenada del poste al hacer zoom, se calibró el anclaje del icono en `L.divIcon`:
* `iconSize: [36, 44]` (dimensiones del lienzo SVG en píxeles).
* `iconAnchor: [18, 42]` (centro horizontal $x = 18$, vértice inferior $y = 42$).
* `popupAnchor: [0, -38]` (despliegue del globo informativo justo encima del cabezal del pin).

### 3.4 Gestión de Popups y Delegación de Eventos
Leaflet destruye y reconstruye dinámicamente el DOM de cada popup cada vez que el usuario hace clic sobre un marcador. Por ello, en lugar de incrustar atributos `onclick` en cadenas de texto HTML (mala práctica de seguridad y mantenimiento), `map.js` escucha el evento nativo `popupopen` del mapa:

```javascript
map.on('popupopen', (event) => {
  const popupElement = event.popup.getElement();
  const detailsBtn = popupElement?.querySelector('.btn-ver-detalles');
  if (detailsBtn) {
    detailsBtn.onclick = () => {
      const napId = Number(detailsBtn.getAttribute('data-nap-id'));
      // Invocación limpia al flujo de inspección detallada
    };
  }
});
```

---

## 4. Guía Paso a Paso de Ejecución de la Actividad

La construcción y validación de la vista principal siguió un flujo incremental de 6 etapas:

1. **Maquetación de la Interfaz (`frontend/index.html`):** Se estructuró el contenedor principal con Flexbox vertical (`flex flex-col h-screen`) para evitar barras de desplazamiento accidentales, integrando el encabezado oscuro (`bg-slate-900`), los indicadores estadísticos (`#stat-total`, `#stat-optimo`, `#stat-critico`) y la leyenda flotante con `z-[1000]` para superponerse a las capas de Leaflet.
2. **Estilización Especializada (`frontend/assets/css/custom.css`):** Se eliminó el recuadro blanco predeterminado de `.leaflet-div-icon` y se creó la animación de ondas expansivas (`@keyframes pulse-ring`) aplicada exclusivamente a los nodos en estado `CRITICO`.
3. **Construcción de Componentes UI (`frontend/assets/js/components.js`):** Se implementó el módulo `NapComponents` con los métodos `createNapMarkerIcon()` y `createNapPopupContent()`, validando el cumplimiento de la nomenclatura `PLZ-[ZONA]-[SECTOR]-[DISTRIBUCION]-[CONSECUTIVO]-[MONTAJE]`.
4. **Programación del Controlador GIS (`frontend/assets/js/map.js`):** Se instanció `L.map`, se reposicionó el control de zoom en `bottomright` (evitando colisiones con la leyenda en `bottomleft`), se agruparon los marcadores dentro de un `L.layerGroup()` para facilitar futuras actualizaciones y se conectaron los datos `MOCK_NAPS`.
5. **Auditoría Visual y Corrección Cartográfica:** Mediante servidor local (`python3 -m http.server 8080 --directory frontend`) y DevTools se detectó la restricción de teselas de CARTO y se migró a OpenStreetMap, verificando el encuadre en Guarenas.
6. **Automatización de Pruebas E2E (`tests/test_frontend_map.py`):** Se escribió una prueba con `pytest` y `playwright` que valida ausencia de errores JavaScript (`pageerror`), carga efectiva de teselas (`.leaflet-tile-loaded`), exactitud de contadores, presencia de marcadores y captura del evento de consola al pulsar **"Ver Detalles"** tanto en **Chromium** como en **Firefox**.

---

## 5. Plan de Integración con el Backend vía API REST

Actualmente, `map.js` opera con la constante local `MOCK_NAPS`. Dado que su estructura de atributos (`id`, `codigo_nap`, `zona`, `sector`, `ubicacion_referencia`, `latitud`, `longitud`, `estado_fisico`, `capacidad_puertos`, `estado_general`) es idéntica al esquema de respuesta del backend en FastAPI (`app/api/v1/naps.py`), la integración requiere únicamente sustituir el arreglo estático por consumo asíncrono mediante `fetch()`.

### 5.1 Flujo de Autenticación y Consumo de Datos

1. **Autenticación JWT:** El usuario inicia sesión en `frontend/login.html` contra `POST /api/v1/auth/login`. El token JWT recibido se almacena en `localStorage.getItem('access_token')`.
2. **Petición Geográfica (`GET /api/v1/naps`):** Al cargar `index.html`, `map.js` solicita el listado completo de cajas NAP enviando el encabezado `Authorization: Bearer <token>`.
3. **Actualización Reactiva de Capas:** Al recibir el JSON desde SQLite/SQLModel, se invoca `renderNapMarkers(data)`, el cual limpia `napMarkersLayer.clearLayers()` y redibuja los pines sin recargar la página ni perder el nivel de zoom actual del operador.
4. **Inspección Profunda (`GET /api/v1/naps/{id}`):** Al hacer clic en el botón **"Ver Detalles"** del popup, en lugar de imprimir en consola, se consultará el detalle de puertos ópticos y telemetría (`emulador_telemetria.py`) para abrir un panel lateral (*drawer*) o modal con las mediciones en $\text{dBm}$ (estándar ITU-T G.984).

### 5.2 Patrón de Implementación para la Fase de Integración (`map.js`)

```javascript
const API_BASE_URL = 'http://localhost:8000/api/v1';

async function loadNapsFromApi() {
  const token = localStorage.getItem('access_token');

  try {
    const response = await fetch(`${API_BASE_URL}/naps`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      }
    });

    if (response.status === 401) {
      window.location.href = 'login.html';
      return;
    }

    if (!response.ok) {
      throw new Error(`Error HTTP ${response.status} al consultar cajas NAP`);
    }

    const napsData = await response.json();
    renderNapMarkers(napsData);
  } catch (error) {
    console.error('[Gestión NAP] Fallo de sincronización con API:', error);
  }
}
```

---

