/**
 * Controlador principal del mapa GIS para Gestión NAP (Municipio Plaza).
 */
document.addEventListener('DOMContentLoaded', async () => {
  'use strict';

  // Exigir sesión JWT válida antes de cargar el mapa
  if (typeof ApiClient !== 'undefined' && !ApiClient.requireAuth()) {
    return;
  }

  const MUNICIPIO_PLAZA_CENTER = [10.4685, -66.6050];
  const DEFAULT_ZOOM = 14;

  let activeNaps = [];

  const map = L.map('map', {
    center: MUNICIPIO_PLAZA_CENTER,
    zoom: DEFAULT_ZOOM,
    zoomControl: false,
  });

  L.control.zoom({ position: 'bottomright' }).addTo(map);

  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Gestión NAP Plaza',
    maxZoom: 19,
  }).addTo(map);

  const napMarkersLayer = L.layerGroup().addTo(map);

  function isValidCoordinate(lat, lng) {
    return (
      Number.isFinite(lat) &&
      Number.isFinite(lng) &&
      lat >= -90 &&
      lat <= 90 &&
      lng >= -180 &&
      lng <= 180
    );
  }

  function renderNapMarkers(napsList) {
    napMarkersLayer.clearLayers();

    napsList.forEach((nap) => {
      if (!isValidCoordinate(nap.latitud, nap.longitud)) {
        return;
      }

      const markerIcon = NapComponents.createNapMarkerIcon(nap.estado_general);
      const popupHtml = NapComponents.createNapPopupContent(nap);

      const marker = L.marker([nap.latitud, nap.longitud], {
        icon: markerIcon,
        title: `${nap.codigo_nap} (${nap.estado_general})`,
      });

      marker.bindPopup(popupHtml, {
        maxWidth: 300,
        closeButton: true,
      });

      marker.addTo(napMarkersLayer);
    });

    updateHeaderStats(napsList);
  }

  function updateHeaderStats(napsList) {
    const totalEl = document.getElementById('stat-total');
    const optimoEl = document.getElementById('stat-optimo');
    const criticoEl = document.getElementById('stat-critico');

    if (totalEl) totalEl.textContent = napsList.length;
    if (optimoEl) {
      optimoEl.textContent = napsList.filter((n) => n.estado_general === 'OPTIMO').length;
    }
    if (criticoEl) {
      criticoEl.textContent = napsList.filter((n) => n.estado_general === 'CRITICO').length;
    }
  }

  // Vincular evento al botón "Ver Detalles" dentro del Popup nativo de Leaflet
  map.on('popupopen', (event) => {
    const popupElement = event.popup.getElement();
    if (!popupElement) return;

    const detailsBtn = popupElement.querySelector('.btn-ver-detalles');
    if (detailsBtn) {
      detailsBtn.addEventListener('click', () => {
        const napId = Number(detailsBtn.getAttribute('data-nap-id'));
        const selectedNap = activeNaps.find((item) => item.id === napId);

        console.log('[Gestión NAP] Ver Detalles -> NAP seleccionada:', {
          id: napId,
          codigo_nap: selectedNap?.codigo_nap,
          estado_general: selectedNap?.estado_general,
          datos_completos: selectedNap,
        });
      });
    }
  });

  // Actualizar estado del marcador en tiempo real tras registrar telemetría
  document.addEventListener('nap:telemetry-submitted', (event) => {
    const detail = event.detail || {};
    if (!detail.codigo_nap || !detail.diagnostico) return;

    const targetNap = activeNaps.find((n) => n.codigo_nap === detail.codigo_nap);
    if (!targetNap) return;

    const diag = String(detail.diagnostico).toUpperCase();
    targetNap.estado_general = diag === 'CAIDO' || diag === 'CRITICO' ? 'CRITICO' : 'OPTIMO';
    renderNapMarkers(activeNaps);
  });

  // Carga inicial desde GET /api/v1/naps/
  try {
    activeNaps = await ApiClient.getNaps();
    renderNapMarkers(activeNaps);
  } catch (err) {
    console.error('[Gestión NAP] Error cargando cajas NAP desde el backend:', err.message);
  }
});
