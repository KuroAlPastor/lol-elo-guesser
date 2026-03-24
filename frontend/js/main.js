// URL del backend — cambiá esto por tu URL de Render en producción
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://lol-elo-guesser-api.onrender.com'; // ← reemplazar con tu URL de Render

// Pre-llenar si viene de profile.html con query params
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('gameName') && urlParams.get('tagLine')) {
  const preRiotId = `${urlParams.get('gameName')}#${urlParams.get('tagLine')}`;
  document.getElementById('riotId').value = preRiotId;
  if (urlParams.get('region')) {
    document.getElementById('region').value = urlParams.get('region');
  }
}

const form    = document.getElementById('searchForm');
const riotId  = document.getElementById('riotId');
const region  = document.getElementById('region');
const playBtn = document.getElementById('playBtn');
const errorMsg = document.getElementById('errorMsg');
const loader  = document.getElementById('loader');

function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.classList.add('show');
  loader.classList.remove('show');
  playBtn.disabled = false;
}

function hideError() {
  errorMsg.classList.remove('show');
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  hideError();

  const raw = riotId.value.trim();
  if (!raw.includes('#')) {
    showError('Ingresá tu Riot ID completo: Nombre#TAG (ej: Faker#KR1)');
    return;
  }

  const [gameName, tagLine] = raw.split('#');
  if (!gameName || !tagLine) {
    showError('Formato inválido. Usá: Nombre#TAG');
    return;
  }

  playBtn.disabled = true;
  loader.classList.add('show');

  try {
    const url = `${API_BASE}/api/game/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}?region=${region.value}`;
    const resp = await apiFetch(url);
    const data = await resp.json();

    if (!resp.ok) {
      showError(data.detail || 'Error desconocido. Revisá el Riot ID e intentá de nuevo.');
      return;
    }

    // Guardar datos en sessionStorage y navegar al juego
    sessionStorage.setItem('gameData', JSON.stringify(data));
    window.location.href = 'game.html';

  } catch (err) {
    showError('No se pudo conectar con el servidor. Intentá de nuevo en unos segundos.');
  }
});

function parseRiotId() {
  const raw = riotId.value.trim();
  if (!raw.includes('#')) return null;
  const [gameName, tagLine] = raw.split('#');
  if (!gameName || !tagLine) return null;
  return { gameName, tagLine };
}

document.getElementById('triviaBtn').addEventListener('click', () => {
  hideError();
  const parsed = parseRiotId();
  if (!parsed) {
    showError('Ingresá tu Riot ID primero: Nombre#TAG');
    return;
  }
  const { gameName, tagLine } = parsed;
  const params = new URLSearchParams({ gameName, tagLine, region: region.value });
  window.location.href = `trivia.html?${params}`;
});

document.getElementById('profileBtn').addEventListener('click', () => {
  hideError();
  const parsed = parseRiotId();
  if (!parsed) {
    showError('Ingresá tu Riot ID primero: Nombre#TAG');
    return;
  }
  const { gameName, tagLine } = parsed;
  const params = new URLSearchParams({ gameName, tagLine, region: region.value });
  window.location.href = `profile.html?${params}`;
});
