# Emulador de Telemetría GPON (Script CLI)
**Proyecto:** Plataforma Digital para la Gestión Técnica y Auditoría de Conectividad (NAPs)  
**Módulo:** Ingesta de Datos y Pruebas Autenticadas  

---

## 1. Propósito y Justificación Académica
El **Emulador de Telemetría GPON** (`emulador_telemetria.py`) es una herramienta de interfaz de línea de comandos (CLI) desarrollada en Python. Su propósito es simular el tráfico en tiempo real proveniente de equipos de red físicos (OLTs) o medidores de potencia óptica (OPMs).

Dado que en un entorno universitario no se dispone de infraestructura OLT física conectada a la red de Guarenas, este script actúa como el **generador de eventos (mock en producción)**. Permite:
1. Validar la lógica de negocio del Backend (cálculo de atenuación y estado ITU-T G.984.2).
2. Actualizar dinámicamente el Frontend (cambio de colores de los pines en el mapa interactivo y métricas del dashboard).
3. Demostrar la robustez del sistema en tiempo real durante la defensa académica.

---

## 2. Contrato de Interfaz y Autenticación JWT
El emulador está acoplado al esquema DTO definido en `app/models/nap.py` (`LecturaPotenciaCreate`) y opera autenticado contra la API protegida:

1. **Obtención de Token:** Antes de inyectar lecturas, el script se autentica contra `POST /api/v1/auth/login` (por defecto con credenciales de operador o mediante parámetros/variables de entorno) para obtener un token **JWT (HS256)**.
2. **Endpoint Destino:** `POST /api/v1/naps/lecturas`
3. **Headers:**
   * `Content-Type: application/json`
   * `Authorization: Bearer <JWT_TOKEN>`

**Estructura del JSON Inyectado:**
```json
{
  "puerto_id": 1,
  "potencia_rx_1490_dbm": -19.45,
  "potencia_tx_1310_dbm": 2.10,
  "clase_sfp": "B+",
  "fuente_dato": "SIMULADOR"
}
```

---

## 3. Umbrales Ópticos (Norma ITU-T G.984.2 — SFP Clase B+)
La generación de datos respeta estrictamente la matriz de clasificación implementada en `app/services/nap_service.py`:

| Modo CLI | Rango Rx (dBm) generado | Estado resultante en BD (`EstadoPotencia`) | Condición Simulada |
| :--- | :--- | :--- | :--- |
| `--modo optimo` | `-8.0` a `-24.0` | **`OPTIMO`** | Operación nominal, dentro del margen operativo. |
| `--modo critico` | `-24.1` a `-27.0` | **`CRITICO`** | Degradación preventiva (empalmes sucios, macrocurvaturas). |
| `--modo caido` | `< -27.0` | **`CAIDO`** | Corte de fibra o pérdida de señal (LOS). |
| `--modo saturado` | `> -8.0` | **`CAIDO`** | Exceso de potencia óptica (saturación del fotodiodo receptor). |

> **Nota:** En el modelo de datos solo existen tres estados de potencia (`OPTIMO`, `CRITICO` y `CAIDO`). El modo `--modo saturado` simula una potencia por encima de `-8.0 dBm`, la cual el backend clasifica correctamente como **`CAIDO`** por riesgo de saturación óptica.

---

## 4. Instrucciones de Uso (CLI)

### Dependencias
El script utiliza la librería `requests` incluida en `requirements.txt`:
```bash
pip install requests
```

### Argumentos del Comando
```text
uso: emulador_telemetria.py [-h] --puerto PUERTO [--modo {optimo,critico,caido,saturado,random}] [--ciclos CICLOS] [--intervalo INTERVALO] [--url URL]

Argumentos requeridos:
  --puerto PUERTO       ID del puerto NAP a auditar (Ej. 1)

Argumentos opcionales:
  --modo                Estado a simular (default: optimo)
  --ciclos              Número de envíos consecutivos (default: 1)
  --intervalo           Segundos de espera entre envíos (default: 2)
  --url                 URL del endpoint (default: [http://127.0.0.1:8000/api/v1/naps/lecturas](http://127.0.0.1:8000/api/v1/naps/lecturas))
```

### Ejemplos de Ejecución para la Defensa del Proyecto

1. **Simular un puerto operando de forma ideal (un solo disparo):**
   ```bash
   python emulador_telemetria.py --puerto 1 --modo optimo
   ```

2. **Simular vandalismo o corte de fibra (cambia el pin a rojo en el mapa):**
   ```bash
   python emulador_telemetria.py --puerto 1 --modo caido
   ```

3. **Simular tráfico de red en segundo plano (piloto automático):**
   Envía una lectura aleatoria al puerto 1 cada 4 segundos, 100 veces.
   ```bash
   python emulador_telemetria.py --puerto 1 --modo random --ciclos 100 --intervalo 4
   ```