# AdivinaELO — League of Legends

Mini-juego web donde adivinás el rango de partidas reales de LoL usando la Riot API.

## Cómo jugar

1. Ingresás tu Riot ID (`Nombre#TAG`)
2. El backend obtiene tus últimas partidas rankeadas
3. Aparecen stats anonimizadas de partidas reales
4. Adivinás en qué rango fue jugada cada una
5. Puntuás y compartís tu resultado

---

## Setup local

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Editá .env y ponés tu RIOT_API_KEY
uvicorn main:app --reload
```

El backend corre en `http://localhost:8000`.

### Frontend

Abrí `frontend/index.html` con un servidor estático (ej: VS Code Live Server, o `python -m http.server` desde la carpeta `frontend`).

La URL del backend en desarrollo ya está configurada como `localhost:8000` en `js/main.js`.

---

## Deploy

### Backend → Render (free tier)

1. Creá un nuevo Web Service en [render.com](https://render.com)
2. Conectá este repositorio
3. Render detecta el `render.yaml` automáticamente
4. Agregá la variable de entorno `RIOT_API_KEY` en el dashboard de Render
5. Deploy 🚀

**Nota:** El free tier se duerme tras 15 min de inactividad. La primera request puede tardar 30-60 segundos.

### Frontend → GitHub Pages

1. Ve a Settings → Pages en tu repositorio
2. Source: Deploy from branch → rama `main`, carpeta `/frontend`
3. Guardá y esperá 1-2 minutos
4. Actualizá la URL del backend en `frontend/js/main.js` con tu URL de Render

---

## Estructura

```
lol-elo-guesser/
├── backend/
│   ├── main.py          # FastAPI: endpoints
│   ├── riot_client.py   # Wrapper async Riot API
│   ├── game_builder.py  # Construye las preguntas del juego
│   ├── cache.py         # Cache TTL en memoria
│   └── requirements.txt
├── frontend/
│   ├── index.html       # Landing page
│   ├── game.html        # Pantalla del juego
│   ├── css/style.css    # Tema LoL oscuro
│   └── js/
│       ├── main.js      # Lógica landing
│       └── game.js      # Lógica del juego + scoring
└── render.yaml
```

---

## API key

Conseguí tu development key gratuita en [developer.riotgames.com](https://developer.riotgames.com).

- Expira cada 24 horas (hay que renovarla manualmente)
- Rate limit: 20 req/seg, 100 req/2min
- Para producción, aplicá a una production key desde el portal de Riot

---

## Sistema de puntos

| Resultado              | Puntos |
|------------------------|--------|
| Tier exacto            | 1000   |
| 1 tier de diferencia   | 500    |
| 2 tiers de diferencia  | 100    |
| 3+ tiers de diferencia | 0      |

Máximo: 10,000 puntos. Grados: S / A / B / C / D.
