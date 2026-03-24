// ===== Constantes =====
const TIER_ORDER = ['IRON','BRONZE','SILVER','GOLD','PLATINUM','EMERALD','DIAMOND','MASTER'];
const TIER_ES = {
  IRON: 'Hierro', BRONZE: 'Bronce', SILVER: 'Plata', GOLD: 'Oro',
  PLATINUM: 'Platino', EMERALD: 'Esmeralda', DIAMOND: 'Diamante',
  MASTER: 'Master', GRANDMASTER: 'Master', CHALLENGER: 'Master',
};
const POINTS = { 0: 1000, 1: 500, 2: 100 };
const HINT_CAPS = [1000, 700, 500]; // índice = nro de pistas usadas

const DDRAGON_VERSION = '15.1.1';

function champImgUrl(name) {
  const fixed = name.replace(/\s+/g, '').replace(/'/g, '');
  return `https://ddragon.leagueoflegends.com/cdn/${DDRAGON_VERSION}/img/champion/${fixed}.png`;
}

function fmt(n) {
  return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n);
}

function normTier(t) {
  return ['GRANDMASTER', 'CHALLENGER'].includes(t) ? 'MASTER' : t;
}

function tierDiff(a, b) {
  const na = normTier(a);
  const nb = normTier(b);
  const ia = TIER_ORDER.includes(na) ? TIER_ORDER.indexOf(na) : TIER_ORDER.length - 1;
  const ib = TIER_ORDER.includes(nb) ? TIER_ORDER.indexOf(nb) : TIER_ORDER.length - 1;
  return Math.abs(ia - ib);
}

// ===== Estado =====
let gameData = null;
let questions = [];
let current = 0;
let score = 0;
let hintsUsed = 0;
let history = []; // { champion, position, guess, correct, pts, hintsUsed }

// ===== Init =====
window.addEventListener('DOMContentLoaded', () => {
  const raw = sessionStorage.getItem('gameData');
  if (!raw) {
    window.location.href = 'index.html';
    return;
  }

  gameData = JSON.parse(raw);
  questions = gameData.questions;

  document.getElementById('initLoader').classList.remove('show');
  document.getElementById('gameScreen').style.display = 'block';

  const p = gameData.player;
  document.getElementById('playerName').textContent = `${p.gameName}#${p.tagLine}`;
  const rankTxt = p.tier === 'UNRANKED'
    ? 'Sin rango · ' + p.region
    : `${p.tier_es} ${p.rank} · ${p.lp} LP · ${p.region}`;
  document.getElementById('playerRank').textContent = rankTxt;
  document.getElementById('qTotal').textContent = questions.length;

  renderProgressCircles(questions.length);
  loadQuestion(0);

  document.getElementById('nextBtn').addEventListener('click', onNext);
  document.getElementById('shareBtn').addEventListener('click', onShare);
  document.getElementById('playAgainBtn').addEventListener('click', () => {
    window.location.href = 'index.html';
  });
});

// ===== Círculos de progreso =====
function renderProgressCircles(total) {
  const wrap = document.getElementById('progressCircles');
  if (!wrap) return;
  wrap.innerHTML = '';
  for (let i = 0; i < total; i++) {
    const c = document.createElement('span');
    c.className = 'prog-circle';
    c.id = `pc-${i}`;
    wrap.appendChild(c);
  }
}

function updateCircle(idx, diff) {
  const c = document.getElementById(`pc-${idx}`);
  if (!c) return;
  c.classList.add(diff === 0 ? 'pc-exact' : diff === 1 ? 'pc-close' : 'pc-miss');
}

// ===== Cargar pregunta =====
function loadQuestion(idx) {
  const q = questions[idx];
  current = idx;

  const pct = Math.round((idx / questions.length) * 100);
  document.getElementById('qNum').textContent = idx + 1;
  document.getElementById('progressPct').textContent = pct + '%';
  document.getElementById('progressFill').style.width = pct + '%';

  const img = document.getElementById('champImg');
  img.src = champImgUrl(q.champion);
  img.alt = q.champion;
  img.onerror = () => { img.src = ''; img.style.background = 'var(--surface2)'; };

  document.getElementById('champName').textContent = q.champion;
  document.getElementById('champPos').textContent = q.position;
  document.getElementById('champDur').textContent = q.duration_minutes;

  const badge = document.getElementById('champResult');
  badge.textContent = q.win ? 'VICTORIA' : 'DERROTA';
  badge.className = 'badge ' + (q.win ? 'win' : 'loss');

  document.getElementById('statKda').textContent = `${q.kda.kills} / ${q.kda.deaths} / ${q.kda.assists}`;
  document.getElementById('statKdaRatio').textContent = `ratio ${q.kda_ratio}`;
  document.getElementById('statCs').textContent = q.cs;
  document.getElementById('statCsMin').textContent = `${q.cs_per_min} / min`;
  document.getElementById('statVision').textContent = q.vision_score;
  document.getElementById('statDmg').textContent = fmt(q.damage_to_champions);
  document.getElementById('statGold').textContent = fmt(q.gold_earned);
  document.getElementById('statOpponent').textContent = q.lane_opponent || 'Sin dato';

  hintsUsed = 0;
  setupHints(q);

  const rankGrid = document.getElementById('rankGrid');
  rankGrid.querySelectorAll('.rank-btn').forEach(btn => {
    btn.disabled = false;
    btn.className = 'rank-btn';
    btn.onclick = () => onGuess(btn.dataset.tier, btn);
  });

  const fb = document.getElementById('feedback');
  fb.classList.remove('show', 'animate-fade');
  const nextBtn = document.getElementById('nextBtn');
  nextBtn.textContent = idx === questions.length - 1 ? 'Ver resultados' : 'Siguiente pregunta →';

  const card = document.getElementById('questionCard');
  card.classList.remove('animate-in');
  void card.offsetWidth;
  card.classList.add('animate-in');
}

// ===== Pistas opcionales =====
function setupHints(q) {
  const alliesBtn    = document.getElementById('hintAlliesBtn');
  const dateBtn      = document.getElementById('hintDateBtn');
  const alliesReveal = document.getElementById('hintAlliesReveal');
  const dateReveal   = document.getElementById('hintDateReveal');

  alliesBtn.disabled = false;
  dateBtn.disabled   = false;
  alliesBtn.classList.remove('used');
  dateBtn.classList.remove('used');
  alliesReveal.style.display = 'none';
  dateReveal.style.display   = 'none';
  alliesReveal.textContent   = '';
  dateReveal.textContent     = '';

  function updateCostLabels() {
    const nextCap = HINT_CAPS[Math.min(hintsUsed + 1, 2)];
    dateBtn.querySelector('.hint-cost').textContent = `cap → ${nextCap} pts`;
  }

  alliesBtn.onclick = () => {
    if (alliesBtn.disabled) return;
    hintsUsed = Math.min(hintsUsed + 1, 2);
    alliesBtn.classList.add('used');
    alliesBtn.disabled = true;
    showAlliesReveal(q, alliesReveal);
    updateCostLabels();
  };

  dateBtn.onclick = () => {
    if (dateBtn.disabled) return;
    hintsUsed = Math.min(hintsUsed + 1, 2);
    dateBtn.classList.add('used');
    dateBtn.disabled = true;
    dateReveal.style.display = 'block';
    dateReveal.textContent = `Fecha: ${q.hint_date || 'Sin dato'}`;
    updateCostLabels();
  };
}

function showAlliesReveal(q, el) {
  const alliesTxt = (q.hint_allies || [])
    .map(a => `${a.name} (${a.champion})`)
    .join(' · ') || 'Sin dato';
  el.style.display = 'block';
  el.textContent = `Aliados: ${alliesTxt}`;
}

function disableHints() {
  document.getElementById('hintAlliesBtn').disabled = true;
  document.getElementById('hintDateBtn').disabled   = true;
}

// ===== Auto-revelar pistas después de responder =====
function autoRevealHints(q) {
  const alliesReveal = document.getElementById('hintAlliesReveal');
  const dateReveal   = document.getElementById('hintDateReveal');

  // Revelar aliados si no estaban ya visibles
  if (alliesReveal.style.display === 'none') {
    showAlliesReveal(q, alliesReveal);
  }
  // Revelar fecha si no estaba ya visible
  if (dateReveal.style.display === 'none') {
    dateReveal.style.display = 'block';
    dateReveal.textContent = `Fecha: ${q.hint_date || 'Sin dato'}`;
  }
}

// ===== Respuesta del jugador =====
function onGuess(guessedTier, btn) {
  const q = questions[current];
  const correctTier = q.correct_tier in TIER_ES ? q.correct_tier : 'MASTER';

  const diff = tierDiff(guessedTier, correctTier);
  const cap  = HINT_CAPS[Math.min(hintsUsed, 2)];
  const pts  = Math.round((POINTS[diff] ?? 0) * cap / 1000);
  score += pts;

  history.push({
    champion: q.champion,
    position: q.position,
    guess:    guessedTier,
    correct:  correctTier,
    pts,
    hintsUsed,
  });

  disableHints();
  autoRevealHints(q);
  updateCircle(current, diff);

  document.getElementById('scoreNum').textContent = score.toLocaleString();

  const rankGrid = document.getElementById('rankGrid');
  const normalizedCorrect = normTier(correctTier);
  rankGrid.querySelectorAll('.rank-btn').forEach(b => {
    b.disabled = true;
    const t = b.dataset.tier;
    const btnIsCorrect = t === normalizedCorrect;
    if (t === guessedTier && btnIsCorrect) b.classList.add('correct');
    else if (t === guessedTier) b.classList.add('wrong');
    else if (btnIsCorrect) b.classList.add('correct');
  });

  showFeedback(diff, pts, q);
}

function showFeedback(diff, pts, q) {
  const fb = document.getElementById('feedback');

  const raccoonEl = document.getElementById('feedbackRaccoon');
  const raccoonMap = { 0: 'raccoon-happy', 1: 'raccoon-ok', 2: 'raccoon-sad' };
  const raccoonFile = raccoonMap[diff] ?? 'raccoon-sad';
  raccoonEl.src = `img/${raccoonFile}.svg`;
  raccoonEl.className = 'feedback-raccoon';
  void raccoonEl.offsetWidth;
  raccoonEl.classList.add(diff === 0 ? 'raccoon-bounce' : diff <= 1 ? 'raccoon-bob' : 'raccoon-shake');

  const filledCount = diff === 0 ? 3 : diff === 1 ? 2 : diff === 2 ? 1 : 0;
  const starsEl = document.getElementById('feedbackStars');
  starsEl.innerHTML = '';
  for (let i = 0; i < 3; i++) {
    const span = document.createElement('span');
    span.className = 'star-anim';
    span.style.animationDelay = `${i * 120}ms`;
    span.textContent = i < filledCount ? '★' : '☆';
    starsEl.appendChild(span);
  }

  const titleEl = document.getElementById('feedbackTitle');
  if (diff === 0) {
    titleEl.textContent = `¡Exacto! Era ${TIER_ES[q.correct_tier] || q.correct_tier} (+${pts} pts)`;
    titleEl.className = 'feedback-title exact';
  } else if (diff === 1) {
    titleEl.textContent = `¡Cerca! Era ${TIER_ES[q.correct_tier] || q.correct_tier} (+${pts} pts)`;
    titleEl.className = 'feedback-title close';
  } else {
    titleEl.textContent = `Era ${TIER_ES[q.correct_tier] || q.correct_tier} (+${pts} pts)`;
    titleEl.className = 'feedback-title miss';
  }

  const hintsEl = document.getElementById('feedbackHints');
  hintsEl.innerHTML = '';
  (q.hints || []).forEach(h => {
    const li = document.createElement('li');
    li.textContent = h;
    hintsEl.appendChild(li);
  });

  fb.classList.add('show', 'animate-fade');
}

// ===== Siguiente pregunta =====
function onNext() {
  if (current + 1 >= questions.length) {
    showResults();
  } else {
    loadQuestion(current + 1);
  }
}

// ===== Resultados =====
function showResults() {
  document.getElementById('gameScreen').style.display = 'none';
  const rs = document.getElementById('resultsScreen');
  rs.classList.add('show', 'animate-in');

  document.getElementById('progressFill').style.width = '100%';
  document.getElementById('progressPct').textContent = '100%';

  const maxScore = questions.length * 1000;
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
    const diff = tierDiff(h.guess, h.correct);
    li.className = 'result-item ' + (diff === 0 ? 'exact' : diff === 1 ? 'close' : 'miss');

    const guessEs   = TIER_ES[h.guess]   || h.guess;
    const correctEs = TIER_ES[h.correct] || h.correct;
    const exact = normTier(h.guess) === normTier(h.correct);

    const hintBadge = h.hintsUsed > 0
      ? `<span class="ri-hint-badge">pista ×${h.hintsUsed}</span>`
      : '';

    li.innerHTML = `
      <span class="ri-champ">${h.champion} <small style="color:var(--text-dim)">${h.position}</small></span>
      <span class="ri-guess">Tu: ${guessEs}</span>
      <span class="ri-answer">${exact ? '✓' : '→'} ${correctEs}</span>
      ${hintBadge}
      <span class="ri-pts">+${h.pts}</span>
    `;
    list.appendChild(li);
  });
}

// ===== Compartir =====
function onShare() {
  const maxScore = questions.length * 1000;
  const pct = score / maxScore;
  let grade = 'D';
  if (pct >= 0.9) grade = 'S';
  else if (pct >= 0.75) grade = 'A';
  else if (pct >= 0.55) grade = 'B';
  else if (pct >= 0.35) grade = 'C';

  const p = gameData.player;
  const text = [
    `AdivinaELO — League of Legends`,
    `${p.gameName}#${p.tagLine} (${p.tier_es})`,
    `Puntuación: ${score.toLocaleString()}/${maxScore.toLocaleString()} — Grado ${grade}`,
    ``,
    history.map(h => {
      const diff = tierDiff(h.guess, h.correct);
      return diff === 0 ? '★★★' : diff === 1 ? '★★☆' : diff === 2 ? '★☆☆' : '☆☆☆';
    }).join(' '),
    ``,
    window.location.origin + '/index.html',
  ].join('\n');

  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('shareBtn');
    btn.textContent = '¡Copiado!';
    setTimeout(() => { btn.textContent = 'Compartir resultado'; }, 2000);
  });
}
