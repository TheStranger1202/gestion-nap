# Documentación Técnica: Formulario Interactivo de Telemetría Óptica en Campo

**Proyecto:** Sistema de Gestión y Auditoría de Cajas NAP — Municipio Plaza (Guarenas, Estado Miranda)  
**Módulo:** Frontend GIS e Ingesta de Telemetría (`frontend/`)  
**Artefactos cubiertos:** `frontend/index.html`, `frontend/assets/js/telemetry.js`, `tests/test_frontend_telemetry.py`  
**Estándar de trazabilidad:** ISO/IEC/IEEE 12207 · Conventional Commits v1.0.0

---

## 1. Filosofía de Ingeniería: *"Si no está documentado, no existe"*

En el desarrollo de software profesional y en la ingeniería de telecomunicaciones, un componente funcional cuyo diseño, restricciones y decisiones de seguridad permanecen únicamente en el código fuente representa un riesgo operativo: no es auditable, dificulta el relevo técnico y carece de respaldo formal ante evaluaciones o auditorías.

Alineado con los principios de trazabilidad de la norma **ISO/IEC/IEEE 12207**, este documento establece la línea base oficial del módulo de captura de telemetría en campo. Su propósito es doble:

1. **Garantizar la mantenibilidad y escalabilidad técnica:** Dejar explícito cómo opera la interfaz actual en modo simulado (*mock*) y cuál es el contrato exacto para acoplarla al backend FastAPI sin refactorizar la vista.
2. **Servir como base de sustentación académica:** Proveer los fundamentos arquitectónicos, de seguridad y de negocio necesarios para defender el diseño del sistema ante un jurado evaluador.

---

## 2. Resumen Ejecutivo y Alcance del Módulo

El formulario interactivo de registro de potencia óptica permite a los técnicos de planta externa simular o ingresar lecturas de telemetría GPON directamente sobre el mapa operativo GIS del Municipio Plaza, sin abandonar el contexto geográfico ni recargar la aplicación.

### Objetivos cumplidos
* **Integración no intrusiva:** Se superpone como una tarjeta flotante colapsable sobre el lienzo cartográfico de `Leaflet.js` en `frontend/index.html`, respetando el DOM, los estilos y los selectores probados previamente en `map.js` y `components.js`.
* **Validación territorial en tiempo real:** Verifica instantáneamente la sintaxis del identificador de caja terminal mediante la expresión regular oficial del Municipio Plaza, ofreciendo retroalimentación visual inmediata (borde verde o rojo) y validación cruzada de Zonas Operativas de Distribución (ZOD).
* **Blindaje de seguridad en cliente:** Implementa protección contra inyección DOM-XSS, validación numérica estricta de señales ópticas en $\text{dBm}$, bloqueo contra envíos duplicados (*double-submit*) y aislamiento de eventos frente al mapa.
* **Desacoplamiento mediante eventos:** Emite un evento personalizado del navegador (`nap:telemetry-submitted`) con una carga útil (*payload*) inmutable y tipada, preparando el terreno para la futura conexión vía API REST.

---

## 3. Arquitectura y Diseño del Sistema

### 3.1 Estructura de Archivos Involucrados

```text
gestion-nap/
├── doc/
│   └── documentacion_formulario_telemetria.md   # Este documento técnico
├── frontend/
│   ├── index.html                               # Vista principal GIS + Tarjeta flotante y contenedor Toast
│   └── assets/
│       └── js/
│           ├── components.js                    # Componentes visuales auxiliares
│           ├── map.js                           # Controlador Leaflet.js y datos MOCK_NAPS
│           └── telemetry.js                     # Lógica encapsulada de validación, seguridad y envío
└── tests/
    ├── test_frontend_map.py                     # Pruebas E2E del mapa y marcadores
    └── test_frontend_telemetry.py               # Pruebas E2E del formulario de telemetría
```

### 3.2 Jerarquía Visual, Responsividad y Capas (`z-index`)

El diseño utiliza **Tailwind CSS** bajo una paleta coherente con la barra superior (`slate-900`) y la leyenda GIS (`white/95` con `backdrop-blur-md`). Para evitar colisiones visuales entre el mapa interactivo, los controles flotantes y las alertas, se definió una jerarquía estricta de apilamiento:

| Capa / Elemento | Selector / ID | Clase `z-index` | Posición y Comportamiento Responsivo |
| :--- | :--- | :---: | :--- |
| **Lienzo Cartográfico** | `#map` | `z-10` | Ocupa el $100\%$ del área disponible debajo del `<header>`. |
| **Barra Superior** | `<header>` | `z-20` | Fija en la parte superior (`h-16`) con indicadores globales. |
| **Leyenda GIS** | `<aside>` | `z-[1000]` | Esquina inferior izquierda (`bottom-6 left-4`). |
| **Panel de Telemetría** | `#telemetry-panel` | `z-[1000]` | Esquina superior derecha (`top-4 right-4`). En móviles ocupa `w-[calc(100vw-2rem)]` y en pantallas `sm:` o superiores `sm:w-96`, con botón colapsable (`#telemetry-toggle-btn`) para liberar visibilidad del mapa en campo. |
| **Notificación Toast** | `#telemetry-toast-container` | `z-[1100]` | Fija en la esquina inferior derecha (`bottom-6 right-4`), por encima de cualquier panel, con `pointer-events-none` en el contenedor para no bloquear clics en el mapa. |

### 3.3 Diagrama de Flujo de Datos (Arquitectura Desacoplada)

```text
+-------------------------------------------------------------------+
|                   Usuario / Técnico en Campo                      |
+---------------------------------+---------------------------------+
                                  |
             1. Ingresa Código NAP, Puerto (1-16) y Potencia (dBm)
                                  v
+-------------------------------------------------------------------+
|           frontend/index.html (#telemetry-form)                   |
|  - Atributos HTML5 (required, pattern, step="0.01", min, max)     |
+---------------------------------+---------------------------------+
                                  |
             2. Eventos 'input', 'change', 'blur' y 'submit'
                                  v
+-------------------------------------------------------------------+
|           frontend/assets/js/telemetry.js (IIFE 'use strict')     |
|  - Intercepta submit -> e.preventDefault()                        |
|  - Valida regex ^PLZ-Z0[1-8]-[A-Z]{3}-D\d{3}-\d{3}-[AFS]$          |
|  - Valida rango entero de puerto [1..16] y potencia [-50..+5] dBm |
|  - Congela payload con Object.freeze(...)                         |
+----------------+---------------------------------+----------------+
                 |                                 |
   3a. Limpia UI y muestra Toast     3b. Despacha CustomEvent
                 v                                 v
+---------------------------------+ +-------------------------------+
|  #telemetry-toast-container     | | Evento en document:           |
|  (Nodos DOM seguros via         | | 'nap:telemetry-submitted'     |
|   createElement + textContent)  | | -> Listo para API REST / Mapa |
+---------------------------------+ +-------------------------------+
```

---

## 4. Especificación de Campos, Reglas de Negocio y Blindaje de Seguridad

### 4.1 Validación del Código NAP y Coherencia Territorial

Cada Caja de Acceso Terminal (NAP) en el Municipio Plaza responde a la sintaxis oficial:

$$\text{PLZ}-\text{[ZONA]}-\text{[SECTOR]}-\text{[DISTRIBUCION]}-\text{[CONSECUTIVO]}-\text{[MONTAJE]}$$

* **Expresión Regular Estricta (`NAP_CODE_REGEX`):**
  ```regex
  ^PLZ-Z0[1-8]-[A-Z]{3}-D\d{3}-\d{3}-[AFS]$
  ```
* **Retroalimentación Visual en Tiempo Real:**
  * **Estado inicial / limpio (`pristine`):** Borde neutro `border-slate-300`. Evita mostrar errores falsos antes de que el técnico comience a escribir o inmediatamente después de registrar una lectura.
  * **Estado inválido (`INVALID`):** Borde rojo `border-rose-500 ring-2 ring-rose-500/20` y atributo `aria-invalid="true"`.
  * **Estado válido (`VALID`):** Borde verde `border-emerald-500 ring-2 ring-emerald-500/20` y atributo `aria-invalid="false"`. Adicionalmente, el módulo consulta el catálogo inmutable `ZOD_SECTORS` (`Z01` a `Z08`) para confirmar en el texto de ayuda si el acrónimo de 3 letras corresponde a un sector catalogado de esa zona operativa.

### 4.2 Iteraciones de Blindaje de Seguridad Frontend

El desarrollo incorporó dos iteraciones explícitas de endurecimiento (*hardening*) antes de escribir la interfaz:

#### Iteración 1: Integridad del DOM y Aislamiento de Ejecución
1. **Prevención de DOM-Based XSS:** Las notificaciones flotantes (*Toast*) y los mensajes de validación jamás utilizan `innerHTML` ni `insertAdjacentHTML`. Toda inserción dinámica se construye mediante `document.createElement` y `textContent`, garantizando que cualquier cadena sea tratada como texto plano por el navegador.
2. **Validación en Doble Capa (HTML5 + JavaScript):** Dado que los atributos HTML5 (`pattern`, `min`, `max`, `required`) pueden modificarse desde las herramientas de desarrollador del navegador, `telemetry.js` ejecuta su propia validación independiente antes de procesar cualquier dato, almacenando límites y expresiones regulares en objetos sellados con `Object.freeze()`.
3. **Encapsulamiento de Ámbito (*Scope*):** Todo el controlador se envuelve en una expresión de función ejecutada inmediatamente (`(() => { 'use strict'; ... })()`), evitando contaminar el objeto global `window` y eliminando colisiones de variables con `leaflet.js` o `map.js`.

#### Iteración 2: Resiliencia de Interfaz y Validación Numérica
1. **Protección contra Envíos Duplicados (*Race Conditions*):** Mediante una bandera de estado `isSubmitting` y el deshabilitado temporal del botón `#telemetry-submit-btn`, se impide que múltiples clics rápidos o pulsaciones repetidas de `Enter` disparen registros duplicados.
2. **Validación Numérica Estricta para Potencia Óptica ($\text{dBm}$):** Los campos `<input type="number">` presentan comportamientos particulares cuando el usuario escribe caracteres parciales (como `"-"`, `"--15"` o notación científica `"1e2"`). El sistema evalúa `powerInput.validity.badInput`, verifica `Number.isFinite()`, exige el patrón `/^-?\d+(\.\d{1,2})?$/` (resolución de $0.01\text{ dBm}$), acota el rango físico GPON entre $-50.00\text{ dBm}$ y $+5.00\text{ dBm}$, y normaliza $-0$ a $0$.
3. **Aislamiento de Eventos frente a Leaflet.js:** Se aplican `L.DomEvent.disableClickPropagation(panel)` y `L.DomEvent.disableScrollPropagation(panel)` sobre la tarjeta flotante para evitar que los clics dentro de los inputs o el desplazamiento en pantallas pequeñas muevan el mapa o alteren el nivel de zoom.

### 4.3 Matriz de Casos Borde (*Edge Cases*) Contemplados

| Escenario / Caso Borde | Comportamiento del Sistema | Mecanismo Implementado |
| :--- | :--- | :--- |
| Formulario recién cargado o recién enviado | No muestra borde rojo en el Código NAP vacío | Bandera de estado `isNapDirty` + `resetFormState()` |
| Código con zona fuera de rango (`PLZ-Z09-...`) o montaje inválido (`...-X`) | Marca borde rojo inmediato y bloquea envío | `NAP_CODE_REGEX.test(value)` en evento `input` |
| Manipulación del `<select>` desde DevTools (`value="99"` o `"1.5"`) | Rechaza el envío y enfoca el selector | `Number.isInteger(port) && port >= 1 && port <= 16` |
| Entrada numérica incompleta (`"-"` o `"15..2"`) en potencia | Detecta entrada mal formada sin fallar silenciosamente | Inspección de `powerInput.validity.badInput` |
| Dos envíos exitosos consecutivos en menos de $3.5\text{ s}$ | Reinicia el temporizador y reemplaza el Toast limpiamente | `clearTimeout(activeToastTimeout)` + limpieza de nodos hijos |
| Pantalla móvil estrecha (ej. $360\text{ px}$ de ancho) | La tarjeta no desborda ni oculta permanentemente el mapa | Clases `w-[calc(100vw-2rem)]` + botón colapsable `aria-expanded` |

---

## 5. Guía Paso a Paso de Implementación y Verificación

Esta sección resume la secuencia metodológica ejecutada para construir y validar el requerimiento:

1. **Análisis de Requisitos y Seguridad:** Se revisó la especificación territorial (`mapeo_territorial_y_nomenclatura_nap.md`), el estándar de commits (`estandar_de_commits.md`) y la estructura de `frontend/index.html` para diseñar un componente autónomo que no alterara los IDs existentes (`#map`, `#stat-total`, `#stat-optimo`, `#stat-critico`).
2. **Inyección de Estructura HTML en `frontend/index.html`:**
   * Se añadió el contenedor `<section id="telemetry-panel">` dentro de `<main>`, con campos accesibles (`<label for="...">`, `aria-describedby`, `aria-live="polite"`).
   * Se incluyó el contenedor `#telemetry-toast-container` y la referencia `<script src="assets/js/telemetry.js"></script>` al final del `<body>`.
3. **Desarrollo del Controlador en `frontend/assets/js/telemetry.js`:**
   * Se implementaron los validadores individuales (`validateNapCode`, `validatePort`, `validatePower`), el gestor de notificaciones (`showToast`) y el manejador de `submit` con `e.preventDefault()`.
4. **Verificación Manual y Pruebas Automatizadas E2E (`Playwright`):**
   * Se levantó el servidor estático local (`python3 -m http.server 8080 --directory frontend`) para inspeccionar visualmente el comportamiento en navegador y consola.
   * Se creó la suite `tests/test_frontend_telemetry.py` con **Pytest + Playwright** para automatizar la verificación de cero errores JS, cambio de clases CSS en tiempo real (`border-rose-500` a `border-emerald-500`), bloqueo de potencias fuera de rango, ausencia de recarga de página (`window.__no_page_reload`), aparición del Toast y limpieza del formulario.
   * Se ejecutaron ambas suites (`pytest tests/test_frontend_telemetry.py tests/test_frontend_map.py -v`) confirmando $0$ regresiones.
5. **Control de Versiones Atómico:** Se registraron los cambios en Git siguiendo Conventional Commits (`feat(frontend): ...` y `test(frontend): ...`).

---

## 6. Hoja de Ruta: Integración con el Backend vía API REST

### 6.1 Situación Actual (Modo Simulado / Mock)

Actualmente, el frontend opera de manera autónoma sin dependencias de red hacia el backend:
* `frontend/assets/js/map.js` renderiza los marcadores iniciales a partir de un arreglo estático en memoria (`MOCK_NAPS`).
* `frontend/assets/js/telemetry.js` valida los datos en el cliente, simula el registro exitoso mostrando el Toast y despacha el evento personalizado `nap:telemetry-submitted` con el siguiente contrato de datos:

```json
{
  "codigo_nap": "PLZ-Z01-CEN-D001-001-A",
  "puerto": 8,
  "potencia_dbm": -15.5,
  "timestamp": "2026-11-14T22:30:00.000Z"
}
```

### 6.2 Arquitectura de Integración con FastAPI (`app/api/v1/`)

El backend del proyecto ya cuenta con la estructura modular en FastAPI (`app/api/v1/auth.py`, `app/api/v1/naps.py`, `app/services/nap_service.py` y `app/models/nap.py`). Para transicionar de simulación a persistencia real en SQLite/SQLModel se seguirán cuatro pasos:

#### Paso 1: Endpoint de Ingesta en el Backend (`app/api/v1/naps.py`)
Exponer un endpoint protegido por JWT (por ejemplo, `POST /api/v1/naps/{codigo_nap}/telemetria` o `POST /api/v1/telemetria`) que reciba un esquema Pydantic/SQLModel validado:
* Verifica que `codigo_nap` exista en la tabla `naps`.
* Valida el rango de `puerto` ($1 \dots 16$) y `potencia_dbm`.
* Invoca a `nap_service.py` para clasificar el estado óptico según el estándar **ITU-T G.984** (`OPTIMO`, `ADVERTENCIA` o `CRITICO`), persiste el registro y recalcula el `estado_general` de la caja NAP.
* Retorna HTTP `201 Created` con el estado actualizado de la caja y la lectura registrada.

#### Paso 2: Autenticación mediante Token JWT desde `login.html`
Dado que `app/core/security.py` implementa autenticación basada en tokens JWT, el cliente deberá adjuntar la cabecera `Authorization: Bearer <token>` obtenida al iniciar sesión en `frontend/login.html`.

#### Paso 3: Sustitución de la Simulación por `fetch` Asíncrono en `telemetry.js`
Dentro del manejador `submit` de `frontend/assets/js/telemetry.js`, el bloque `try` reemplazará el despacho síncrono simulado por una petición HTTP asíncrona:

```javascript
// Ejemplo de integración futura con el endpoint FastAPI
const token = sessionStorage.getItem('access_token'); // Emitido por /api/v1/auth/login

const response = await fetch('/api/v1/telemetria', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  },
  body: JSON.stringify({
    codigo_nap: telemetryPayload.codigo_nap,
    puerto: telemetryPayload.puerto,
    potencia_dbm: telemetryPayload.potencia_dbm,
  }),
});

if (!response.ok) {
  const errorData = await response.json().catch(() => ({}));
  throw new Error(errorData.detail || `Error HTTP ${response.status}`);
}

const savedRecord = await response.json();
```

#### Paso 4: Manejo de Errores HTTP y Actualización Reactiva del Mapa
* **Gestión de respuestas de error:**
  * `401 Unauthorized`: Redirigir al técnico a `login.html` por sesión expirada.
  * `404 Not Found`: Mostrar un Toast de advertencia indicando que el `codigo_nap` cumple el formato sintáctico pero aún no está dado de alta en el inventario de base de datos.
  * `422 Unprocessable Entity`: Mostrar el detalle de validación devuelto por FastAPI/Pydantic.
* **Sincronización con `map.js`:** Al recibir `201 Created`, `telemetry.js` emitirá `nap:telemetry-submitted` incluyendo la respuesta del servidor (`savedRecord`), permitiendo que `map.js` actualice el color del marcador en Leaflet (`emerald`, `amber` o `rose`) y los contadores de la barra superior (`#stat-optimo`, `#stat-critico`) sin recargar la página.

---
