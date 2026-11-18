import re
import subprocess
import time
import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="module", autouse=True)
def static_server():
    """Levanta el servidor estático de frontend/ durante la ejecución de los tests."""
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", "8086", "--directory", "frontend"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    yield "http://localhost:8086"
    proc.terminate()


def test_formulario_telemetria_validacion_y_envio(page: Page, static_server: str):
    js_errors = []
    page.on("pageerror", lambda err: js_errors.append(str(err)))

    page.goto(static_server, wait_until="networkidle")

    # 1. Verificar ausencia de errores JS y presencia del panel flotante
    assert len(js_errors) == 0, f"Se detectaron errores JS: {js_errors}"
    panel = page.locator("#telemetry-panel")
    expect(panel).to_be_visible()

    nap_input = page.locator("#nap-codigo")
    port_select = page.locator("#nap-puerto")
    power_input = page.locator("#nap-potencia")
    submit_btn = page.locator("#telemetry-submit-btn")
    toast_container = page.locator("#telemetry-toast-container")

    # 2. Verificar validación visual en tiempo real del Código NAP (inválido -> rojo)
    nap_input.fill("PLZ-Z09-CEN-D001-001-A")
    expect(nap_input).to_have_class(re.compile(r".*border-rose-500.*"))
    expect(nap_input).to_have_attribute("aria-invalid", "true")

    # 3. Verificar validación visual en tiempo real del Código NAP (válido -> verde)
    nap_input.fill("PLZ-Z04-NCA-D001-012-A")
    expect(nap_input).to_have_class(re.compile(r".*border-emerald-500.*"))
    expect(nap_input).to_have_attribute("aria-invalid", "false")

    # 4. Intentar enviar con potencia fuera de rango (debe bloquear envío)
    port_select.select_option("8")
    power_input.fill("-75.00")
    submit_btn.click()
    expect(toast_container).to_be_empty()
    expect(power_input).to_have_attribute("aria-invalid", "true")

    # 5. Marcar bandera en window para confirmar que e.preventDefault() evita recarga
    page.evaluate("window.__no_page_reload = true")

    # 6. Completar lectura válida con potencia negativa y enviar
    power_input.fill("-15.50")
    submit_btn.click()

    assert page.evaluate("window.__no_page_reload") is True

    # 7. Verificar Toast de confirmación y limpieza automática del formulario
    expect(toast_container).to_contain_text("Lectura registrada con éxito")
    expect(nap_input).to_have_value("")
    expect(nap_input).to_have_class(re.compile(r".*border-slate-300.*"))
    expect(port_select).to_have_value("")
    expect(power_input).to_have_value("")

    # 8. Verificar botón de minimizar/expandir formulario
    toggle_btn = page.locator("#telemetry-toggle-btn")
    form_body = page.locator("#telemetry-form-body")
    toggle_btn.click()
    expect(form_body).to_be_hidden()
    toggle_btn.click()
    expect(form_body).to_be_visible()
