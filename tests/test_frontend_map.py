import subprocess
import time
import pytest
from playwright.sync_api import Page, expect

from app.api.v1.auth import create_access_token


@pytest.fixture(scope="module", autouse=True)
def static_server():
    """Levanta el servidor estático de frontend/ durante la ejecución de los tests."""
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", "8085", "--directory", "frontend"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    yield "http://localhost:8085"
    proc.terminate()


def test_redireccion_a_login_sin_sesion(page: Page, static_server: str):
    """Verifica que index.html bloquee el acceso anónimo y redirija a login.html."""
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    page.wait_for_url("**/login.html", timeout=5000)
    expect(page.locator("#login-form")).to_be_visible()


def test_vista_principal_mapa_naps(page: Page, static_server: str):
    js_errors = []
    auth_headers_seen = []
    page.on("pageerror", lambda err: js_errors.append(str(err)))

    # 1. Inyectar JWT válido antes de cargar cualquier script de la página
    token = create_access_token(subject="operador@gestionnap.ve", role="operador")
    page.add_init_script(
        f"""
        localStorage.setItem('access_token', '{token}');
        localStorage.setItem('token_type', 'bearer');
        """
    )

    # 2. Interceptar GET /api/v1/naps/ y verificar cabecera Bearer
    def handle_get_naps(route):
        auth_headers_seen.append(route.request.headers.get("authorization", ""))
        route.fulfill(
            status=200,
            content_type="application/json",
            body="""[
                {
                    "id": 1,
                    "codigo_nap": "PLZ-Z04-NCA-D001-012-A",
                    "zona": "Z04",
                    "sector": "NCA",
                    "ubicacion_referencia": "Nueva Casarapa, Sector Los Cántaros, Poste 32",
                    "latitud": 10.457890,
                    "longitud": -66.589410,
                    "estado_fisico": "OPERATIVO",
                    "capacidad_puertos": 8,
                    "estado_general": "OPTIMO"
                },
                {
                    "id": 2,
                    "codigo_nap": "PLZ-Z01-CEN-D001-001-A",
                    "zona": "Z01",
                    "sector": "CEN",
                    "ubicacion_referencia": "Calle Comercio c/c Calle Real, Poste 12",
                    "latitud": 10.467812,
                    "longitud": -66.613955,
                    "estado_fisico": "OPERATIVO",
                    "capacidad_puertos": 16,
                    "estado_general": "CRITICO"
                }
            ]""",
        )

    page.route("**/api/v1/naps/", handle_get_naps)
    page.goto(f"{static_server}/index.html", wait_until="networkidle")

    # 3. Verificar ausencia de errores JS y envío del token Bearer
    assert len(js_errors) == 0, f"Se detectaron errores JS: {js_errors}"
    assert any(h == f"Bearer {token}" for h in auth_headers_seen)

    # 4. Verificar que las teselas cartográficas (tiles) cargaron correctamente
    loaded_tiles = page.locator(".leaflet-tile-loaded")
    expect(loaded_tiles.first).to_be_visible()
    assert loaded_tiles.count() > 0

    # 5. Verificar contadores de la barra superior
    expect(page.locator("#stat-total")).to_have_text("2")
    expect(page.locator("#stat-optimo")).to_have_text("1")
    expect(page.locator("#stat-critico")).to_have_text("1")

    # 6. Verificar los 2 marcadores personalizados y el pulso de estado CRITICO
    markers = page.locator(".nap-custom-pin")
    expect(markers).to_have_count(2)
    expect(page.locator(".nap-critical-pulse")).to_have_count(1)

    # 7. Hacer clic en el marcador CRITICO (segundo elemento) y validar popup
    markers.nth(1).click()
    popup = page.locator(".leaflet-popup-content")
    expect(popup).to_be_visible()
    expect(popup).to_contain_text("PLZ-Z01-CEN-D001-001-A")
    expect(popup).to_contain_text("OPERATIVO")
    expect(popup).to_contain_text("CRITICO")

    # 8. Hacer clic en "Ver Detalles" y verificar payload de consola + apertura de modal
    with page.expect_console_message(
        lambda msg: "Ver Detalles -> NAP seleccionada" in msg.text
    ) as msg_info:
        popup.locator(".btn-ver-detalles").click()

    payload = msg_info.value.args[1].json_value()
    assert payload["id"] == 2
    assert payload["codigo_nap"] == "PLZ-Z01-CEN-D001-001-A"
    assert payload["estado_general"] == "CRITICO"
    expect(page.locator("#nap-audit-modal")).to_be_visible()
