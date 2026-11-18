import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.database import get_session
from app.main import app


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _get_auth_headers(client: TestClient, username: str = "admin", password: str = "admin123") -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_check(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_naps_rechaza_sin_token(client: TestClient):
    res = client.get("/api/v1/naps/")
    assert res.status_code == 401


def test_flujo_completo_persistencia_sqlite(client: TestClient):
    admin_headers = _get_auth_headers(client, "admin", "admin123")
    operador_headers = _get_auth_headers(client, "operador@gestionnap.ve", "plaza2026")

    # 1. Operador no puede crear cajas NAP (RBAC -> 403)
    nap_payload = {
        "codigo_nap": "PLZ-Z04-NCA-D001-012-A",
        "zona": "Z04",
        "sector": "NCA",
        "ubicacion_referencia": "Nueva Casarapa, Sector Los Cántaros, Poste 32",
        "latitud": 10.457890,
        "longitud": -66.589410,
        "tipo_montaje": "A",
        "capacidad_puertos": 8,
        "splitter_ratio": "1:8",
        "atenuacion_splitter_db": 10.2,
        "cable_distribucion": "DIST-NCA-01",
        "tubo_color_tia598": "Azul",
        "hilo_color_tia598": "Naranja",
    }
    forbidden_res = client.post("/api/v1/naps/", headers=operador_headers, json=nap_payload)
    assert forbidden_res.status_code == 403

    # 2. Admin crea la Caja NAP y sus 8 puertos SC/APC en SQLite
    create_res = client.post("/api/v1/naps/", headers=admin_headers, json=nap_payload)
    assert create_res.status_code == 201
    nap_id = create_res.json()["datos"]["id"]

    # 3. Listar cajas NAP y verificar estado OPTIMO inicial
    list_res = client.get("/api/v1/naps/", headers=operador_headers)
    assert list_res.status_code == 200
    naps = list_res.json()
    assert len(naps) == 1
    assert naps[0]["codigo_nap"] == "PLZ-Z04-NCA-D001-012-A"
    assert naps[0]["estado_general"] == "OPTIMO"
    assert naps[0]["puertos_disponibles"] == 8

    # 4. Ingestar lectura crítica (-28.5 dBm) por codigo_nap + numero_puerto
    lectura_res = client.post(
        "/api/v1/naps/lecturas",
        headers=operador_headers,
        json={
            "codigo_nap": "PLZ-Z04-NCA-D001-012-A",
            "numero_puerto": 2,
            "potencia_rx_1490_dbm": -28.5,
            "potencia_tx_1310_dbm": 2.0,
            "fuente_dato": "MANUAL",
        },
    )
    assert lectura_res.status_code == 201
    assert lectura_res.json()["diagnostico"] == "CAIDO"

    # 5. Verificar que la NAP pasó a CRITICO en el mapa y en el detalle técnico
    list_after = client.get("/api/v1/naps/", headers=operador_headers).json()
    assert list_after[0]["estado_general"] == "CRITICO"

    detalle = client.get(f"/api/v1/naps/{nap_id}", headers=operador_headers).json()
    assert len(detalle["puertos"]) == 8
    puerto_2 = next(p for p in detalle["puertos"] if p["numero_puerto"] == 2)
    assert puerto_2["ultima_lectura"]["potencia_rx_1490_dbm"] == -28.5
