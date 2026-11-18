# Documentación Técnica: Formulario Interactivo de Telemetría Óptica en Campo

**Proyecto:** Sistema de Gestión y Auditoría de Cajas NAP — Municipio Plaza (Guarenas, Estado Miranda)  
**Módulo:** Frontend GIS & Ingesta de Telemetría (`frontend/`)  
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
* **Blindaje de seguridad en cliente:** Implementa protección contra inyección DOM-XSS, validación numérica estricta de señales ópticas en dBm, bloqueo contra envíos duplicados (*double-submit*) y aislamiento de eventos frente al mapa.
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
