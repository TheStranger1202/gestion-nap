/**
 * Módulo de ingesta simulada de telemetría óptica en campo.
 * Valida nomenclatura NAP del Municipio Plaza y parámetros de potencia GPON.
 */
(() => {
  'use strict';

  // Expresión regular estricta definida en la especificación territorial
  const NAP_CODE_REGEX = /^PLZ-Z0[1-8]-[A-Z]{3}-D\d{3}-\d{3}-[AFS]$/;

  // Catálogo inmutable de sectores válidos por Zona Operativa (referencia informativa)
  const ZOD_SECTORS = Object.freeze({
    Z01: Object.freeze(['CEN', 'PAR', 'LLA', 'COM']),
    Z02: Object.freeze(['CLA', 'CUR', 'TAM', 'GUA']),
    Z03: Object.freeze(['TRA', 'RUI', 'ORO']),
    Z04: Object.freeze(['NCA', 'GRI', 'NAR']),
    Z05: Object.freeze(['CCA', 'TDE', 'SPC']),
    Z06: Object.freeze(['MEN', 'VES', 'TOR']),
    Z07: Object.freeze(['ZIG', 'ZIC', 'ZSC']),
    Z08: Object.freeze(['VVE', 'GIR', 'BVT']),
  });

  // Límites operativos y de validación estricta
  const LIMITS = Object.freeze({
    PORT_MIN: 1,
    PORT_MAX: 16,
    POWER_MIN: -50.0,
    POWER_MAX: 5.0,
    POWER_DECIMAL_REGEX: /^-?\d+(\.\d{1,2})?$/,
    TOAST_DURATION_MS: 3500,
  });

  // Clases visuales de borde para estados del input Código NAP
  const BORDER_CLASSES = Object.freeze({
    NEUTRAL: ['border-slate-300', 'focus:border-slate-600'],
    VALID: ['border-emerald-500', 'ring-2', 'ring-emerald-500/20', 'focus:border-emerald-600'],
    INVALID: ['border-rose-500', 'ring-2', 'ring-rose-500/20', 'focus:border-rose-600'],
  });

  const ALL_BORDER_TOKENS = Object.freeze([
    ...BORDER_CLASSES.NEUTRAL,
    ...BORDER_CLASSES.VALID,
    ...BORDER_CLASSES.INVALID,
  ]);

  document.addEventListener('DOMContentLoaded', () => {
    const panel = document.getElementById('telemetry-panel');
    const toggleBtn = document.getElementById('telemetry-toggle-btn');
    const toggleIcon = document.getElementById('telemetry-toggle-icon');
    const formBody = document.getElementById('telemetry-form-body');
    const form = document.getElementById('telemetry-form');
    const napInput = document.getElementById('nap-codigo');
    const napFeedback = document.getElementById('nap-codigo-feedback');
    const portSelect = document.getElementById('nap-puerto');
    const portFeedback = document.getElementById('nap-puerto-feedback');
    const powerInput = document.getElementById('nap-potencia');
    const powerFeedback = document.getElementById('nap-potencia-feedback');
    const submitBtn = document.getElementById('telemetry-submit-btn');
    const toastContainer = document.getElementById('telemetry-toast-container');

    if (
      !panel ||
      !form ||
      !napInput ||
      !napFeedback ||
      !portSelect ||
      !portFeedback ||
      !powerInput ||
      !powerFeedback ||
      !submitBtn ||
      !toastContainer
    ) {
      return;
    }

    let isNapDirty = false;
    let isSubmitting = false;
    let activeToastTimeout = null;

    // Aislar eventos del panel flotante para no propagar clics o scroll al mapa Leaflet
    if (window.L && window.L.DomEvent) {
      window.L.DomEvent.disableClickPropagation(panel);
      window.L.DomEvent.disableScrollPropagation(panel);
    } else {
      ['click', 'dblclick', 'mousedown', 'wheel', 'touchstart'].forEach((evtName) => {
        panel.addEventListener(evtName, (evt) => evt.stopPropagation(), { passive: true });
      });
    }

    // Colapsar / expandir tarjeta en campo o pantallas móviles
    if (toggleBtn && formBody) {
      toggleBtn.addEventListener('click', () => {
        const isExpanded = toggleBtn.getAttribute('aria-expanded') === 'true';
        const nextState = !isExpanded;
        toggleBtn.setAttribute('aria-expanded', String(nextState));
        formBody.classList.toggle('hidden', !nextState);
        if (toggleIcon) {
          toggleIcon.classList.toggle('rotate-180', !nextState);
        }
      });
    }

    /**
     * Aplica estilos de borde de Tailwind según el estado de validación.
     * @param {HTMLElement} element
     * @param {'NEUTRAL'|'VALID'|'INVALID'} state
     */
    function applyBorderState(element, state) {
      element.classList.remove(...ALL_BORDER_TOKENS);
      element.classList.add(...BORDER_CLASSES[state]);
      element.setAttribute('aria-invalid', state === 'INVALID' ? 'true' : 'false');
    }

    /**
     * Valida el Código NAP en tiempo real usando estrictamente NAP_CODE_REGEX.
     * @param {boolean} forceEvaluation - Fuerza evaluación aunque el campo esté vacío.
     * @returns {boolean}
     */
    function validateNapCode(forceEvaluation = false) {
      const value = napInput.value;

      if (!isNapDirty && !forceEvaluation && value === '') {
        applyBorderState(napInput, 'NEUTRAL');
        napFeedback.className = 'mt-1 text-[11px] text-slate-500 leading-snug';
        napFeedback.textContent = 'Formato: PLZ-Z0[1-8]-SEC-D001-001-[A|F|S]';
        return false;
      }

      const isValid = NAP_CODE_REGEX.test(value);

      if (isValid) {
        applyBorderState(napInput, 'VALID');
        const [, zona, sector] = value.split('-');
        const knownSectors = ZOD_SECTORS[zona] || [];
        const isKnownSector = knownSectors.includes(sector);

        napFeedback.className = 'mt-1 text-[11px] text-emerald-700 font-medium leading-snug';
        napFeedback.textContent = isKnownSector
          ? `Código válido (${zona} · Sector ${sector} verificado)`
          : `Código válido según patrón oficial (${zona}-${sector})`;
        return true;
      }

      applyBorderState(napInput, 'INVALID');
      napFeedback.className = 'mt-1 text-[11px] text-rose-600 font-medium leading-snug';
      napFeedback.textContent =
        value === ''
          ? 'El código NAP es obligatorio.'
          : 'Formato inválido. Ej: PLZ-Z01-CEN-D001-001-A';
      return false;
    }

    /**
     * Valida que el puerto sea un entero estricto entre 1 y 16.
     * @returns {boolean}
     */
    function validatePort() {
      const raw = portSelect.value.trim();
      const port = Number(raw);
      const isValid =
        raw !== '' &&
        Number.isInteger(port) &&
        port >= LIMITS.PORT_MIN &&
        port <= LIMITS.PORT_MAX;

      if (isValid) {
        portSelect.classList.remove('border-rose-500');
        portSelect.classList.add('border-slate-300');
        portSelect.setAttribute('aria-invalid', 'false');
        portFeedback.classList.add('hidden');
        portFeedback.textContent = '';
        return true;
      }

      portSelect.classList.remove('border-slate-300');
      portSelect.classList.add('border-rose-500');
      portSelect.setAttribute('aria-invalid', 'true');
      portFeedback.classList.remove('hidden');
      portFeedback.textContent = 'Seleccione un puerto válido (1–16).';
      return false;
    }

    /**
     * Valida la potencia óptica (dBm) con tolerancia a valores negativos y 2 decimales.
     * @returns {boolean}
     */
    function validatePower() {
      const raw = powerInput.value.trim();

      if (powerInput.validity && powerInput.validity.badInput) {
        setPowerError('Valor numérico mal formado.');
        return false;
      }

      if (raw === '') {
        setPowerError('Ingrese la potencia en dBm.');
        return false;
      }

      if (!LIMITS.POWER_DECIMAL_REGEX.test(raw)) {
        setPowerError('Use hasta 2 decimales (ej. -15.50).');
        return false;
      }

      const numericValue = Number(raw);
      if (
        !Number.isFinite(numericValue) ||
        numericValue < LIMITS.POWER_MIN ||
        numericValue > LIMITS.POWER_MAX
      ) {
        setPowerError(`Rango permitido: ${LIMITS.POWER_MIN} a +${LIMITS.POWER_MAX} dBm.`);
        return false;
      }

      powerInput.classList.remove('border-rose-500');
      powerInput.classList.add('border-slate-300');
      powerInput.setAttribute('aria-invalid', 'false');
      powerFeedback.classList.add('hidden');
      powerFeedback.textContent = '';
      return true;
    }

    /**
     * Marca error visual en el campo de potencia.
     * @param {string} message
     */
    function setPowerError(message) {
      powerInput.classList.remove('border-slate-300');
      powerInput.classList.add('border-rose-500');
      powerInput.setAttribute('aria-invalid', 'true');
      powerFeedback.classList.remove('hidden');
      powerFeedback.textContent = message;
    }

    /**
     * Renderiza notificación flotante Toast segura mediante nodos DOM (sin innerHTML).
     * @param {string} message
     */
    function showToast(message) {
      if (activeToastTimeout !== null) {
        clearTimeout(activeToastTimeout);
        activeToastTimeout = null;
      }

      while (toastContainer.firstChild) {
        toastContainer.removeChild(toastContainer.firstChild);
      }

      const toast = document.createElement('div');
      toast.className =
        'pointer-events-auto flex items-center gap-2.5 bg-slate-900 text-white border border-emerald-500/60 px-4 py-3 rounded-xl shadow-2xl text-xs font-medium transition-all duration-200';

      const indicator = document.createElement('span');
      indicator.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400 shrink-0';

      const textNode = document.createElement('span');
      textNode.textContent = message;

      toast.appendChild(indicator);
      toast.appendChild(textNode);
      toastContainer.appendChild(toast);

      activeToastTimeout = setTimeout(() => {
        if (toast.parentNode === toastContainer) {
          toastContainer.removeChild(toast);
        }
        activeToastTimeout = null;
      }, LIMITS.TOAST_DURATION_MS);
    }

    /**
     * Restablece el formulario y limpia todos los estados visuales de validación.
     */
    function resetFormState() {
      form.reset();
      isNapDirty = false;
      applyBorderState(napInput, 'NEUTRAL');
      napFeedback.className = 'mt-1 text-[11px] text-slate-500 leading-snug';
      napFeedback.textContent = 'Formato: PLZ-Z0[1-8]-SEC-D001-001-[A|F|S]';

      portSelect.classList.remove('border-rose-500');
      portSelect.classList.add('border-slate-300');
      portSelect.setAttribute('aria-invalid', 'false');
      portFeedback.classList.add('hidden');
      portFeedback.textContent = '';

      powerInput.classList.remove('border-rose-500');
      powerInput.classList.add('border-slate-300');
      powerInput.setAttribute('aria-invalid', 'false');
      powerFeedback.classList.add('hidden');
      powerFeedback.textContent = '';
    }

    // Listeners de validación en tiempo real
    napInput.addEventListener('input', () => {
      isNapDirty = true;
      validateNapCode(false);
    });

    napInput.addEventListener('blur', () => {
      if (napInput.value !== '') {
        isNapDirty = true;
        validateNapCode(false);
      }
    });

    portSelect.addEventListener('change', validatePort);
    powerInput.addEventListener('input', () => {
      if (!powerFeedback.classList.contains('hidden')) {
        validatePower();
      }
    });
    powerInput.addEventListener('blur', () => {
      if (powerInput.value !== '' || (powerInput.validity && powerInput.validity.badInput)) {
        validatePower();
      }
    });

    // Intercepción del envío del formulario
    form.addEventListener('submit', (e) => {
      e.preventDefault();

      if (isSubmitting) {
        return;
      }

      isNapDirty = true;
      const isNapOk = validateNapCode(true);
      const isPortOk = validatePort();
      const isPowerOk = validatePower();

      if (!isNapOk || !isPortOk || !isPowerOk) {
        if (!isNapOk) {
          napInput.focus();
        } else if (!isPortOk) {
          portSelect.focus();
        } else {
          powerInput.focus();
        }
        return;
      }

      isSubmitting = true;
      submitBtn.disabled = true;

      try {
        const parsedPower = Number(powerInput.value.trim());
        const telemetryPayload = Object.freeze({
          codigo_nap: napInput.value,
          puerto: Number(portSelect.value),
          potencia_dbm: parsedPower === 0 ? 0 : parsedPower,
          timestamp: new Date().toISOString(),
        });

        // Evento desacoplado listo para futura integración con API REST / mapa
        document.dispatchEvent(
          new CustomEvent('nap:telemetry-submitted', { detail: telemetryPayload })
        );

        resetFormState();
        showToast('Lectura registrada con éxito');
      } finally {
        isSubmitting = false;
        submitBtn.disabled = false;
      }
    });
  });
})();
