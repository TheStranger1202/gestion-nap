# Documentación Técnica: Servicio de Ingesta de Telemetría Óptica y Aprovisionamiento de Puertos NAP

**Proyecto:** Sistema de Gestión de Cajas NAP (Red FTTH-GPON — Municipio Plaza)  
**Módulo Documentado:** `app/services/nap_service.py` y `tests/test_naps.py`  
**Dependencias de Dominio:** `app/models/nap.py` (SQLModel / Pydantic)  
**Normativa Técnica Aplicada:** Recomendación **ITU-T G.984.2** (Gigabit-capable Passive Optical Networks)

---

## 1. Principio de Ingeniería: *"Si no está documentado, no existe"*

En ingeniería de software y telecomunicaciones, el código fuente por sí solo expresa **cómo** se ejecuta una instrucción, pero únicamente la documentación técnica preserva **por qué** se tomó una decisión de diseño, **qué** restricciones físicas o normativas gobiernan los umbrales y **cómo** se verifica que el sistema no falle ante escenarios límite.

Aplicar la máxima *"si no está documentado, no existe"* en este proyecto cumple cuatro objetivos críticos:

1. **Trazabilidad y Auditoría:** Permite demostrar ante cualquier evaluación técnica o académica que los umbrales de potencia óptica no son números arbitrarios, sino parámetros derivados de estándares internacionales (ITU-T G.984.2).
2. **Mantenibilidad Evolutiva:** Facilita que cualquier desarrollador futuro integre nuevos orígenes de datos (como colectores SNMP reales de cabeceras OLT) sin alterar las reglas de negocio ya validadas.
3. **Resiliencia Operativa:** Documenta los mecanismos de protección transaccional (`flush`, `commit`, `rollback`) y sanitización de datos que evitan corrupción en la base de datos SQLite.

---

## 2. Arquitectura y Diseño del Módulo

### 2.1 Patrón Capa de Servicios (*Service Layer*)

El sistema **Gestión NAP** implementa una arquitectura en capas estrictamente desacopladas:

```text
+-------------------------------------------------------------------+
|  Capa de Presentación / API REST (app/api/v1/naps.py)             |
|  - Recibe peticiones HTTP, valida JWT/Roles y traduce errores     |
+---------------------------------+---------------------------------+
                                  | Invoca funciones de negocio
                                  v
+-------------------------------------------------------------------+
|  Capa de Servicios de Dominio (app/services/nap_service.py)       |
|  - Evalúa umbrales ópticos ITU-T G.984.2                          |
|  - Garantiza ingesta agnóstica a la fuente del dato               |
|  - Orquesta transacciones atómicas NAP + Puertos                  |
+---------------------------------+---------------------------------+
                                  | Usa esquemas y entidades
                                  v
+-------------------------------------------------------------------+
|  Capa de Persistencia y Modelos (app/models/nap.py + SQLite)      |
|  - Validación Pydantic, integridad referencial y ORM SQLModel     |
+-------------------------------------------------------------------+
```

#### ¿Por qué desacoplar la lógica de negocio de FastAPI?
* **Reutilización Multi-Origen:** La evaluación óptica puede ser invocada desde un endpoint HTTP (captura manual de un técnico), desde un simulador de red o desde un proceso en segundo plano (*worker* SNMP) sin depender de objetos `Request` o `HTTPException`.
* **Testabilidad Pura:** Permite ejecutar pruebas unitarias e integración directamente sobre funciones Python con sesiones SQLite en memoria en milisegundos, sin levantar un servidor web.
* **Excepciones de Dominio:** El servicio define su propia jerarquía de errores (`NAPServiceError`, `NAPDuplicadaError`, `NAPNoEncontradaError`, `PuertoNoEncontradoError`), dejando a la capa HTTP la responsabilidad de mapearlas a códigos de estado (`404 Not Found`, `409 Conflict`, `422 Unprocessable Entity`).

---

## 3. Fundamento Óptico FTTH-GPON y Matriz de Evaluación

### 3.1 Física del Enlace Óptico GPON

En una red pasiva **FTTH-GPON** (*Fiber To The Home - Gigabit Passive Optical Network*), la señal óptica viaja desde el transceptor **SFP** de la cabecera **OLT** (*Optical Line Terminal*), atraviesa la fibra troncal y de distribución, pasa por un divisor óptico pasivo (**Splitter PLC** de relación $1:8$ o $1:16$) alojado dentro de la **Caja NAP**, y llega hasta la **ONT** (*Optical Network Terminal*) del suscriptor:

* **Canal Downstream (OLT $\rightarrow$ ONT):** Opera en la longitud de onda $\lambda = 1490\text{ nm}$. Es la potencia medida en `potencia_rx_1490_dbm`.
* **Canal Upstream (ONT $\rightarrow$ OLT):** Opera en $\lambda = 1310\text{ nm}$ (`potencia_tx_1310_dbm`).

### 3.2 Matriz de Clasificación ITU-T G.984.2

La norma **ITU-T G.984.2** establece distintas clases de módulos ópticos según su presupuesto de potencia (*Optical Budget*):
* **Clase B+:** Presupuesto óptico nominal de $28\text{ dB}$ (estándar más desplegado en planta externa).
* **Clase C+:** Presupuesto óptico extendido de $32\text{ dB}$ (mayor sensibilidad de recepción para enlaces de larga distancia o mayor relación de división).

Para cubrir de forma continua todo el dominio físico permitido por el esquema `LecturaPotenciaCreate` ($[-50.0\text{ dBm}, +10.0\text{ dBm}]$) sin dejar zonas indefinidas, `evaluar_salud_optica()` aplica la siguiente partición matemática:

| Clase SFP | Saturación (`CAIDO`) | Rango Saludable (`OPTIMO`) | Degradación / Margen Bajo (`CRITICO`) | Pérdida de Señal / Falla (`CAIDO`) |
| :--- | :--- | :--- | :--- | :--- |
| **Clase B+** | $P_{rx} > -8.0\text{ dBm}$ | $-24.0 \le P_{rx} \le -8.0\text{ dBm}$ | $-27.0 \le P_{rx} < -24.0\text{ dBm}$ | $P_{rx} < -27.0\text{ dBm}$ |
| **Clase C+** | $P_{rx} > -8.0\text{ dBm}$ | $-26.0 \le P_{rx} \le -8.0\text{ dBm}$ | $-29.0 \le P_{rx} < -26.0\text{ dBm}$ | $P_{rx} < -29.0\text{ dBm}$ |

#### Justificación Técnica de Cada Estado (`EstadoPotencia`)
1. **`OPTIMO`:** La señal recibida se encuentra dentro de la ventana operativa recomendada. El enlace tiene margen de potencia suficiente para absorber variaciones térmicas o envejecimiento de empalmes.
2. **`CRITICO`:** Zona preventiva de advertencia. Aunque la ONT mantiene sincronismo con la OLT, la atenuación excede el límite nominal (causada típicamente por conectores SC/APC sucios, macrocurvaturas en la acometida o empalmes defectuosos). Permite programar mantenimiento preventivo antes de que el cliente pierda servicio.
3. **`CAIDO`:** Se activa bajo dos condiciones físicas opuestas pero igualmente destructivas para la comunicación:
   * **Por debajo de sensibilidad mínima ($P_{rx} < -27.0\text{ dBm}$ en B+ o $P_{rx} < -29.0\text{ dBm}$ en C+):** El receptor óptico no logra discriminar los bits frente al ruido térmico (corte de fibra o atenuación severa).
   * **Por saturación óptica ($P_{rx} > -8.0\text{ dBm}$):** Una potencia excesivamente alta (por ejemplo, conectar una ONT sin atenuador muy cerca de la OLT) satura o daña irreversiblemente el fotodiodo receptor (APD/PIN).

### 3.3 Ingesta Independiente del Origen del Dato (`FuenteDato`)

La función `registrar_lectura_potencia()` recibe un objeto `LecturaPotenciaCreate` que incluye el atributo `fuente_dato` (`MANUAL`, `SIMULADOR` o `SNMP_OLT`). El servicio aplica **exactamente la misma función pura `evaluar_salud_optica()`** sin bifurcaciones condicionales por fuente. Esto garantiza consistencia absoluta en el diagnóstico histórico (`estado_calculado`) sin importar qué subsistema originó la telemetría.

---

## 4. Aprovisionamiento Atómico de Puertos Ópticos

Cuando se da de alta una nueva Caja NAP mediante `crear_nap_con_puertos()`, el sistema debe garantizar que la entidad física (`NAP`) y sus salidas ópticas (`Puerto`, de $1$ a $8$ o de $1$ a $16$ según `capacidad_puertos`) se creen como una **unidad indivisible (atómica)**.

### Flujo Transaccional en SQLModel / SQLite

```text
[Validación Pydantic NAPCreate]
       |
       v
[Verificar unicidad de codigo_nap] ---> Si existe -> Lanza NAPDuplicadaError
       |
       v
[session.add(db_nap)]
       |
       v
[session.flush()]  <-- Envía INSERT a SQLite y obtiene db_nap.id SIN confirmar
       |
       v
[Generar N instancias Puerto(nap_id=db_nap.id, numero_puerto=1..N, conector="SC/APC")]
       |
       v
[session.add_all(puertos_generados)]
       |
       +---> Si ocurre error -> [session.rollback()] (Cero registros huérfanos)
       |
       v
[session.commit()] <-- Confirma NAP + N Puertos en una sola transacción ACID
```

#### ¿Por qué usar `session.flush()` antes de `session.commit()`?
Si se ejecutara `commit()` inmediatamente después de guardar la `NAP` y luego fallara la creación de los puertos, quedaría registrada en inventario una caja NAP sin puertos físicos asociados, violando las reglas del dominio. Al usar `flush()`, SQLite asigna la clave primaria autoincremental `db_nap.id` dentro de la transacción abierta, permitiendo vincular todos los puertos mediante clave foránea y confirmar todo junto en un único `commit()` final.

---

## 5. Auditoría de Seguridad y Programación Defensiva

Durante la implementación de `app/services/nap_service.py` se aplicaron controles alineados con **OWASP / CWE**:

* **Prevención de Inyección SQL (`CWE-89`):** Todas las consultas emplean expresiones tipadas de SQLModel (`select(NAP).where(...)` y `session.get(...)`), parametrizadas automáticamente por el motor SQLAlchemy.
* **Sanitización de Flotantes IEEE 754 (`CWE-20`):** En Python, las comparaciones con `float("nan")` siempre devuelven `False`. Sin una guarda explícita, un valor corrupto `NaN` proveniente de una lectura SNMP habría evadido las condiciones `> -8.0` y `< -27.0`, clasificándose erróneamente. La validación `math.isfinite(potencia_rx_1490_dbm)` bloquea valores `NaN`, $+\infty$ y $-\infty$ lanzando `ValueError`.
* **Integridad Referencial Explícita en SQLite (`CWE-664`):** Dado que SQLite desactiva la comprobación de claves foráneas por defecto si no se ejecuta `PRAGMA foreign_keys = ON` en cada conexión, `registrar_lectura_potencia()` verifica explícitamente la existencia del `Puerto` destino antes de insertar la lectura, lanzando `PuertoNoEncontradoError` si `puerto_id` no existe.
* **Mitigación de Condiciones de Carrera TOCTOU (`CWE-362`):** Ante dos solicitudes simultáneas con el mismo `codigo_nap`, el bloque `try/except IntegrityError` captura la violación de restricción `UNIQUE` a nivel de motor de base de datos, revierte la transacción (`rollback`) y transforma el error técnico en una excepción controlada `NAPDuplicadaError`.

---

## 6. Guía Paso a Paso de Ejecución de la Actividad

A continuación se documenta la secuencia metodológica seguida para construir y validar esta actividad:

1. **Inspección del Contrato de Datos (`app/models/nap.py`):**
   Se revisaron las definiciones estrictas de `NAPCreate`, `Puerto`, `LecturaPotencia`, `LecturaPotenciaCreate` y las enumeraciones `ClaseSFP`, `EstadoPotencia`, `EstadoPuerto` y `FuenteDato` para evitar duplicación de esquemas.
2. **Diseño Técnico y Análisis de Casos Límite (*Edge Cases*):**
   Antes de escribir código, se validaron tres escenarios críticos:
   * Fronteras inclusivas/exclusivas exactas ($-8.0\text{ dBm}$ óptimo vs. $-7.99\text{ dBm}$ saturación; $-24.0\text{ dBm}$ óptimo vs. $-24.01\text{ dBm}$ crítico; $-27.0\text{ dBm}$ crítico vs. $-27.01\text{ dBm}$ caído).
   * Atomicidad transaccional al crear cajas de $8$ y $16$ puertos.
   * Rechazo de lecturas sobre puertos inexistentes.
3. **Implementación de la Lógica de Negocio (`app/services/nap_service.py`):**
   Se codificaron las funciones `evaluar_salud_optica`, `registrar_lectura_potencia`, `crear_nap_con_puertos`, `obtener_nap_por_id` y `listar_puertos_por_nap` con tipado estricto (*Type Hints*) y *docstrings* en español.
4. **Auditoría de Seguridad del Código:**
   Se verificaron vectores de inyección, valores numéricos no finitos, atomicidad y control de fuga de trazas internas de SQLAlchemy.
5. **Desarrollo y Ejecución de Pruebas Automatizadas (`tests/test_naps.py`):**
   Se implementaron pruebas parametrizadas con `pytest` cubriendo todos los umbrales de Clase B+ y C+, valores IEEE 754 inválidos, ingesta desde `MANUAL`, `SIMULADOR` y `SNMP_OLT`, creación de $8$ y $16$ puertos, duplicidad de código NAP y simulación de fallo con `unittest.mock.patch` para comprobar el `rollback()`. Resultado: **42 pruebas aprobadas (`42 passed in 1.10s`)**.
6. **Versionamiento bajo *Conventional Commits*:**
   Se registraron los cambios en Git siguiendo la guía `estandar_de_commits.md`.

---
