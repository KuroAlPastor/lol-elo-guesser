import asyncio
import os
import httpx
from contextvars import ContextVar
from fastapi import HTTPException

API_KEY = os.getenv("RIOT_API_KEY", "")

# Clave por solicitud (override vía X-Riot-Key header)
_request_key: ContextVar[str] = ContextVar('request_key', default='')

def set_request_key(key: str) -> None:
    _request_key.set(key)

# Mapeo plataforma → región
PLATFORM_TO_REGION = {
    "na1": "americas",
    "br1": "americas",
    "la1": "americas",
    "la2": "americas",
    "euw1": "europe",
    "eune1": "europe",
    "tr1": "europe",
    "ru": "europe",
    "kr": "asia",
    "jp1": "asia",
    "oc1": "sea",
}

PLATFORM_NAMES = {
    "la1": "LAN",
    "la2": "LAS",
    "na1": "NA",
    "br1": "BR",
    "euw1": "EUW",
    "eune1": "EUNE",
    "kr": "KR",
    "jp1": "JP",
}

TIER_ORDER = [
    "IRON", "BRONZE", "SILVER", "GOLD",
    "PLATINUM", "EMERALD", "DIAMOND",
    "MASTER", "GRANDMASTER", "CHALLENGER",
]


def _headers() -> dict:
    key = _request_key.get() or API_KEY
    return {"X-Riot-Token": key}


async def _get(client: httpx.AsyncClient, url: str) -> dict:
    """GET con manejo de errores y retry suave en 429."""
    for attempt in range(3):
        resp = await client.get(url, headers=_headers())
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Jugador no encontrado")
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 1))
            await asyncio.sleep(retry_after + 0.5)
            continue
        if resp.status_code == 403:
            raise HTTPException(status_code=403, detail="API key inválida o expirada")
        raise HTTPException(status_code=502, detail=f"Error Riot API: {resp.status_code}")
    raise HTTPException(status_code=429, detail="Rate limit superado, intentá más tarde")


async def get_account(client: httpx.AsyncClient, game_name: str, tag_line: str, region: str) -> dict:
    regional = PLATFORM_TO_REGION.get(region, "americas")
    url = f"https://{regional}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    return await _get(client, url)


async def get_rank(client: httpx.AsyncClient, puuid: str, platform: str) -> dict | None:
    """Retorna el entry RANKED_SOLO_5x5 o None si no rankeado."""
    url = f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    try:
        entries = await _get(client, url)
    except HTTPException as e:
        if e.status_code == 404:
            return None
        raise
    for entry in entries:
        if entry.get("queueType") == "RANKED_SOLO_5x5":
            return entry
    return None


async def get_match_ids(
    client: httpx.AsyncClient,
    puuid: str,
    region: str,
    count: int = 20,
    start_time: int | None = None,
) -> list[str]:
    regional = PLATFORM_TO_REGION.get(region, "americas")
    url = (
        f"https://{regional}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        f"?type=ranked&start=0&count={count}"
    )
    if start_time is not None:
        url += f"&startTime={start_time}"
    return await _get(client, url)


async def get_match(client: httpx.AsyncClient, match_id: str, region: str) -> dict:
    regional = PLATFORM_TO_REGION.get(region, "americas")
    url = f"https://{regional}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    await asyncio.sleep(0.1)  # rate limit suave
    return await _get(client, url)


async def get_champion_mastery(client: httpx.AsyncClient, puuid: str, platform: str, count: int = 10) -> list:
    url = (
        f"https://{platform}.api.riotgames.com"
        f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?count={count}"
    )
    return await _get(client, url)


async def get_champion_skins(client: httpx.AsyncClient, champion_name: str, version: str = "15.1.1") -> dict:
    """Retorna {skin_num: skin_name} para un campeón. skin_num 0 = 'default'."""
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion/{champion_name}.json"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        champ_data = list(data.get("data", {}).values())
        if not champ_data:
            return {}
        skins = champ_data[0].get("skins", [])
        return {s["num"]: s["name"] for s in skins}
    except Exception:
        return {}


async def get_champion_names(client: httpx.AsyncClient, version: str = "15.1.1") -> dict:
    """Retorna {championId_str: championName} desde Data Dragon. Sin auth header."""
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    resp = await client.get(url)
    data = resp.json()
    # data["data"] = {name: {key: "numeric_id", ...}}
    return {v["key"]: k for k, v in data["data"].items()}
