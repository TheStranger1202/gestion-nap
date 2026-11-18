from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_naps_rechaza_sin_token():
    res = client.get("/api/v1/naps/")
    assert res.status_code == 401


def test_login_credenciales_invalidas():
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "operador@gestionnap.ve", "password": "incorrecta"},
    )
    assert res.status_code == 401


def test_flujo_completo_autenticado():
    # 1. Obtener JWT
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": "operador@gestionnap.ve", "password": "plaza2026"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Listar cajas NAP
    naps_res = client.get("/api/v1/naps/", headers=headers)
    assert naps_res.status_code == 200
    naps = naps_res.json()
    assert len(naps) >= 2
    assert naps[0]["id_nap"] == "PLZ-Z04-NCA-D001-012-A"

    # 3. Registrar lectura de telemetría
    lectura_res = client.post(
        "/api/v1/naps/lecturas",
        headers=headers,
        json={
            "puerto_id": 2,
            "potencia_rx_1490_dbm": -31.0,
            "potencia_tx_1310_dbm": 2.1,
            "fuente_dato": "API",
        },
    )
    assert lectura_res.status_code == 201
    assert "diagnostico" in lectura_res.json()

    # 4. Validar rechazo de coordenadas fuera de rango (422)
    bad_nap = client.post(
        "/api/v1/naps/",
        headers=headers,
        json={
            "id_nap": "PLZ-Z01-CEN-D001-099-A",
            "sector": "CEN",
            "latitud": 999.0,
            "longitud": -66.60,
            "capacidad_puertos": 8,
        },
    )
    assert bad_nap.status_code == 422
