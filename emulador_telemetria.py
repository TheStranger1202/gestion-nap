import argparse
import random
import sys
import time
from typing import Any, Dict, Tuple

import requests

# Umbrales alineados con app/services/nap_service.py (ITU-T G.984.2 - SFP Clase B+)
RANGOS_POTENCIA_DBM = {
    "optimo": (-24.0, -8.5),     # OPTIMO en backend (-24.0 <= rx <= -8.0)
    "critico": (-27.0, -24.1),   # CRITICO en backend (-27.0 <= rx < -24.0)
    "caido": (-42.0, -27.1),     # CAIDO en backend (rx < -27.0)
    "saturado": (-7.9, 2.0),     # CAIDO por saturación (> -8.0)
}


def generar_potencia_dbm(modo: str) -> Tuple[float, str]:
    modo_efectivo = modo.lower()
    if modo_efectivo == "random":
        modo_efectivo = random.choice(["optimo", "critico", "caido"])

    limite_inferior, limite_superior = RANGOS_POTENCIA_DBM[modo_efectivo]
    potencia_generada = random.uniform(limite_inferior, limite_superior)
    return round(potencia_generada, 2), modo_efectivo


def obtener_token_jwt(base_url: str, username: str, password: str) -> str:
    login_url = f"{base_url.rstrip('/')}/auth/login"
    resp = requests.post(
        login_url,
        data={"username": username, "password": password},
        timeout=5.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Error autenticando emulador (HTTP {resp.status_code}): {resp.text}")
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("El servidor no devolvió access_token.")
    return token


def construir_payload(puerto_id: int, potencia_rx: float, clase_sfp: str = "B+") -> Dict[str, Any]:
    potencia_tx = round(random.uniform(1.5, 3.5), 2)
    return {
        "puerto_id": puerto_id,
        "potencia_rx_1490_dbm": potencia_rx,
        "potencia_tx_1310_dbm": potencia_tx,
        "clase_sfp": clase_sfp,
        "fuente_dato": "SIMULADOR",
    }


def ejecutar_emulador(
    puerto: int,
    modo: str,
    ciclos: int,
    intervalo: int,
    base_url: str,
    username: str,
    password: str,
) -> None:
    lecturas_url = f"{base_url.rstrip('/')}/naps/lecturas"
    print("=" * 70)
    print("🛰️  INICIANDO EMULADOR DE TELEMETRÍA GPON (JWT + ITU-T G.984.2)")
    print(f" • Puerto ID destino: {puerto}")
    print(f" • Modo configurado:  {modo.upper()}")
    print(f" • Endpoint destino:  {lecturas_url}")
    print("=" * 70)

    try:
        token = obtener_token_jwt(base_url, username, password)
    except Exception as exc:
        print(f" ❌ ERROR DE AUTENTICACIÓN: {exc}")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    for ciclo_actual in range(1, ciclos + 1):
        potencia, _ = generar_potencia_dbm(modo)
        payload = construir_payload(puerto_id=puerto, potencia_rx=potencia)

        print(f"\n[Ciclo {ciclo_actual}/{ciclos}] Transmitiendo lectura...")
        print(
            f" -> Rx: {potencia} dBm | Tx: {payload['potencia_tx_1310_dbm']} dBm | Fuente: {payload['fuente_dato']}"
        )

        try:
            inicio_transmision = time.time()
            respuesta = requests.post(lecturas_url, json=payload, headers=headers, timeout=5.0)
            latencia_ms = round((time.time() - inicio_transmision) * 1000, 2)

            if respuesta.status_code in (200, 201):
                datos_respuesta = respuesta.json()
                diagnostico = datos_respuesta.get("diagnostico", "NO_ESPECIFICADO")
                print(f" ✔️  [HTTP {respuesta.status_code}] {latencia_ms} ms | Estado BD: {diagnostico}")
            else:
                print(f" ⚠️  Error HTTP {respuesta.status_code}: {respuesta.text}")

        except requests.exceptions.ConnectionError:
            print(f" ❌ ERROR DE CONEXIÓN: Servidor inalcanzable en '{lecturas_url}'.")
            if ciclo_actual == 1 and ciclos > 1:
                sys.exit(1)

        if ciclo_actual < ciclos:
            time.sleep(intervalo)


def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emulador CLI de Telemetría GPON.")
    parser.add_argument("--puerto", type=int, required=True, help="ID del puerto NAP en BD")
    parser.add_argument(
        "--modo",
        type=str,
        choices=["optimo", "critico", "caido", "saturado", "random"],
        default="optimo",
    )
    parser.add_argument("--ciclos", type=int, default=1)
    parser.add_argument("--intervalo", type=int, default=2)
    parser.add_argument("--base-url", type=str, default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--username", type=str, default="operador@gestionnap.ve")
    parser.add_argument("--password", type=str, default="plaza2026")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = parsear_argumentos()
        ejecutar_emulador(
            args.puerto,
            args.modo,
            args.ciclos,
            args.intervalo,
            args.base_url,
            args.username,
            args.password,
        )
    except KeyboardInterrupt:
        sys.exit(0)
