import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()  # debe correr antes de importar riot_client

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from riot_client import (
    get_account, get_rank, get_match_ids, get_match,
    get_champion_mastery, get_champion_names, get_champion_skins,
    PLATFORM_TO_REGION, PLATFORM_NAMES, TIER_ORDER,
    set_request_key,
)
from game_builder import build_game_questions, TIER_ES
from trivia_builder import build_trivia_questions
from cache import game_cache
from cachetools import TTLCache
from datetime import datetime, timezone

# Cache separado para datos de perfil y para champion names (TTL largo)
profile_cache: TTLCache = TTLCache(maxsize=200, ttl=3600)
champ_names_cache: TTLCache = TTLCache(maxsize=1, ttl=86400)  # 24 horas

POINTS_PER_BOOK = 84_000  # ≈ 7 horas de juego

BOOK_REFS = [
    (100, "Una biblioteca entera"),
    (60,  "La Rueda del Tiempo completa"),
    (30,  "La colección de Discworld"),
    (15,  "A Song of Ice and Fire completo"),
    (7,   "Harry Potter completo y te sobró tiempo"),
    (3,   "El Hobbit y algo más"),
    (1,   "Un libro cortito"),
]

DDRAGON_VERSION = "15.1.1"

app = FastAPI(title="Adivina tu ELO API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/game/{game_name}/{tag_line}")
async def get_game(
    request: Request,
    game_name: str,
    tag_line: str,
    region: str = Query(default="la1", description="Plataforma: la1, la2, na1, euw1, etc."),
):
    region = region.lower()
    if region not in PLATFORM_TO_REGION:
        raise HTTPException(status_code=400, detail=f"Región '{region}' no soportada")

    custom_key = request.headers.get("X-Riot-Key", "").strip()
    effective_key = custom_key or os.getenv("RIOT_API_KEY", "")
    if not effective_key:
        raise HTTPException(status_code=500, detail="RIOT_API_KEY no configurada en el servidor")
    set_request_key(effective_key)

    # Solo cachear cuando se usa la clave del servidor
    cache_key = f"{game_name.lower()}#{tag_line.lower()}:{region}"
    if not custom_key and cache_key in game_cache:
        return game_cache[cache_key]

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. PUUID del jugador
        account = await get_account(client, game_name, tag_line, region)
        puuid = account["puuid"]

        # 2. Rango actual del jugador
        rank_entry = await get_rank(client, puuid, region)
        if rank_entry:
            player_tier = rank_entry["tier"]
            player_rank = rank_entry.get("rank", "")
            player_lp = rank_entry.get("leaguePoints", 0)
            player_wins = rank_entry.get("wins", 0)
            player_losses = rank_entry.get("losses", 0)
        else:
            player_tier = "UNRANKED"
            player_rank = ""
            player_lp = 0
            player_wins = 0
            player_losses = 0

        # 3. Historial de partidas rankeadas
        match_ids = await get_match_ids(client, puuid, region, count=20)
        if not match_ids:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron partidas rankeadas recientes para este jugador",
            )

        # 4. Construir las preguntas del juego
        questions = await build_game_questions(client, puuid, player_tier, match_ids, region)

    if len(questions) < 3:
        raise HTTPException(
            status_code=404,
            detail="No hay suficientes partidas rankeadas para armar el juego (mínimo 3)",
        )

    result = {
        "player": {
            "gameName": account["gameName"],
            "tagLine": account["tagLine"],
            "region": PLATFORM_NAMES.get(region, region.upper()),
            "tier": player_tier,
            "tier_es": TIER_ES.get(player_tier, player_tier),
            "rank": player_rank,
            "lp": player_lp,
            "wins": player_wins,
            "losses": player_losses,
        },
        "questions": questions,
        "total_questions": len(questions),
    }

    if not custom_key:
        game_cache[cache_key] = result
    return result


@app.get("/api/profile/{game_name}/{tag_line}")
async def get_profile(
    request: Request,
    game_name: str,
    tag_line: str,
    region: str = Query(default="la1"),
):
    region = region.lower()
    if region not in PLATFORM_TO_REGION:
        raise HTTPException(status_code=400, detail=f"Región '{region}' no soportada")

    custom_key = request.headers.get("X-Riot-Key", "").strip()
    effective_key = custom_key or os.getenv("RIOT_API_KEY", "")
    if not effective_key:
        raise HTTPException(status_code=500, detail="RIOT_API_KEY no configurada en el servidor")
    set_request_key(effective_key)

    cache_key = f"profile:{game_name.lower()}#{tag_line.lower()}:{region}"
    if not custom_key and cache_key in profile_cache:
        return profile_cache[cache_key]

    now_ts = datetime.now(timezone.utc).timestamp()
    cutoff_ts = int(now_ts - 28 * 24 * 3600)  # epoch segundos, hace 28 días

    async with httpx.AsyncClient(timeout=40.0) as client:
        account = await get_account(client, game_name, tag_line, region)
        puuid = account["puuid"]

        rank_entry = await get_rank(client, puuid, region)
        if rank_entry:
            player_tier = rank_entry["tier"]
            player_rank = rank_entry.get("rank", "")
            player_lp = rank_entry.get("leaguePoints", 0)
        else:
            player_tier = "UNRANKED"
            player_rank = ""
            player_lp = 0

        # Mastery histórica (top 15 para tener más datos)
        masteries = await get_champion_mastery(client, puuid, region, count=15)

        # Champion names: usar cache de 24h
        if "names" in champ_names_cache:
            champ_names = champ_names_cache["names"]
        else:
            champ_names = await get_champion_names(client, DDRAGON_VERSION)
            champ_names_cache["names"] = champ_names

        # Partidas recientes (28 días) para recent mains y escaladores
        recent_ids = await get_match_ids(
            client, puuid, region, count=100, start_time=cutoff_ts
        )

        # Descargar matches en paralelo
        sem = asyncio.Semaphore(5)
        async def _fetch(mid):
            async with sem:
                try:
                    return await get_match(client, mid, region)
                except Exception:
                    return None

        raw = await asyncio.gather(*[_fetch(mid) for mid in recent_ids])
        recent_matches = [m for m in raw if m is not None]

    # --- Mains recientes: campeones más jugados por partidas (28 días) ---
    # Acumuladores separados por cola
    champ_all:  dict[str, dict] = {}
    champ_solo: dict[str, dict] = {}
    champ_flex: dict[str, dict] = {}

    def _add(bucket, champ, won):
        if champ not in bucket:
            bucket[champ] = {"games": 0, "wins": 0}
        bucket[champ]["games"] += 1
        if won:
            bucket[champ]["wins"] += 1

    for match in recent_matches:
        info = match.get("info", {})
        qid = info.get("queueId")
        if qid not in (420, 440):
            continue
        for p in info.get("participants", []):
            if p.get("puuid") != puuid:
                continue
            champ = p.get("championName", "?")
            won = p.get("win", False)
            _add(champ_all, champ, won)
            if qid == 420:
                _add(champ_solo, champ, won)
            else:
                _add(champ_flex, champ, won)

    def _to_recent(bucket):
        return sorted(
            [
                {
                    "champion": c,
                    "games": v["games"],
                    "wins": v["wins"],
                    "losses": v["games"] - v["wins"],
                    "winrate": round(v["wins"] / v["games"] * 100) if v["games"] else 0,
                }
                for c, v in bucket.items()
            ],
            key=lambda x: (-x["games"], -x["winrate"]),
        )[:8]

    recent = _to_recent(champ_all)

    def _to_escala(bucket):
        return sorted(
            [
                {
                    "champion": c,
                    "games": v["games"],
                    "wins": v["wins"],
                    "losses": v["games"] - v["wins"],
                    "net_wins": v["wins"] - (v["games"] - v["wins"]),
                    "winrate": round(v["wins"] / v["games"] * 100) if v["games"] else 0,
                }
                for c, v in bucket.items()
                if v["games"] >= 3
            ],
            key=lambda x: (-x["net_wins"], -x["winrate"]),
        )[:5]

    escaladores = {
        "solo": _to_escala(champ_solo),
        "flex": _to_escala(champ_flex),
    }

    # --- Mains históricos: top mastery por puntos ---
    historical = sorted(
        [
            {
                "champion": champ_names.get(str(m.get("championId", "")), f"Campeón {m.get('championId','')}"),
                "points": m.get("championPoints", 0),
                "level": m.get("championLevel", 1),
                "lastPlayDate": datetime.fromtimestamp(
                    m.get("lastPlayTime", 0) / 1000, tz=timezone.utc
                ).strftime("%Y-%m-%d"),
                "books": m.get("championPoints", 0) // POINTS_PER_BOOK,
            }
            for m in masteries
        ],
        key=lambda x: -x["points"],
    )[:8]

    # --- Libros: suma total de mastery top 15 ---
    total_points = sum(m.get("championPoints", 0) for m in masteries)
    total_books = total_points // POINTS_PER_BOOK
    books_ref = "¡Ni un libro!"
    for threshold, label in BOOK_REFS:
        if total_books >= threshold:
            books_ref = label
            break

    result = {
        "player": {
            "gameName": account["gameName"],
            "tagLine": account["tagLine"],
            "region": PLATFORM_NAMES.get(region, region.upper()),
            "tier": player_tier,
            "tier_es": TIER_ES.get(player_tier, player_tier),
            "rank": player_rank,
            "lp": player_lp,
        },
        "mastery": {
            "recent": recent,
            "historical": historical,
            "escaladores": escaladores,
            "total_points": total_points,
            "total_books": total_books,
            "books_reference": books_ref,
            "ddragon_version": DDRAGON_VERSION,
        },
    }

    if not custom_key:
        profile_cache[cache_key] = result
    return result


trivia_cache: TTLCache = TTLCache(maxsize=100, ttl=3600)


@app.get("/api/trivia/{game_name}/{tag_line}")
async def get_trivia(
    request: Request,
    game_name: str,
    tag_line: str,
    region: str = Query(default="la1"),
):
    region = region.lower()
    if region not in PLATFORM_TO_REGION:
        raise HTTPException(status_code=400, detail=f"Región '{region}' no soportada")

    custom_key = request.headers.get("X-Riot-Key", "").strip()
    effective_key = custom_key or os.getenv("RIOT_API_KEY", "")
    if not effective_key:
        raise HTTPException(status_code=500, detail="RIOT_API_KEY no configurada en el servidor")
    set_request_key(effective_key)

    cache_key = f"trivia:{game_name.lower()}#{tag_line.lower()}:{region}"
    if not custom_key and cache_key in trivia_cache:
        return trivia_cache[cache_key]

    async with httpx.AsyncClient(timeout=40.0) as client:
        account = await get_account(client, game_name, tag_line, region)
        puuid = account["puuid"]

        rank_entry = await get_rank(client, puuid, region)
        player_tier = rank_entry["tier"] if rank_entry else "UNRANKED"
        player_rank = rank_entry.get("rank", "") if rank_entry else ""
        player_lp   = rank_entry.get("leaguePoints", 0) if rank_entry else 0

        # Fetch 50 partidas (más que el modo normal) para tener datos suficientes
        match_ids = await get_match_ids(client, puuid, region, count=50)
        if not match_ids:
            raise HTTPException(status_code=404, detail="No se encontraron partidas rankeadas recientes")

        # Descargar matches en paralelo
        sem = asyncio.Semaphore(5)
        async def _fetch(mid):
            async with sem:
                try:
                    return await get_match(client, mid, region)
                except Exception:
                    return None

        raw = await asyncio.gather(*[_fetch(mid) for mid in match_ids[:50]])
        matches = [m for m in raw if m is not None]

        # Champion names para opciones falsas
        if "names" in champ_names_cache:
            champ_names = champ_names_cache["names"]
        else:
            champ_names = await get_champion_names(client, DDRAGON_VERSION)
            champ_names_cache["names"] = champ_names
        champ_pool = list(champ_names.values())

        # Resolver skin IDs a nombres para los campeones que el jugador usó con skin
        skin_champs: set = set()
        for m in matches:
            info = m.get("info", {})
            if info.get("queueId") not in (420, 440):
                continue
            for p in info.get("participants", []):
                if p.get("puuid") == puuid and p.get("skinId", 0) > 0:
                    skin_champs.add(p.get("championName", ""))

        champion_skins: dict = {}
        skin_sem = asyncio.Semaphore(3)
        async def _fetch_skins(champ):
            async with skin_sem:
                skins = await get_champion_skins(client, champ, DDRAGON_VERSION)
                if skins:
                    champion_skins[champ] = skins

        await asyncio.gather(*[_fetch_skins(c) for c in skin_champs])

    questions = build_trivia_questions(puuid, matches, champ_pool, champion_skins)

    if len(questions) < 3:
        raise HTTPException(status_code=404, detail="No hay suficientes datos para generar el trivia (jugá más partidas rankeadas)")

    result = {
        "player": {
            "gameName": account["gameName"],
            "tagLine":  account["tagLine"],
            "region":   PLATFORM_NAMES.get(region, region.upper()),
            "tier":     player_tier,
            "tier_es":  TIER_ES.get(player_tier, player_tier),
            "rank":     player_rank,
            "lp":       player_lp,
        },
        "questions": questions,
    }

    if not custom_key:
        trivia_cache[cache_key] = result
    return result
