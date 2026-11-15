import argparse
import random
import sys
import time
from typing import Dict, Any, Tuple
import requests

# Umbrales ajustados al contrato del backend (SFP Clase B+)
RANGOS_POTENCIA_DBM = {
    "optimo": (-27.0, -8.0),       # Rango nominal según el backend
    "critico": (-30.0, -27.1),     # Marcado automáticamente como CRITICO
    "caido": (-45.0, -30.1),       # Luz inexistente o degradación extrema
    "saturado": (-7.9, 2.0),       # Sobrecarga
}

def generar_potencia_dbm(modo: str) -> Tuple[float, str]:
    modo_efectivo = modo.lower()
    if modo_efectivo == "random":
        modo_efectivo = random.choice(["optimo", "critico", "caido"])

    limite_inferior, limite_superior = RANGOS_POTENCIA_DBM[modo_efectivo]
    potencia_generada = random.uniform(limite_inferior, limite_superior)
    
    return round(potencia_generada, 2), modo_efectivo

def construir_payload(puerto_id: int, potencia_rx: float, clase_sfp: str = "B+") -> Dict[str, Any]:
    # Simulamos también un valor realista para la potencia de transmisión (Upstream)
    potencia_tx = round(random.uniform(1.5, 3.5), 2)
    
    return {
        "puerto_id": puerto_id,
        "potencia_rx_1490_dbm": potencia_rx,
        "potencia_tx_1310_dbm": potencia_tx,
        "clase_sfp": clase_sfp,
        "fuente_dato": "SIMULADOR"
    }

def ejecutar_emulador(puerto: int, modo: str, ciclos: int, intervalo: int, url: str) -> None:
    print("=" * 70)
    print("🛰️  INICIANDO EMULADOR DE TELEMETRÍA GPON (CONTRATO BACKEND ACTUALIZADO)")
    print(f" • Puerto ID destino: {puerto}")
    print(f" • Modo configurado:  {modo.upper()}")
    print(f" • Endpoint destino:  {url}")
    print("=" * 70)

    for ciclo_actual in range(1, ciclos + 1):
        potencia, modo_efectivo = generar_potencia_dbm(modo)
        payload = construir_payload(puerto_id=puerto, potencia_rx=potencia)

        print(f"\n[Ciclo {ciclo_actual}/{ciclos}] Transmitiendo lectura...")
        print(f" -> Rx: {potencia} dBm | Tx: {payload['potencia_tx_1310_dbm']} dBm | Fuente: {payload['fuente_dato']}")

        try:
            inicio_transmision = time.time()
            respuesta = requests.post(url, json=payload, timeout=5.0)
            latencia_ms = round((time.time() - inicio_transmision) * 1000, 2)

            if respuesta.status_code in (200, 201):
                datos_respuesta = respuesta.json()
                diagnostico = datos_respuesta.get("diagnostico", "NO_ESPECIFICADO")
                print(f" ✔️  [HTTP {respuesta.status_code}] {latencia_ms} ms | Estado BD: {diagnostico}")
            else:
                print(f" ⚠️  Error HTTP {respuesta.status_code}: {respuesta.text}")

        except requests.exceptions.ConnectionError:
            print(f" ❌ ERROR DE CONEXIÓN: Servidor inalcanzable en '{url}'.")
            if ciclo_actual == 1 and ciclos > 1:
                sys.exit(1)
        
        if ciclo_actual < ciclos:
            time.sleep(intervalo)

def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emulador CLI de Telemetría GPON.")
    parser.add_argument("--puerto", type=int, required=True, help="ID del puerto NAP a auditar")
    parser.add_argument("--modo", type=str, choices=["optimo", "critico", "caido", "saturado", "random"], default="optimo")
    parser.add_argument("--ciclos", type=int, default=1)
    parser.add_argument("--intervalo", type=int, default=2)
    parser.add_argument("--url", type=str, default="http://127.0.0.1:8000/api/v1/naps/lecturas")
    return parser.parse_args()

if __name__ == "__main__":
    try:
        args = parsear_argumentos()
        ejecutar_emulador(args.puerto, args.modo, args.ciclos, args.intervalo, args.url)
    except KeyboardInterrupt:
        sys.exit(0)