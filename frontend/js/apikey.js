// ===== API Key local storage =====
function getStoredKey() {
  return localStorage.getItem('riot_api_key') || '';
}
function setStoredKey(key) {
  if (key) localStorage.setItem('riot_api_key', key.trim());
  else localStorage.removeItem('riot_api_key');
}

// ===== Fetch wrapper que agrega X-Riot-Key si hay una clave guardada =====
async function apiFetch(url) {
  const key = getStoredKey();
  const headers = key ? { 'X-Riot-Key': key } : {};
  return fetch(url, { headers });
}

// ===== Modal de configuración =====
window.addEventListener('DOMContentLoaded', () => {
  const btn     = document.getElementById('apiKeyBtn');
  const modal   = document.getElementById('apiKeyModal');
  const overlay = document.getElementById('apiKeyOverlay');
  const input   = document.getElementById('apiKeyInput');
  const saveBtn = document.getElementById('apiKeySave');
  const clearBtn = document.getElementById('apiKeyClear');
  const status  = document.getElementById('apiKeyStatus');

  function updateStatus() {
    const k = getStoredKey();
    status.textContent = k
      ? `Clave activa: ${k.slice(0, 12)}…`
      : 'Sin clave — usando la del servidor';
  }

  function openModal() {
    input.value = getStoredKey();
    updateStatus();
    modal.classList.add('show');
    overlay.classList.add('show');
    input.focus();
    input.select();
  }
  function closeModal() {
    modal.classList.remove('show');
    overlay.classList.remove('show');
  }

  btn.addEventListener('click', openModal);
  overlay.addEventListener('click', closeModal);

  saveBtn.addEventListener('click', () => {
    setStoredKey(input.value);
    updateStatus();
    setTimeout(closeModal, 700);
  });

  clearBtn.addEventListener('click', () => {
    input.value = '';
    setStoredKey('');
    updateStatus();
  });

  // Cerrar con Escape
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });
});
