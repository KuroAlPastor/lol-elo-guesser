const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://lol-elo-guesser.onrender.com';

const DDRAGON_VERSION = '15.1.1';

function champImgUrl(name) {
  const fixed = name.replace(/\s+/g, '').replace(/'/g, '');
  return `https://ddragon.leagueoflegends.com/cdn/${DDRAGON_VERSION}/img/champion/${fixed}.png`;
}

function fmtPoints(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'k';
  return String(n);
}

// Card para mains recientes (datos de partidas)
function buildRecentCard(entry, delay) {
  const div = document.createElement('div');
  div.className = 'champ-card animate-in';
  div.style.animationDelay = `${delay}ms`;

  const img = document.createElement('img');
  img.className = 'champ-card-img';
  img.src = champImgUrl(entry.champion);
  img.alt = entry.champion;
  img.onerror = () => { img.src = ''; img.style.background = 'var(--bg2)'; };

  const info = document.createElement('div');
  info.innerHTML = `
    <div class="champ-card-name">${entry.champion}</div>
    <div class="champ-card-pts">${entry.games} partida${entry.games !== 1 ? 's' : ''} · ${entry.winrate}% victorias</div>
    <div class="champ-card-level">${entry.wins}V ${entry.losses}D</div>
  `;

  div.appendChild(img);
  div.appendChild(info);
  return div;
}

// Card para mains históricos (datos de maestría)
function buildMasteryCard(entry, delay) {
  const div = document.createElement('div');
  div.className = 'champ-card animate-in';
  div.style.animationDelay = `${delay}ms`;

  const img = document.createElement('img');
  img.className = 'champ-card-img';
  img.src = champImgUrl(entry.champion);
  img.alt = entry.champion;
  img.onerror = () => { img.src = ''; img.style.background = 'var(--bg2)'; };

  const info = document.createElement('div');
  info.innerHTML = `
    <div class="champ-card-name">${entry.champion}</div>
    <div class="champ-card-pts">${fmtPoints(entry.points)} pts · Nivel ${entry.level}</div>
    <div class="champ-card-level">
      ${entry.books > 0 ? entry.books + ' libro' + (entry.books !== 1 ? 's' : '') : 'Menos de 1 libro'}
      · ${entry.lastPlayDate}
    </div>
  `;

  div.appendChild(img);
  div.appendChild(info);
  return div;
}

// Card para escaladores (con badge de net wins)
function buildEscalaCard(entry, delay) {
  const div = document.createElement('div');
  div.className = 'champ-card animate-in';
  div.style.animationDelay = `${delay}ms`;

  const img = document.createElement('img');
  img.className = 'champ-card-img';
  img.src = champImgUrl(entry.champion);
  img.alt = entry.champion;
  img.onerror = () => { img.src = ''; img.style.background = 'var(--bg2)'; };

  const info = document.createElement('div');
  const netSign = entry.net_wins > 0 ? '+' : '';
  info.innerHTML = `
    <div class="champ-card-name">${entry.champion}</div>
    <div class="champ-card-pts">${entry.winrate}% victorias · ${entry.games} partidas</div>
    <div class="champ-card-level escala-net">${netSign}${entry.net_wins} LP neto</div>
  `;

  div.appendChild(img);
  div.appendChild(info);
  return div;
}

window.addEventListener('DOMContentLoaded', async () => {
  const params = new URLSearchParams(window.location.search);
  const gameName = params.get('gameName');
  const tagLine  = params.get('tagLine');
  const region   = params.get('region') || 'la1';

  const loader     = document.getElementById('loader');
  const errorMsg   = document.getElementById('errorMsg');
  const content    = document.getElementById('profileContent');

  function showError(msg) {
    loader.classList.remove('show');
    errorMsg.textContent = msg;
    errorMsg.classList.add('show');
  }

  if (!gameName || !tagLine) {
    showError('Faltan datos del jugador. Vuelve a la página principal.');
    return;
  }

  try {
    const url = `${API_BASE}/api/profile/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}?region=${region}`;
    const resp = await apiFetch(url);
    const data = await resp.json();

    if (!resp.ok) {
      showError(data.detail || 'Error al cargar el perfil.');
      return;
    }

    loader.classList.remove('show');
    content.style.display = 'block';

    // Banner
    const p = data.player;
    document.getElementById('playerName').textContent = `${p.gameName}#${p.tagLine}`;
    const rankTxt = p.tier === 'UNRANKED'
      ? `Sin rango · ${p.region}`
      : `${p.tier_es} ${p.rank} · ${p.lp} LP · ${p.region}`;
    document.getElementById('playerRank').textContent = rankTxt;

    // Mains recientes (por partidas jugadas)
    const recentEl = document.getElementById('recentMains');
    if (data.mastery.recent.length === 0) {
      document.getElementById('noRecent').style.display = 'block';
    } else {
      data.mastery.recent.forEach((entry, i) => {
        recentEl.appendChild(buildRecentCard(entry, i * 80));
      });
    }

    // Mains históricos (por maestría)
    const histEl = document.getElementById('historicalMains');
    if (data.mastery.historical.length === 0) {
      document.getElementById('noHistorical').style.display = 'block';
    } else {
      data.mastery.historical.forEach((entry, i) => {
        histEl.appendChild(buildMasteryCard(entry, i * 80));
      });
    }

    // Escaladores (solo y flex por separado)
    const escala = data.mastery.escaladores;
    if (escala && (escala.solo.length > 0 || escala.flex.length > 0)) {
      document.getElementById('escalaTitle').style.display = 'block';

      if (escala.solo.length > 0) {
        document.getElementById('escalaSoloLabel').style.display = 'block';
        const soloEl = document.getElementById('escalaSoloList');
        escala.solo.forEach((entry, i) => soloEl.appendChild(buildEscalaCard(entry, i * 80)));
      }

      if (escala.flex.length > 0) {
        document.getElementById('escalaFlexLabel').style.display = 'block';
        const flexEl = document.getElementById('escalaFlexList');
        escala.flex.forEach((entry, i) => flexEl.appendChild(buildEscalaCard(entry, i * 80)));
      }
    }

    // Libros
    document.getElementById('booksCount').textContent = data.mastery.total_books.toLocaleString();
    document.getElementById('booksRef').textContent = data.mastery.books_reference;
    document.getElementById('totalPoints').textContent = fmtPoints(data.mastery.total_points);

    // Botón jugar
    document.getElementById('playBtn').addEventListener('click', () => {
      const qs = new URLSearchParams({ gameName, tagLine, region });
      sessionStorage.removeItem('gameData');
      window.location.href = `index.html?${qs}`;
    });

  } catch (err) {
    showError('No se pudo conectar con el servidor. Intentá de nuevo.');
  }
});
