# Manual de Usuario — Plataforma Gestión NAP (Municipio Plaza)

**Versión:** 1.0  
**Ámbito Operativo:** Red de Distribución Óptica FTTH-GPON — Guarenas, Municipio Plaza, Estado Miranda.

---

## 1. Introducción

**Gestión NAP** es una plataforma web georreferenciada (GIS) diseñada para el inventario, monitoreo de telemetría óptica y auditoría técnica de Cajas de Acceso Terminal (NAP) en planta externa. Permite a técnicos de campo y supervisores de red visualizar el estado de salud óptica en tiempo real, registrar mediciones de potencia y detectar degradaciones de señal conforme a la norma internacional **ITU-T G.984.2**.

---

## 2. Acceso al Sistema e Inicio de Sesión

Todas las vistas operativas están protegidas mediante autenticación por token JWT.

1. Abra su navegador web e ingrese a `login.html` (por ejemplo: `http://localhost:8080/login.html`).
2. Introduzca su **Usuario o Correo Institucional** y su **Contraseña**.
   * *Perfil Operador de Campo:* `operador@gestionnap.ve` / `plaza2026` (consulta de mapa, dashboard y registro de telemetría).
   * *Perfil Administrador:* `admin` / `admin123` (incluye permisos de alta de nuevas cajas NAP).
3. Pulse **Ingresar al Sistema**.
4. **Cierre de Sesión:** Cuando finalice su turno, pulse el botón **Salir** en la esquina superior derecha para invalidar la sesión local en el navegador.

> **Nota de seguridad:** Si intenta acceder directamente a `index.html` o `dashboard.html` sin iniciar sesión, o si su token expira, el sistema lo redirigirá automáticamente a la pantalla de inicio de sesión.

---

## 3. Mapa Operativo GIS (`index.html`)

Al ingresar, visualizará el mapa interactivo centrado en el **Municipio Plaza (Guarenas)**:

* **Barra Superior:**
  * **Navegación:** Permite alternar entre **Mapa GIS**, **Dashboard**, abrir rápidamente la **Auditoría NAP** o cerrar sesión (**Salir**).
  * **Indicadores Resumen:** Muestran el conteo en tiempo real de *Total Cajas*, cajas en estado *Óptimo* y cajas en estado *Crítico*.
* **Leyenda Flotante (inferior izquierda):**
  * **Verde (`ÓPTIMO`):** Todos los puertos activos operan dentro de los umbrales nominales de potencia óptica.
  * **Ámbar (`ADVERTENCIA`):** La caja se encuentra en mantenimiento preventivo o presenta atenuación leve.
  * **Rojo con pulso animado (`CRÍTICO`):** Al menos un puerto presenta atenuación crítica, caída de señal (`CAIDO`) o daño físico en la caja.
* **Inspección de una Caja NAP:**
  * Haga clic sobre cualquier marcador en el mapa para desplegar su tarjeta resumen con código identificador, estado físico, zona/sector, capacidad de puertos y dirección de referencia.
  * Pulse **Ver Detalles** dentro de la tarjeta para abrir el panel de auditoría técnica de esa caja.

---

## 4. Registro de Potencia Óptica en Campo

En la esquina superior derecha del mapa se encuentra el panel flotante **Registro de Potencia Óptica** (puede minimizarse pulsando la flecha en su cabecera).

### Pasos para registrar una lectura:
1. **Código NAP:** Escriba el código normalizado de la caja siguiendo estrictamente el formato territorial del Municipio Plaza:
   $$\text{PLZ-Z0}[1\text{-}8]\text{-[SECTOR]-D000-000-[A|F|S]}$$
   * Ejemplo válido: `PLZ-Z04-NCA-D001-012-A`
   * El borde del campo se tornará **verde** cuando el código sea válido o **rojo** si incumple el formato.
2. **Puerto:** Seleccione el puerto físico evaluado (del `1` al `16`).
3. **Potencia (dBm):** Ingrese la potencia óptica downstream medida a $1490\text{ nm}$ (rango permitido: $-50.00\text{ dBm}$ a $+5.00\text{ dBm}$, hasta 2 decimales).
4. Pulse **Registrar Lectura**.

### Criterios de Evaluación Automática (ITU-T G.984.2 — SFP Clase B+):
* **OPTIMO:** Potencia entre $-24.00\text{ dBm}$ y $-8.00\text{ dBm}$.
* **CRITICO:** Potencia entre $-27.00\text{ dBm}$ y $-24.01\text{ dBm}$.
* **CAIDO:** Potencia inferior a $-27.00\text{ dBm}$ (pérdida de enlace) o superior a $-8.00\text{ dBm}$ (saturación del receptor).

Al confirmar el registro, aparecerá una notificación en la esquina inferior derecha con el dictamen calculado y el marcador en el mapa actualizará su color automáticamente.

---

## 5. Auditoría Técnica de Cajas NAP

Al pulsar **Ver Detalles** en cualquier marcador del mapa se despliega el modal de auditoría técnica:

* **Identificación Óptica TIA/EIA-598:** Muestra la relación del *splitter* pasivo (`1:8` o `1:16`), el color del tubo búfer y el color del hilo de fibra fusionado.
* **Gráfico de Distribución:** Visualiza porcentualmente los puertos *Ocupados*, *Libres* y en *Estado Crítico*.
* **Panel de Alertas:** Lista los puertos con atenuación alta o caída óptica junto al código del suscriptor afectado.
* **Tira de Puertos (`P1` a `PN`):** Muestra puerto por puerto su estado operativo y la última potencia registrada en $\text{dBm}$.

---

## 6. Dashboard Ejecutivo FTTH y Alertas (`dashboard.html`)

La vista de **Dashboard** ofrece una panorámica consolidada de toda la red:

* **Tarjetas KPI:** Total de Cajas NAP instaladas, Total de Puertos, Puertos Conectados (%) y Puertos Dañados (%).
* **Estado de Puertos (Gráfico de Dona):** Distribución entre puertos conectados, disponibles, reservados y dañados.
* **Salud Óptica (Barras Horizontales):** Comparativa de puertos activos clasificados en Óptimo, Crítico y Caído.
* **Tabla de Alertas Recientes:** Listado priorizado de incidencias activas con nivel de severidad, código NAP, número de puerto y motivo técnico.

---

## 7. Uso del Emulador CLI de Telemetría (Pruebas en Laboratorio)

Para simular ráfagas de telemetría óptica desde terminal sin hardware OLT conectado, utilice el script `emulador_telemetria.py` con el entorno virtual activo:

```bash
python3 emulador_telemetria.py --puerto 2 --modo critico --ciclos 3 --intervalo 2
```

* `--puerto`: ID primario del puerto en la base de datos SQLite.
* `--modo`: `optimo`, `critico`, `caido`, `saturado` o `random`.
* `--ciclos`: Cantidad de lecturas a transmitir.
* `--intervalo`: Segundos de espera entre cada lectura.