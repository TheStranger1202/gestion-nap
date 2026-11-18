/**
 * Cliente HTTP centralizado y guardia de sesión JWT para Gestión NAP.
 */
const ApiClient = (() => {
  'use strict';

  const DEFAULT_API_BASE =
    window.location.port === '8000'
      ? `${window.location.origin}/api/v1`
      : `${window.location.protocol}//${window.location.hostname || 'localhost'}:8000/api/v1`;

  const CONFIG = Object.freeze({
    apiBaseUrl: DEFAULT_API_BASE,
    loginPage: 'login.html',
    timeoutMs: 10000,
  });

  function getToken() {
    try {
      return localStorage.getItem('access_token');
    } catch (_) {
      return null;
    }
  }

  function clearSession() {
    try {
      localStorage.removeItem('access_token');
      localStorage.removeItem('token_type');
    } catch (_) {}
  }

  function isTokenValid(token) {
    if (!token || typeof token !== 'string') return false;
    const parts = token.split('.');
    if (parts.length !== 3) return false;

    try {
      const payloadJson = atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'));
      const payload = JSON.parse(payloadJson);
      if (!payload.exp || typeof payload.exp !== 'number') return false;
      return payload.exp * 1000 > Date.now();
    } catch (_) {
      return false;
    }
  }

  /**
   * Verifica que exista una sesión JWT vigente; de lo contrario redirige al login.
   */
  function requireAuth() {
    const token = getToken();
    if (!isTokenValid(token)) {
      clearSession();
      window.location.replace(CONFIG.loginPage);
      return false;
    }
    return true;
  }

  function logout() {
    clearSession();
    window.location.replace(CONFIG.loginPage);
  }

  /**
   * Envoltorio seguro sobre fetch con Bearer JWT, timeout y manejo de HTTP 401.
   */
  async function request(endpoint, options = {}) {
    const token = getToken();
    if (!isTokenValid(token)) {
      clearSession();
      window.location.replace(CONFIG.loginPage);
      throw new Error('Sesión expirada o no iniciada.');
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), CONFIG.timeoutMs);

    const headers = {
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    };

    try {
      const response = await fetch(`${CONFIG.apiBaseUrl}${endpoint}`, {
        ...options,
        headers,
        signal: controller.signal,
      });

      if (response.status === 401) {
        clearSession();
        window.location.replace(CONFIG.loginPage);
        throw new Error('Tu sesión ha expirado. Inicia sesión nuevamente.');
      }

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        const detail =
          typeof data?.detail === 'string'
            ? data.detail
            : Array.isArray(data?.detail)
              ? data.detail.map((e) => e.msg || 'Dato inválido').join(' · ')
              : `Error HTTP ${response.status}`;
        throw new Error(detail);
      }

      return data;
    } catch (err) {
      if (err.name === 'AbortError') {
        throw new Error('Tiempo de espera agotado al contactar el servidor.');
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Normaliza un registro NAP del backend al formato esperado por el mapa GIS.
   */
  function normalizeNapRecord(raw, index = 0) {
    const codigo = String(raw.codigo_nap || raw.id_nap || `NAP-${index + 1}`);
    const parts = codigo.split('-');
    const zonaExtraida = parts.length >= 2 ? parts[1] : 'Z01';

    const estadoRaw = String(raw.estado_general || raw.estado || 'OPERATIVO').toUpperCase();
    let estadoGeneral = 'OPTIMO';
    if (estadoRaw === 'CRITICO' || estadoRaw === 'CAIDO') {
      estadoGeneral = 'CRITICO';
    } else if (estadoRaw === 'ADVERTENCIA') {
      estadoGeneral = 'ADVERTENCIA';
    }

    return {
      id: Number.isInteger(raw.id) ? raw.id : index + 1,
      codigo_nap: codigo,
      zona: String(raw.zona || zonaExtraida),
      sector: String(raw.sector || (parts[2] || 'GEN')),
      ubicacion_referencia: String(raw.ubicacion_referencia || 'Sin referencia registrada'),
      latitud: Number(raw.latitud),
      longitud: Number(raw.longitud),
      estado_fisico: String(raw.estado_fisico || raw.estado || 'OPERATIVO'),
      capacidad_puertos: Number(raw.capacidad_puertos) || 8,
      puertos_disponibles:
        raw.puertos_disponibles !== undefined ? Number(raw.puertos_disponibles) : null,
      estado_general: estadoGeneral,
    };
  }

  async function getNaps() {
    const list = await request('/naps/', { method: 'GET' });
    if (!Array.isArray(list)) return [];
    return list.map((item, idx) => normalizeNapRecord(item, idx));
  }

  async function submitTelemetry({ codigo_nap, puerto, potencia_dbm }) {
    return request('/naps/lecturas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
	numero_puerto: Number(puerto),
        potencia_rx_1490_dbm: Number(potencia_dbm),
        potencia_tx_1310_dbm: 2.0, // Valor nominal upstream GPON Clase B+
        fuente_dato: 'MANUAL',
        clase_sfp: 'B+',
        codigo_nap: String(codigo_nap),
      }),
    });
  }

  return Object.freeze({
    requireAuth,
    logout,
    request,
    getNaps,
    submitTelemetry,
  });
})();
