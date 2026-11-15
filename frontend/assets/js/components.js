/**
 * Componentes visuales reutilizables para marcadores y popups GIS de cajas NAP.
 */
const NapComponents = (() => {
  // Diccionario de estilos condicionales según `estado_general`
  const STATUS_CONFIG = {
    OPTIMO: {
      hex: '#10b981',        // Emerald 500
      stroke: '#047857',     // Emerald 700
      badgeBg: 'bg-emerald-50',
      badgeText: 'text-emerald-700',
      badgeBorder: 'border-emerald-200',
      isCritical: false
    },
    ADVERTENCIA: {
      hex: '#f59e0b',        // Amber 500
      stroke: '#b45309',     // Amber 700
      badgeBg: 'bg-amber-50',
      badgeText: 'text-amber-700',
      badgeBorder: 'border-amber-200',
      isCritical: false
    },
    CRITICO: {
      hex: '#e11d48',        // Rose 600
      stroke: '#9f1239',     // Rose 800
      badgeBg: 'bg-rose-50',
      badgeText: 'text-rose-700',
      badgeBorder: 'border-rose-200',
      isCritical: true
    },
    DEFAULT: {
      hex: '#64748b',        // Slate 500
      stroke: '#334155',     // Slate 700
      badgeBg: 'bg-slate-100',
      badgeText: 'text-slate-700',
      badgeBorder: 'border-slate-200',
      isCritical: false
    }
  };

  function getStatusStyle(estadoGeneral) {
    const key = (estadoGeneral || '').toUpperCase();
    return STATUS_CONFIG[key] || STATUS_CONFIG.DEFAULT;
  }

  /**
   * Genera un L.divIcon SVG georreferenciado cuyo color depende de `estado_general`.
   */
  function createNapMarkerIcon(estadoGeneral) {
    const style = getStatusStyle(estadoGeneral);

    const pulseCircle = style.isCritical
      ? `<circle cx="18" cy="16" r="11" fill="${style.hex}" class="nap-critical-pulse" />`
      : '';

    const svgHtml = `
      <svg width="36" height="44" viewBox="0 0 36 44" fill="none" xmlns="http://www.w3.org/2000/svg">
        ${pulseCircle}
        <path
          d="M18 2C9.71573 2 3 8.71573 3 17C3 27.5 18 42 18 42C18 42 33 27.5 33 17C33 8.71573 26.2843 2 18 2Z"
          fill="${style.hex}"
          stroke="#ffffff"
          stroke-width="2.5"
        />
        <circle cx="18" cy="16.5" r="5.5" fill="#ffffff" />
      </svg>
    `;

    return L.divIcon({
      className: 'nap-custom-pin',
      html: svgHtml,
      iconSize: [36, 44],
      iconAnchor: [18, 42],   // Punta exacta del pin sobre la coordenada WGS84
      popupAnchor: [0, -38]   // Apertura limpia del popup encima del marcador
    });
  }

  /**
   * Construye el HTML interno para el Popup nativo de Leaflet.
   */
  function createNapPopupContent(nap) {
    const style = getStatusStyle(nap.estado_general);

    return `
      <div class="p-3.5 font-sans text-slate-800">
        <!-- Encabezado con Código NAP -->
        <div class="flex items-start justify-between gap-2 pb-2.5 border-b border-slate-100">
          <div>
            <span class="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
              Código Identificador
            </span>
            <h3 class="text-xs font-bold text-slate-900 font-mono tracking-tight mt-0.5">
              ${nap.codigo_nap}
            </h3>
          </div>
          <span class="px-2 py-0.5 text-[10px] font-bold rounded-full border ${style.badgeBg} ${style.badgeText} ${style.badgeBorder}">
            ${nap.estado_general}
          </span>
        </div>

        <!-- Metadatos Operativos -->
        <div class="py-2.5 space-y-1.5 text-xs">
          <div class="flex items-center justify-between">
            <span class="text-slate-500">Estado Físico:</span>
            <span class="font-semibold text-slate-800">${nap.estado_fisico}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-slate-500">Zona / Sector:</span>
            <span class="font-medium text-slate-700">${nap.zona} · ${nap.sector}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-slate-500">Capacidad:</span>
            <span class="font-medium text-slate-700">${nap.capacidad_puertos} puertos</span>
          </div>
          <p class="text-[11px] text-slate-500 pt-1 leading-snug">
            ${nap.ubicacion_referencia}
          </p>
        </div>

        <!-- Botón de Acción -->
        <button
          type="button"
          data-nap-id="${nap.id}"
          class="btn-ver-detalles w-full mt-1 py-2 px-3 bg-slate-900 hover:bg-slate-800 active:bg-slate-950 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <span>Ver Detalles</span>
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </button>
      </div>
    `;
  }

  return {
    createNapMarkerIcon,
    createNapPopupContent
  };
})();
