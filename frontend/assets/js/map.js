/**
 * Controlador principal del mapa GIS para Gestión NAP (Municipio Plaza).
 */
document.addEventListener('DOMContentLoaded', () => {
  // Coordenadas centrales de Guarenas, Municipio Plaza (Edo. Miranda, Venezuela)
  const MUNICIPIO_PLAZA_CENTER = [10.4635, -66.6010];
  const DEFAULT_ZOOM = 14;

  // Datos Mock simulando respuesta de GET /api/v1/naps
  const MOCK_NAPS = [
    {
      id: 1,
      codigo_nap: 'PLZ-Z04-NCA-D001-012-A',
      zona: 'Z04',
      sector: 'NCA',
      ubicacion_referencia: 'Nueva Casarapa, Sector Los Cántaros, Poste 32',
      latitud: 10.457890,
      longitud: -66.589410,
      estado_fisico: 'OPERATIVO',
      capacidad_puertos: 8,
      estado_general: 'OPTIMO'
    },
    {
      id: 2,
      codigo_nap: 'PLZ-Z01-CEN-D001-001-A',
      zona: 'Z01',
      sector: 'CEN',
      ubicacion_referencia: 'Calle Comercio c/c Calle Real, Poste 12',
      latitud: 10.467812,
      longitud: -66.613955,
      estado_fisico: 'OPERATIVO',
      capacidad_puertos: 16,
      estado_general: 'CRITICO'
    }
  ];

  // 1. Inicializar instancia de mapa Leaflet
  const map = L.map('map', {
    center: MUNICIPIO_PLAZA_CENTER,
    zoom: DEFAULT_ZOOM,
    zoomControl: false // Reposicionamos abajo a la derecha para mejor ergonomía GIS
  });

  L.control.zoom({ position: 'bottomright' }).addTo(map);

  // Capa base cartográfica oficial de OpenStreetMap (sin API key requerida)
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Gestión NAP Plaza',
    maxZoom: 19
  }).addTo(map);

  // Grupo de capas para gestionar marcadores NAP
  const napMarkersLayer = L.layerGroup().addTo(map);

  // 2. Iterar sobre datos Mock y renderizar marcadores condicionales
  function renderNapMarkers(napsList) {
    napMarkersLayer.clearLayers();

    napsList.forEach((nap) => {
      const markerIcon = NapComponents.createNapMarkerIcon(nap.estado_general);
      const popupHtml = NapComponents.createNapPopupContent(nap);

      const marker = L.marker([nap.latitud, nap.longitud], {
        icon: markerIcon,
        title: `${nap.codigo_nap} (${nap.estado_general})`
      });

      marker.bindPopup(popupHtml, {
        maxWidth: 300,
        closeButton: true
      });

      marker.addTo(napMarkersLayer);
    });

    updateHeaderStats(napsList);
  }

  // 3. Vincular evento al botón "Ver Detalles" dentro del Popup nativo de Leaflet
  map.on('popupopen', (event) => {
    const popupElement = event.popup.getElement();
    if (!popupElement) return;

    const detailsBtn = popupElement.querySelector('.btn-ver-detalles');
    if (detailsBtn) {
      detailsBtn.onclick = () => {
        const napId = Number(detailsBtn.getAttribute('data-nap-id'));
        const selectedNap = MOCK_NAPS.find((item) => item.id === napId);

        console.log('[Gestión NAP] Ver Detalles -> NAP seleccionada:', {
          id: napId,
          codigo_nap: selectedNap?.codigo_nap,
          estado_general: selectedNap?.estado_general,
          datos_completos: selectedNap
        });
      };
    }
  });

  // 4. Actualizar contadores en la barra superior
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

  // Ejecución inicial
  renderNapMarkers(MOCK_NAPS);
});
