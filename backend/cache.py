from cachetools import TTLCache

# Cache de sesiones de juego: key = "gameName#tagLine:region", TTL = 1 hora
game_cache: TTLCache = TTLCache(maxsize=200, ttl=3600)
