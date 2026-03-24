import asyncio
import random
from datetime import datetime, timezone
from riot_client import get_match, TIER_ORDER

POSITION_LABELS = {
    "TOP": "Top",
    "JUNGLE": "Jungla",
    "MIDDLE": "Mid",
    "BOTTOM": "Bot",
    "UTILITY": "Support",
    "": "Desconocida",
}

TIER_ES = {
    "IRON": "Hierro",
    "BRONZE": "Bronce",
    "SILVER": "Plata",
    "GOLD": "Oro",
    "PLATINUM": "Platino",
    "EMERALD": "Esmeralda",
    "DIAMOND": "Diamante",
    "MASTER": "Master",
    "GRANDMASTER": "Gran Maestro",
    "CHALLENGER": "Challenger",
    "UNRANKED": "Sin rango",
}


def _find_lane_opponent(participants: list, team_id: int, team_position: str) -> str | None:
    """Encuentra el campeón enemigo que juega en la misma posición."""
    if not team_position:
        return None
    for p in participants:
        if p.get("teamId") != team_id and p.get("teamPosition") == team_position:
            return p.get("championName")
    return None


def _extract_participant(match_data: dict, puuid: str) -> dict | None:
    info = match_data.get("info", {})
    for p in info.get("participants", []):
        if p.get("puuid") == puuid:
            return p
    return None


def _build_question(match_data: dict, participant: dict, tier: str, question_id: str) -> dict:
    info = match_data.get("info", {})
    participants = info.get("participants", [])
    duration_sec = info.get("gameDuration", 0)
    duration_min = max(duration_sec / 60, 1)

    kills = participant.get("kills", 0)
    deaths = participant.get("deaths", 0)
    assists = participant.get("assists", 0)
    kda_ratio = round((kills + assists) / max(deaths, 1), 2)

    cs = participant.get("totalMinionsKilled", 0) + participant.get("neutralMinionsKilled", 0)
    cs_per_min = round(cs / duration_min, 1)

    position = participant.get("teamPosition", "")
    team_id = participant.get("teamId", 0)
    champion = participant.get("championName", "Unknown")
    win = participant.get("win", False)
    vision = participant.get("visionScore", 0)
    damage = participant.get("totalDamageDealtToChampions", 0)
    gold = participant.get("goldEarned", 0)

    # Rival de línea
    lane_opponent = _find_lane_opponent(participants, team_id, position)

    # Aliados (pista opcional) — nombre de usuario + campeón
    allies = [
        {
            "name": p.get("riotIdGameName") or p.get("summonerName") or "?",
            "champion": p.get("championName", "?"),
        }
        for p in participants
        if p.get("teamId") == team_id and p.get("puuid") != participant.get("puuid")
    ]

    # Fecha de la partida (pista opcional)
    game_creation_ms = info.get("gameCreation", 0)
    if game_creation_ms:
        match_date = datetime.fromtimestamp(
            game_creation_ms / 1000, tz=timezone.utc
        ).strftime("%d/%m/%Y")
    else:
        match_date = "Desconocida"

    # Feedback educativo basado en stats
    edu_hints = _generate_hints(cs_per_min, vision, deaths, damage, duration_min, position, tier)

    return {
        "id": question_id,
        "champion": champion,
        "position": POSITION_LABELS.get(position, position),
        "lane_opponent": lane_opponent,
        "kda": {"kills": kills, "deaths": deaths, "assists": assists},
        "kda_ratio": kda_ratio,
        "cs": cs,
        "cs_per_min": cs_per_min,
        "vision_score": vision,
        "damage_to_champions": damage,
        "gold_earned": gold,
        "duration_minutes": round(duration_min, 1),
        "win": win,
        "correct_tier": tier,
        "correct_tier_es": TIER_ES.get(tier, tier),
        "hints": edu_hints,
        "hint_allies": allies,
        "hint_date": match_date,
    }


def _generate_hints(cs_per_min: float, vision: int, deaths: int,
                    damage: int, duration_min: float, position: str, tier: str) -> list[str]:
    hints = []
    tier_idx = TIER_ORDER.index(tier) if tier in TIER_ORDER else 0

    if position not in ("UTILITY",):
        if cs_per_min < 4:
            hints.append("CS muy bajo — en alto elo se promedian 8+ por minuto")
        elif cs_per_min >= 8:
            hints.append("CS excelente — farming consistente, señal de alto elo")

    if vision > 60:
        hints.append("Visión excepcional — jugadores de alto elo priorizan el control de visión")
    elif vision < 10 and position == "UTILITY":
        hints.append("Visión muy baja para un support")

    if deaths >= 10:
        hints.append("Muchas muertes — morir poco es una de las claves para subir de elo")
    elif deaths == 0:
        hints.append("Partida sin muertes — excelente gestión de riesgo")

    if damage < 5000 and position not in ("UTILITY",) and duration_min > 20:
        hints.append("Daño bajo — podría indicar un rol más de utilidad o bajo impacto")
    elif damage > 40000:
        hints.append("Daño altísimo — probablemente carry de la partida")

    return hints[:2]  # máximo 2 hints por pregunta


async def build_game_questions(
    client,
    player_puuid: str,
    player_tier: str,
    match_ids: list[str],
    platform: str,
) -> list[dict]:
    # Fetch matches en paralelo con semáforo para respetar rate limit
    sem = asyncio.Semaphore(5)

    async def fetch_one(mid: str) -> dict | None:
        async with sem:
            try:
                return await get_match(client, mid, platform)
            except Exception:
                return None

    matches_raw = await asyncio.gather(*[fetch_one(mid) for mid in match_ids[:20]])
    matches = [m for m in matches_raw if m is not None]

    questions = []
    for match in matches:
        info = match.get("info", {})

        # Solo ranked solo (420) o flex (440)
        if info.get("queueId") not in (420, 440):
            continue

        p = _extract_participant(match, player_puuid)
        if p is None or not player_tier or player_tier == "UNRANKED":
            continue

        q = _build_question(match, p, player_tier, match["metadata"]["matchId"])
        questions.append(q)

    random.shuffle(questions)
    return questions[:10]
