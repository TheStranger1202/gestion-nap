# Emulador de Telemetría GPON (Script CLI)
**Proyecto:** Plataforma Digital para la Gestión Técnica y Auditoría de Conectividad (NAPs)  
**Módulo:** Ingesta de Datos y Pruebas Desacopladas  

---

## 1. Propósito y Justificación Académica
El **Emulador de Telemetría GPON** (`emulador_telemetria.py`) es una herramienta de interfaz de línea de comandos (CLI) desarrollada en Python. Su propósito es simular el tráfico en tiempo real proveniente de equipos de red físicos (OLTs) o medidores de potencia óptica (OPMs).

Dado que en un entorno universitario no se dispone de infraestructura OLT física conectada a la red de Guarenas, este script actúa como el **generador de eventos (mock en producción)**. Permite:
1. Validar la lógica de negocio del Backend (cálculo de atenuación y estado).
2. Dar vida al Frontend (cambio de colores de los pines en el mapa interactivo).
3. Demostrar la robustez del sistema en tiempo real durante la defensa académica.

---

## 2. Contrato de Interfaz (API Payload)
El emulador está estrictamente acoplado al esquema DTO definido por el equipo de Base de Datos (`LecturaPotenciaCreate`). 

* **Endpoint Destino:** `POST /api/v1/naps/lecturas`
* **Headers:** `Content-Type: application/json`

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

## 3. Umbrales Ópticos (Norma ITU-T G.984)
La generación de datos respeta la lógica de atenuación acordada en el backend para SFP Clase B+:

| Modo CLI | Rango Rx (dBm) generado | Estado resultante en BD | Condición Simulada |
| :--- | :--- | :--- | :--- |
| `--modo optimo` | `-8.0` a `-27.0` | **ÓPTIMO** | Operación nominal, sin fallas. |
| `--modo critico`| `-27.1` a `-30.0` | **CRÍTICO** | Degradación (empalmes sucios, curvaturas). |
| `--modo caido`  | `< -30.1` | **CAÍDO** | Corte de fibra o pérdida de señal (LOS). |
| `--modo saturado`| `> -8.0` | **SATURADO**| Exceso de potencia óptica. |

---

## 4. Instrucciones de Uso (CLI)

### Dependencias
El script solo requiere la librería `requests` estándar del entorno virtual:
```bash
pip install requests
```

### Argumentos del Comando
```text
uso: emulador_telemetria.py [-h] --puerto PUERTO [--modo {optimo,critico,caido,saturado,random}] [--ciclos CICLOS] [--intervalo INTERVALO] [--url URL]

Argumentos requeridos:
  --puerto PUERTO       ID del puerto NAP a auditar (Ej. 10)

Argumentos opcionales:
  --modo                Estado a simular (default: optimo)
  --ciclos              Número de envíos consecutivos (default: 1)
  --intervalo           Segundos de espera entre envíos (default: 2)
  --url                 URL del endpoint (default: http://127.0.0.1:8000/api/v1/naps/lecturas)
```

### Ejemplos de Ejecución para la Defensa del Proyecto

1. **Simular un puerto operando de forma ideal (un solo disparo):**
   ```bash
   python emulador_telemetria.py --puerto 5 --modo optimo
   ```

2. **Simular vandalismo o corte de fibra (cambio a rojo en el mapa):**
   ```bash
   python emulador_telemetria.py --puerto 12 --modo caido
   ```

3. **Simular tráfico de red en segundo plano (piloto automático):**
   Envía una lectura aleatoria al puerto 8 cada 4 segundos, 100 veces.
   ```bash
   python emulador_telemetria.py --puerto 8 --modo random --ciclos 100 --intervalo 4
   ```

---

## 5. Entorno de Pruebas (Mock API)
Para probar modificaciones en el emulador sin necesidad de encender el servidor de Base de Datos, se incluye el archivo `mock_api_pruebas.py`.

**Para usarlo:**
1. Abre una terminal y ejecuta: `python mock_api_pruebas.py`
2. Abre otra terminal y dispara el emulador. La Mock API procesará el JSON y devolverá el cálculo exacto que haría la base de datos real.