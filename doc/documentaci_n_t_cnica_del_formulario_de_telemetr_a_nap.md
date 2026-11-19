# Documentación Técnica: Formulario Interactivo de Telemetría Óptica en Campo

**Proyecto:** Sistema de Gestión y Auditoría de Cajas NAP — Municipio Plaza (Guarenas, Estado Miranda)  
**Módulo:** Frontend GIS e Ingesta de Telemetría (`frontend/`)  
**Artefactos cubiertos:** `frontend/index.html`, `frontend/assets/js/telemetry.js`, `frontend/assets/js/api.js`, `tests/test_frontend_telemetry.py`  
**Estándar de trazabilidad:** ISO/IEC/IEEE 12207 · Conventional Commits v1.0.0

---

## 1. Filosofía de Ingeniería: *"Si no está documentado, no existe"*

Alineado con los principios de trazabilidad de la norma **ISO/IEC/IEEE 12207**, este documento establece la línea base oficial del módulo de captura de telemetría en campo. Su propósito es garantizar la mantenibilidad técnica, documentar los controles de seguridad en cliente y respaldar la arquitectura de integración con el backend FastAPI ante evaluaciones técnicas.

---

## 2. Resumen Ejecutivo y Alcance del Módulo

El formulario interactivo de registro de potencia óptica permite a los técnicos de planta externa registrar lecturas de telemetría GPON directamente sobre el mapa operativo GIS del Municipio Plaza, persistiendo los datos en SQLite vía API REST sin abandonar el contexto geográfico ni recargar la aplicación.

### Objetivos cumplidos
* **Integración no intrusiva:** Tarjeta flotante colapsable sobre el lienzo `Leaflet.js` en `frontend/index.html`.
* **Validación territorial en tiempo real:** Verifica la sintaxis oficial del Municipio Plaza mediante expresión regular, ofreciendo retroalimentación visual inmediata (borde verde o rojo) y validación cruzada de Zonas Operativas de Distribución (ZOD).
* **Blindaje de seguridad en cliente:** Protección contra DOM-XSS, validación numérica estricta de señales ópticas en $\text{dBm}$, bloqueo contra envíos duplicados (*double-submit*) y aislamiento de eventos frente al mapa.
* **Ingesta autenticada con FastAPI:** Envío asíncrono mediante `api.js` con token JWT y actualización reactiva de marcadores y contadores del mapa mediante el evento personalizado `nap:telemetry-submitted`.

---

## 3. Arquitectura y Diseño del Sistema

### 3.1 Estructura de Archivos Involucrados

```text
gestion-nap/
├── doc/
│   └── documentaci_n_t_cnica_del_formulario_de_telemetr_a_nap.md
├── frontend/
│   ├── index.html                               # Vista principal GIS + Tarjeta flotante y contenedor Toast
│   └── assets/
│       └── js/
│           ├── api.js                           # Cliente HTTP centralizado y guardia JWT
│           ├── components.js                    # Pines SVG y popups sanitizados
│           ├── map.js                           # Controlador Leaflet.js conectado a FastAPI
│           └── telemetry.js                     # Validación, seguridad e ingesta de telemetría
└── tests/
    ├── test_frontend_map.py                     # Pruebas E2E del mapa y sesión JWT
    └── test_frontend_telemetry.py               # Pruebas E2E del formulario de telemetría
```

### 3.2 Jerarquía Visual, Responsividad y Capas (`z-index`)

| Capa / Elemento | Selector / ID | Clase `z-index` | Posición y Comportamiento Responsivo |
| :--- | :--- | :---: | :--- |
| **Lienzo Cartográfico** | `#map` | `z-10` | Ocupa el $100\%$ del área disponible debajo del `<header>`. |
| **Barra Superior** | `<header>` | `z-20` | Fija en la parte superior (`h-16`) con indicadores globales. |
| **Leyenda GIS** | `<aside>` | `z-[1000]` | Esquina inferior izquierda (`bottom-6 left-4`). |
| **Panel de Telemetría** | `#telemetry-panel` | `z-[1000]` | Esquina superior derecha (`top-4 right-4`). En móviles ocupa `w-[calc(100vw-2rem)]` y en pantallas `sm:` o superiores `sm:w-96`, con botón colapsable (`#telemetry-toggle-btn`). |
| **Notificación Toast** | `#telemetry-toast-container` | `z-[1100]` | Esquina inferior derecha (`bottom-6 right-4`), con `pointer-events-none` en el contenedor. |

### 3.3 Flujo de Datos (Cliente $\rightarrow$ API REST $\rightarrow$ Mapa)

```text
+-------------------------------------------------------------------+
|                   Usuario / Técnico en Campo                      |
+---------------------------------+---------------------------------+
                                  |
             1. Ingresa Código NAP, Puerto (1-16) y Potencia (dBm)
                                  v
+-------------------------------------------------------------------+
|           frontend/assets/js/telemetry.js (IIFE 'use strict')     |
|  - Valida regex ^PLZ-Z0[1-8]-[A-Z]{3}-D\d{3}-\d{3}-[AFS]$          |
|  - Valida rango entero de puerto [1..16] y potencia [-50..+5] dBm |
+---------------------------------+---------------------------------+
                                  |
             2. Petición autenticada via api.js (Bearer JWT)
                                  v
+-------------------------------------------------------------------+
|       FastAPI: POST /api/v1/naps/lecturas (nap_service.py)        |
|  - Evalúa ITU-T G.984.2 (OPTIMO / CRITICO / CAIDO)                |
|  - Persiste en SQLite y devuelve HTTP 201 Created                 |
+----------------+---------------------------------+----------------+
                 |                                 |
   3a. Limpia UI y muestra Toast     3b. Despacha CustomEvent
                 v                                 v
+---------------------------------+ +-------------------------------+
|  #telemetry-toast-container     | | Evento 'nap:telemetry-submitted'
|  (Nodos DOM seguros via         | | -> map.js refresca pines y    |
|   createElement + textContent)  | |    contadores sin recargar    |
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
  * **Estado inicial / limpio (`pristine`):** Borde neutro `border-slate-300`.
  * **Estado inválido (`INVALID`):** Borde rojo `border-rose-500 ring-2 ring-rose-500/20` y `aria-invalid="true"`.
  * **Estado válido (`VALID`):** Borde verde `border-emerald-500 ring-2 ring-emerald-500/20` y `aria-invalid="false"`, validando además el acrónimo del sector contra el catálogo inmutable `ZOD_SECTORS` (`Z01`–`Z08`).

### 4.2 Controles de Seguridad Frontend (*Hardening*)

1. **Prevención de DOM-Based XSS:** Las notificaciones Toast y los mensajes de validación construyen nodos exclusivamente con `document.createElement` y `textContent`, evitando `innerHTML`.
2. **Validación en Doble Capa (HTML5 + JavaScript):** `telemetry.js` ejecuta su propia validación con reglas selladas mediante `Object.freeze()`, independientemente de los atributos HTML5.
3. **Encapsulamiento de Ámbito:** El módulo se ejecuta dentro de una IIFE en modo estricto (`(() => { 'use strict'; ... })()`).
4. **Protección contra Envíos Duplicados:** Una bandera `isSubmitting` deshabilita temporalmente `#telemetry-submit-btn` mientras se resuelve la petición HTTP.
5. **Validación Numérica Estricta ($\text{dBm}$):** Evalúa `powerInput.validity.badInput`, `Number.isFinite()`, patrón `/^-?\d+(\.\d{1,2})?$/` y rango físico GPON $[-50.00, +5.00]\text{ dBm}$.
6. **Aislamiento frente a Leaflet.js:** `L.DomEvent.disableClickPropagation` y `L.DomEvent.disableScrollPropagation` evitan que interactuar con el formulario mueva o haga zoom sobre el mapa.

### 4.3 Matriz de Casos Borde (*Edge Cases*) Contemplados

| Escenario / Caso Borde | Comportamiento del Sistema | Mecanismo Implementado |
| :--- | :--- | :--- |
| Formulario recién cargado o recién enviado | No muestra borde rojo en el Código NAP vacío | Bandera `isNapDirty` + `resetFormState()` |
| Código con zona fuera de rango (`PLZ-Z09-...`) o montaje inválido (`...-X`) | Marca borde rojo inmediato y bloquea envío | `NAP_CODE_REGEX.test(value)` en evento `input` |
| Manipulación del `<select>` desde DevTools (`value="99"` o `"1.5"`) | Rechaza el envío y enfoca el selector | `Number.isInteger(port) && port >= 1 && port <= 16` |
| Entrada numérica incompleta (`"-"` o `"15..2"`) en potencia | Detecta entrada mal formada sin fallar silenciosamente | Inspección de `powerInput.validity.badInput` |
| Sesión JWT expirada (`401 Unauthorized`) | Redirige automáticamente a `login.html` | Guardia centralizada en `api.js` |
| Código NAP válido en formato pero inexistente en BD (`404 Not Found`) | Muestra notificación Toast de advertencia | Manejo de respuesta HTTP en `telemetry.js` |

---

## 5. Integración con FastAPI y Gestión de Errores

El envío de telemetría se realiza de forma autenticada reutilizando el token almacenado en `localStorage` (`access_token`) a través del cliente centralizado `frontend/assets/js/api.js`:

* **`201 Created`:** El backend clasifica la lectura según **ITU-T G.984.2** (`OPTIMO`, `CRITICO` o `CAIDO`), persiste el registro y devuelve el diagnóstico. `telemetry.js` muestra el Toast de confirmación y despacha `nap:telemetry-submitted` para que `map.js` actualice los marcadores (`OPTIMO`, `ADVERTENCIA`, `CRITICO`) y los contadores de la barra superior.
* **`401 Unauthorized`:** Redirección inmediata a `login.html`.
* **`404 Not Found` / `422 Unprocessable Entity`:** Despliegue del mensaje de error retornado por FastAPI en un Toast sin perder el contexto del mapa.