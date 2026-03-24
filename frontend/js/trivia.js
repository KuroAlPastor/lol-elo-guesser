const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://lol-elo-guesser-api.onrender.com';

const DDRAGON_VERSION = '15.1.1';
const POINTS_CORRECT = 1000;
const POINTS_WILDCARD_PENALTY = 200; // descuento por usar comodín

// ===== Estado =====
let triviaData  = null;
let questions   = [];
let current     = 0;
let score       = 0;
let history     = []; // {question, correct, guess, pts, wildcardsUsed}
let wc50Used    = false;
let wcHintUsed  = false;

// ===== Init =====
window.addEventListener('DOMContentLoaded', async () => {
  const params   = new URLSearchParams(window.location.search);
  const gameName = params.get('gameName');
  const tagLine  = params.get('tagLine');
  const region   = params.get('region') || 'la1';

  if (!gameName || !tagLine) {
    window.location.href = 'index.html';
    return;
  }

  try {
    const url  = `${API_BASE}/api/trivia/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}?region=${region}`;
    const resp = await apiFetch(url);
    const data = await resp.json();

    if (!resp.ok) {
      showInitError(data.detail || 'Error al cargar el trivia.');
      return;
    }

    triviaData = data;
    questions  = data.questions;

    document.getElementById('initLoader').classList.remove('show');
    document.getElementById('triviaScreen').style.display = 'block';

    const p = data.player;
    document.getElementById('playerName').textContent = `${p.gameName}#${p.tagLine}`;
    const rankTxt = p.tier === 'UNRANKED'
      ? `Sin rango · ${p.region}`
      : `${p.tier_es} ${p.rank} · ${p.lp} LP · ${p.region}`;
    document.getElementById('playerRank').textContent = rankTxt;
    document.getElementById('qTotal').textContent = questions.length;

    renderCircles(questions.length);
    loadQuestion(0);

    document.getElementById('triviaNextBtn').addEventListener('click', onNext);
    document.getElementById('shareBtn').addEventListener('click', onShare);
    document.getElementById('playAgainBtn').addEventListener('click', () => {
      window.location.href = 'index.html';
    });

  } catch (err) {
    showInitError('No se pudo conectar con el servidor.');
  }
});

function showInitError(msg) {
  const loader = document.getElementById('initLoader');
  loader.innerHTML = `<div style="color:var(--loss);padding:1rem">${msg}</div>
    <a href="index.html" class="btn" style="margin-top:1rem;display:inline-flex">Volver</a>`;
}

// ===== Círculos =====
function renderCircles(total) {
  const wrap = document.getElementById('progressCircles');
  wrap.innerHTML = '';
  for (let i = 0; i < total; i++) {
    const c = document.createElement('span');
    c.className = 'prog-circle';
    c.id = `pc-${i}`;
    wrap.appendChild(c);
  }
}
function updateCircle(idx, correct) {
  const c = document.getElementById(`pc-${idx}`);
  if (c) c.classList.add(correct ? 'pc-exact' : 'pc-miss');
}

// ===== Cargar pregunta =====
function loadQuestion(idx) {
  const q = questions[idx];
  current = idx;
  wc50Used   = false;
  wcHintUsed = false;

  const pct = Math.round((idx / questions.length) * 100);
  document.getElementById('qNum').textContent = idx + 1;
  document.getElementById('progressPct').textContent = pct + '%';
  document.getElementById('progressFill').style.width = pct + '%';

  const rq = document.getElementById('triviaRaccoonQ');
  rq.src = 'img/' + (q.raccoon || 'raccoon-ok') + '.svg';
  document.getElementById('triviaQuestion').textContent = q.question;

  // Limpiar feedback y comodines
  const fb = document.getElementById('triviaFeedback');
  fb.style.display = 'none';
  document.getElementById('wildcardHintReveal').style.display = 'none';

  const wc50btn  = document.getElementById('wc50btn');
  const wcHintBtn = document.getElementById('wcHintBtn');
  wc50btn.disabled   = false;
  wcHintBtn.disabled = false;
  wc50btn.classList.remove('used');
  wcHintBtn.classList.remove('used');

  wc50btn.onclick = () => onWildcard50(q);
  wcHintBtn.onclick = () => onWildcardHint(q);

  // Renderizar opciones
  renderOptions(q.options, q.correct, false);

  // Animación entrada
  const card = document.getElementById('triviaCard');
  card.classList.remove('animate-in');
  void card.offsetWidth;
  card.classList.add('animate-in');

  document.getElementById('triviaNextBtn').textContent =
    idx === questions.length - 1 ? 'Ver resultados' : 'Siguiente →';
}

function renderOptions(options, correct, eliminatedWrong) {
  const container = document.getElementById('triviaOptions');
  container.innerHTML = '';

  options.forEach(opt => {
    const btn = document.createElement('button');
    btn.className = 'trivia-opt-btn';
    btn.textContent = opt;

    // Si 50/50 eliminó esta opción
    if (eliminatedWrong && opt !== correct && eliminatedWrong.includes(opt)) {
      btn.disabled = true;
      btn.classList.add('eliminated');
    } else {
      btn.onclick = () => onAnswer(opt, correct);
    }
    container.appendChild(btn);
  });
}

// ===== Comodines =====
function onWildcard50(q) {
  if (wc50Used) return;
  wc50Used = true;
  document.getElementById('wc50btn').disabled = true;
  document.getElementById('wc50btn').classList.add('used');

  // Eliminar 2 opciones incorrectas aleatoriamente
  const wrong = q.options.filter(o => o !== q.correct);
  const toEliminate = wrong.sort(() => Math.random() - 0.5).slice(0, 2);
  renderOptions(q.options, q.correct, toEliminate);
}

function onWildcardHint(q) {
  if (wcHintUsed) return;
  wcHintUsed = true;
  document.getElementById('wcHintBtn').disabled = true;
  document.getElementById('wcHintBtn').classList.add('used');

  const revealEl = document.getElementById('wildcardHintReveal');
  revealEl.style.display = 'block';
  // La pista es el fact (dato real), para no revelar la respuesta directamente
  revealEl.textContent = 'Pista: ' + (q.hint || 'Sin pista disponible');
}

// ===== Respuesta =====
function onAnswer(chosen, correct) {
  const q = questions[current];
  const isCorrect = chosen === correct;

  // Calcular puntos: descontar por comodines usados
  let pts = isCorrect ? POINTS_CORRECT : 0;
  if (isCorrect && (wc50Used || wcHintUsed)) {
    pts -= (wc50Used ? POINTS_WILDCARD_PENALTY : 0) + (wcHintUsed ? POINTS_WILDCARD_PENALTY : 0);
    pts = Math.max(pts, 0);
  }
  score += pts;

  const wildcardsUsed = (wc50Used ? 1 : 0) + (wcHintUsed ? 1 : 0);
  history.push({ question: q.question, correct, guess: chosen, pts, wildcardsUsed });

  document.getElementById('scoreNum').textContent = score.toLocaleString();
  updateCircle(current, isCorrect);

  // Resaltar opciones
  document.getElementById('triviaOptions').querySelectorAll('.trivia-opt-btn').forEach(btn => {
    btn.disabled = true;
    if (btn.textContent === correct) btn.classList.add('correct');
    else if (btn.textContent === chosen && !isCorrect) btn.classList.add('wrong');
  });

  // Deshabilitar comodines
  document.getElementById('wc50btn').disabled  = true;
  document.getElementById('wcHintBtn').disabled = true;

  // Mostrar feedback
  const raccoonFile = isCorrect ? 'raccoon-happy' : 'raccoon-sad';
  const raccoon = document.getElementById('triviaRaccoon');
  raccoon.src = `img/${raccoonFile}.svg`;
  raccoon.className = `feedback-raccoon ${isCorrect ? 'raccoon-bounce' : 'raccoon-shake'}`;

  document.getElementById('triviaFact').textContent = `${isCorrect ? '¡Correcto! ' : ''}${q.fact}`;
  document.getElementById('triviaFact').className = `trivia-fact ${isCorrect ? 'exact' : 'miss'}`;

  document.getElementById('triviaFeedback').style.display = 'block';
}

// ===== Siguiente =====
function onNext() {
  if (current + 1 >= questions.length) {
    showResults();
  } else {
    loadQuestion(current + 1);
  }
}

// ===== Resultados =====
function showResults() {
  document.getElementById('triviaScreen').style.display = 'none';
  const rs = document.getElementById('resultsScreen');
  rs.classList.add('show', 'animate-in');

  document.getElementById('progressFill').style.width = '100%';
  document.getElementById('progressPct').textContent = '100%';

  const maxScore = questions.length * POINTS_CORRECT;
  const pct = score / maxScore;
  let grade = 'D';
  if (pct >= 0.9) grade = 'S';
  else if (pct >= 0.75) grade = 'A';
  else if (pct >= 0.55) grade = 'B';
  else if (pct >= 0.35) grade = 'C';

  document.getElementById('gradeLetter').textContent = grade;
  document.getElementById('gradeScore').textContent = score.toLocaleString();

  const gradeRaccoon = document.getElementById('gradeRaccoon');
  const raccoonByGrade = { S: 'raccoon-happy', A: 'raccoon-happy', B: 'raccoon-ok', C: 'raccoon-sad', D: 'raccoon-sad' };
  gradeRaccoon.src = `img/${raccoonByGrade[grade]}.svg`;
  gradeRaccoon.className = `grade-raccoon ${grade <= 'B' ? 'raccoon-bounce' : 'raccoon-shake'}`;

  const list = document.getElementById('resultsList');
  list.innerHTML = '';
  history.forEach(h => {
    const li = document.createElement('li');
    const correct = h.guess === h.correct;
    li.className = 'result-item ' + (correct ? 'exact' : 'miss');

    const wcBadge = h.wildcardsUsed > 0
      ? `<span class="ri-hint-badge">comodín ×${h.wildcardsUsed}</span>`
      : '';

    li.innerHTML = `
      <span class="ri-champ" style="flex:2;font-size:0.82rem">${h.question}</span>
      ${wcBadge}
      <span class="ri-answer">${correct ? '✓' : '✗'} ${h.correct}</span>
      <span class="ri-pts">+${h.pts}</span>
    `;
    list.appendChild(li);
  });
}

// ===== Compartir =====
function onShare() {
  const maxScore = questions.length * POINTS_CORRECT;
  const pct = score / maxScore;
  let grade = 'D';
  if (pct >= 0.9) grade = 'S';
  else if (pct >= 0.75) grade = 'A';
  else if (pct >= 0.55) grade = 'B';
  else if (pct >= 0.35) grade = 'C';

  const p = triviaData.player;
  const text = [
    `AdivinaELO — Trivia de cuenta`,
    `${p.gameName}#${p.tagLine}`,
    `Puntuación: ${score.toLocaleString()}/${maxScore.toLocaleString()} — Grado ${grade}`,
    ``,
    history.map(h => h.guess === h.correct ? '[OK]' : '[--]').join(' '),
    ``,
    window.location.origin + '/index.html',
  ].join('\n');

  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('shareBtn');
    btn.textContent = '¡Copiado!';
    setTimeout(() => { btn.textContent = 'Compartir resultado'; }, 2000);
  });
}
