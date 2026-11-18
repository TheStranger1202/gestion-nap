import subprocess
import time
import pytest
from playwright.sync_api import Page, expect


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


def test_vista_principal_mapa_naps(page: Page, static_server: str):
    js_errors = []
    page.on("pageerror", lambda err: js_errors.append(str(err)))

    page.goto(static_server, wait_until="networkidle")

    # 1. Verificar ausencia de errores de ejecución en JavaScript
    assert len(js_errors) == 0, f"Se detectaron errores JS: {js_errors}"

    # 2. Verificar que las teselas cartográficas (tiles) cargaron correctamente
    loaded_tiles = page.locator(".leaflet-tile-loaded")
    expect(loaded_tiles.first).to_be_visible()
    assert loaded_tiles.count() > 0

    # 3. Verificar contadores de la barra superior
    expect(page.locator("#stat-total")).to_have_text("2")
    expect(page.locator("#stat-optimo")).to_have_text("1")
    expect(page.locator("#stat-critico")).to_have_text("1")

    # 4. Verificar los 2 marcadores personalizados y el pulso de estado CRITICO
    markers = page.locator(".nap-custom-pin")
    expect(markers).to_have_count(2)
    expect(page.locator(".nap-critical-pulse")).to_have_count(1)

    # 5. Hacer clic en el marcador CRITICO (segundo elemento en MOCK_NAPS) y validar popup
    markers.nth(1).click()
    popup = page.locator(".leaflet-popup-content")
    expect(popup).to_be_visible()
    expect(popup).to_contain_text("PLZ-Z01-CEN-D001-001-A")
    expect(popup).to_contain_text("OPERATIVO")
    expect(popup).to_contain_text("CRITICO")

    # 6. Hacer clic en "Ver Detalles" esperando explícitamente el evento de consola
    with page.expect_console_message(
        lambda msg: "Ver Detalles -> NAP seleccionada" in msg.text
    ) as msg_info:
        popup.locator(".btn-ver-detalles").click()

    payload = msg_info.value.args[1].json_value()
    assert payload["id"] == 2
    assert payload["codigo_nap"] == "PLZ-Z01-CEN-D001-001-A"
    assert payload["estado_general"] == "CRITICO"
