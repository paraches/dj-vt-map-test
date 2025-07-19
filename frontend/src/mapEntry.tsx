import 'vite/modulepreload-polyfill';
import React from 'react';
import ReactDOM from 'react-dom/client';
// エイリアス @ を使ってコンポーネントをインポート
import GoogleMapViewer from './components/GoogleMapViewer';
// グローバルCSSやコンポーネント固有CSSが必要な場合はここでインポート
// import '@/index.css'; // 例: SPAと同じグローバルスタイルを適用する場合

const mapContainer = document.getElementById('google-map-react-container');

if (mapContainer) {
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
  const latStr = mapContainer.dataset.lat;
  const lngStr = mapContainer.dataset.lng;
  const zoomStr = mapContainer.dataset.zoom;

  if (!apiKey) {
    console.error("Google Maps API key is missing from Vite env.");
    mapContainer.innerHTML = '<p style="color:red; text-align:center; padding: 20px;">Configuration Error: Google Maps API Key not found.</p>';
  } else if (!latStr || !lngStr || !zoomStr) {
    console.error("Map coordinates or zoom level missing from data attributes.");
    mapContainer.innerHTML = '<p style="color:red; text-align:center; padding: 20px;">Configuration Error: Map data missing.</p>';
  }
  else {
    const lat = parseFloat(latStr);
    const lng = parseFloat(lngStr);
    const zoom = parseInt(zoomStr, 10);

    ReactDOM.createRoot(mapContainer).render(
      <React.StrictMode>
        <GoogleMapViewer apiKey={apiKey} initialCenter={{ lat, lng }} initialZoom={zoom} />
      </React.StrictMode>
    );
  }
} else {
  console.warn('Map container with ID "google-map-react-container" not found.');
}