"""
Genera preguntas de trivia sobre la cuenta del jugador a partir de su historial de partidas.
"""
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone

# Valores son nombres de archivo SVG (sin la ruta img/)
RACCOON_HINTS = {
    "most_played_champ":     "raccoon-spy",     # investigando el campeón más jugado
    "most_played_role":      "raccoon-spy",     # investigando la línea
    "best_kda_champ":        "raccoon-happy",   # buenas stats
    "most_teammate":         "raccoon-ok",      # compañero de equipo
    "most_used_skin":        "raccoon-ok",      # skin usada
    "highest_kills":         "raccoon-sad",     # kills (víctimas)
    "best_winrate_champ":    "raccoon-happy",   # victorias
    "most_played_vs":        "raccoon-spy",     # rival investigado
    "most_cs_game":          "raccoon-read",    # CS = farmeo = "lectura del mapa"
    "total_pentas":          "raccoon-happy",   # logro épico
    "win_streak":            "raccoon-happy",   # racha ganadora
    "skin_of_champ":         "raccoon-ok",      # skin específica
    "default_vs_skin":       "raccoon-spy",     # estadística de skins
    "most_played_with_skin": "raccoon-ok",      # skin frecuente
    "fav_champ_role":        "raccoon-spy",     # favorito por línea
    "tilt_pick":             "raccoon-sad",     # tilt = triste
}

ROLE_ES = {
    "TOP":     "Top",
    "JUNGLE":  "Jungla",
    "MIDDLE":  "Mid",
    "BOTTOM":  "Bot",
    "UTILITY": "Support",
}


def _plural(n: int, sing: str = "vez", pl: str = "veces") -> str:
    return sing if n == 1 else pl


def _make_options(correct: str, pool: list, n: int = 4) -> list:
    wrong = [x for x in pool if x != correct]
    random.shuffle(wrong)
    options = [correct] + wrong[:n - 1]
    random.shuffle(options)
    return options


def _first_letter_hint(name: str) -> str:
    return "Empieza con '" + name[0].upper() + "' y tiene " + str(len(name)) + " letras"


def build_trivia_questions(
    player_puuid: str,
    matches: list,
    champ_pool: list,
    champion_skins: dict = None,  # {champion: {skin_num: skin_name}}
) -> list:
    if champion_skins is None:
        champion_skins = {}

    questions = []

    # ---- Acumular estadísticas ----
    champ_games:    Counter = Counter()
    champ_wins:     Counter = Counter()
    champ_kda:      defaultdict = defaultdict(list)
    role_games:     Counter = Counter()
    # Campeón más jugado por posición: {position: Counter({champion: games})}
    role_champ_games: defaultdict = defaultdict(Counter)
    teammate_games: Counter = Counter()
    opponent_games: Counter = Counter()
    total_pentas    = 0
    penta_champs:   Counter = Counter()

    # Skins: {champion: Counter({skin_name: usos})}
    champ_skin_uses: defaultdict = defaultdict(Counter)
    skin_total   = 0
    default_total = 0

    max_streak = 0
    current_streak = 0

    max_kills_info = {"kills": 0, "champion": "", "date": ""}
    max_cs_info    = {"cs": 0,    "champion": "", "date": ""}

    # Tilt pick: campeón elegido después de 2+ derrotas seguidas
    # Ordenar los matches de más antiguo a más reciente para analizar la secuencia
    ranked_matches = sorted(
        [m for m in matches if m.get("info", {}).get("queueId") in (420, 440)],
        key=lambda m: m.get("info", {}).get("gameCreation", 0)
    )
    tilt_picks: Counter = Counter()   # campeón elegido estando en tilt (≥2 derrotas seguidas)
    tilt_streak = 0                   # contador de derrotas consecutivas en orden temporal

    for match in ranked_matches:
        info = match.get("info", {})
        participants = info.get("participants", [])
        game_date = datetime.fromtimestamp(
            info.get("gameCreation", 0) / 1000, tz=timezone.utc
        ).strftime("%d/%m/%Y")

        me = next((p for p in participants if p.get("puuid") == player_puuid), None)
        if me is None:
            continue

        champion = me.get("championName", "")
        team_id  = me.get("teamId", 0)
        position = me.get("teamPosition", "")
        win      = me.get("win", False)
        kills    = me.get("kills", 0)
        deaths   = me.get("deaths", 0)
        assists  = me.get("assists", 0)
        cs       = me.get("totalMinionsKilled", 0) + me.get("neutralMinionsKilled", 0)
        skin_id  = me.get("skinId", 0)
        pentas   = me.get("pentaKills", 0)

        champ_games[champion] += 1
        if win:
            champ_wins[champion] += 1

        kda_ratio = round((kills + assists) / max(deaths, 1), 2)
        champ_kda[champion].append(kda_ratio)

        if position:
            role_games[position] += 1
            role_champ_games[position][champion] += 1

        # Skins
        if skin_id > 0:
            skin_total += 1
            # Resolver nombre de la skin
            skins_map = champion_skins.get(champion, {})
            skin_name = skins_map.get(skin_id)
            if skin_name and skin_name.lower() != "default":
                champ_skin_uses[champion][skin_name] += 1
            else:
                # Fallback si no tenemos el nombre
                champ_skin_uses[champion]["Skin #" + str(skin_id)] += 1
        else:
            default_total += 1

        # Pentakills
        if pentas > 0:
            total_pentas += pentas
            penta_champs[champion] += pentas

        # Record kills
        if kills > max_kills_info["kills"]:
            max_kills_info = {"kills": kills, "champion": champion, "date": game_date}

        # Record CS
        if cs > max_cs_info["cs"]:
            max_cs_info = {"cs": cs, "champion": champion, "date": game_date}

        # Tilt pick: si el jugador llegó a esta partida con ≥2 derrotas seguidas,
        # el campeón elegido cuenta como "tilt pick"
        if tilt_streak >= 2:
            tilt_picks[champion] += 1

        # Actualizar rachas DESPUÉS de registrar el tilt pick
        if win:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
            tilt_streak = 0
        else:
            current_streak = 0
            tilt_streak += 1

        # Teammates
        for p in participants:
            if p.get("teamId") == team_id and p.get("puuid") != player_puuid:
                name = p.get("riotIdGameName") or p.get("summonerName")
                if name:
                    teammate_games[name] += 1

        # Rivales
        for p in participants:
            if p.get("teamId") != team_id and p.get("teamPosition") == position and position:
                opp = p.get("championName", "")
                if opp:
                    opponent_games[opp] += 1

    played_champs = list(champ_games.keys())

    # ============================================================
    # PREGUNTAS
    # ============================================================

    # 1. Campeón más jugado
    if champ_games:
        top_champ, top_count = champ_games.most_common(1)[0]
        second_count = champ_games.most_common(2)[-1][1] if len(champ_games) >= 2 else 0
        questions.append({
            "id":         "most_played_champ",
            "question":   "¿Cuál fue el campeón que más veces jugaste?",
            "options":    _make_options(top_champ, played_champs + champ_pool),
            "correct":    top_champ,
            "raccoon": RACCOON_HINTS["most_played_champ"],
            "hint":       _first_letter_hint(top_champ),
            "fact":       "Lo jugaste " + str(top_count) + " " + _plural(top_count) + " (el 2º: " + str(second_count) + ")",
        })

    # 2. Skin de tu campeón principal
    # Pregunta: "¿Qué skin de [champion] más usaste en ranked?"
    # Opciones: todas las skins disponibles del campeón (desde Data Dragon)
    if champ_games and champ_skin_uses:
        top_champ = champ_games.most_common(1)[0][0]
        if top_champ in champ_skin_uses and champ_skin_uses[top_champ]:
            top_skin, top_skin_count = champ_skin_uses[top_champ].most_common(1)[0]
            # Opciones: otras skins del mismo campeón desde Data Dragon
            all_skins_for_champ = [
                name for num, name in champion_skins.get(top_champ, {}).items()
                if num > 0 and name.lower() != "default"
            ]
            if len(all_skins_for_champ) >= 3:
                opts = _make_options(top_skin, all_skins_for_champ)
                questions.append({
                    "id":         "skin_of_champ",
                    "question":   "¿Qué skin de " + top_champ + " más usaste en ranked?",
                    "options":    opts,
                    "correct":    top_skin,
                    "raccoon": RACCOON_HINTS["skin_of_champ"],
                    "hint":       "Su nombre empieza con '" + top_skin[0].upper() + "' y tiene " + str(len(top_skin)) + " caracteres",
                    "fact":       "La usaste " + str(top_skin_count) + " " + _plural(top_skin_count) + " en ranked con " + top_champ,
                })

    # 3. ¿Con o sin skin?
    total_games = skin_total + default_total
    if total_games >= 10 and skin_total > 0 and default_total > 0:
        skin_pct = round(skin_total / total_games * 100)
        # Opciones: porcentajes cercanos
        base = skin_pct
        opts_pool = list({str(max(0, base - 20)), str(max(0, base - 10)),
                          str(min(100, base + 10)), str(min(100, base + 20))} - {str(base)})
        correct_val = str(base) + "%"
        opts = _make_options(correct_val, [str(x) + "%" for x in [
            max(0, base - 20), max(0, base - 10), min(100, base + 10), min(100, base + 20)
        ] if x != base])
        questions.append({
            "id":         "default_vs_skin",
            "question":   "¿Qué porcentaje de tus partidas rankeadas jugaste CON skin (no default)?",
            "options":    opts,
            "correct":    correct_val,
            "raccoon": RACCOON_HINTS["default_vs_skin"],
            "hint":       "Jugaste " + str(total_games) + " partidas en total con este historial",
            "fact":       str(skin_total) + " con skin y " + str(default_total) + " con default (" + str(skin_pct) + "%)",
        })

    # 4. Posición más jugada
    if len(role_games) >= 2:
        top_role, top_role_count = role_games.most_common(1)[0]
        second_role_count = role_games.most_common(2)[-1][1]
        top_role_es = ROLE_ES.get(top_role, top_role)
        raw_opts = _make_options(top_role, list(ROLE_ES.keys()))
        questions.append({
            "id":         "most_played_role",
            "question":   "¿Cuál fue tu posición más jugada?",
            "options":    [ROLE_ES.get(o, o) for o in raw_opts],
            "correct":    top_role_es,
            "raccoon": RACCOON_HINTS["most_played_role"],
            "hint":       "La jugaste más de " + str(second_role_count) + " veces",
            "fact":       "Jugaste " + str(top_role_count) + " partidas como " + top_role_es,
        })

    # 5. Mejor KDA (mín. 3 partidas)
    eligible_kda = {c: sum(v) / len(v) for c, v in champ_kda.items() if len(v) >= 3}
    if eligible_kda:
        best_kda_champ = max(eligible_kda, key=eligible_kda.get)
        best_kda_val   = round(eligible_kda[best_kda_champ], 2)
        questions.append({
            "id":         "best_kda_champ",
            "question":   "¿Con qué campeón tuviste el mejor KDA promedio? (mín. 3 partidas)",
            "options":    _make_options(best_kda_champ, played_champs + champ_pool),
            "correct":    best_kda_champ,
            "raccoon": RACCOON_HINTS["best_kda_champ"],
            "hint":       _first_letter_hint(best_kda_champ) + " — KDA supera el " + str(int(best_kda_val)),
            "fact":       "KDA promedio de " + str(best_kda_val) + " con " + best_kda_champ,
        })

    # 6. Compañero más frecuente
    if len(teammate_games) >= 2:
        top_tm, top_tm_count = teammate_games.most_common(1)[0]
        questions.append({
            "id":         "most_teammate",
            "question":   "¿Con qué invocador jugaste más partidas en equipo?",
            "options":    _make_options(top_tm, list(teammate_games.keys())),
            "correct":    top_tm,
            "raccoon": RACCOON_HINTS["most_teammate"],
            "hint":       _first_letter_hint(top_tm),
            "fact":       "Jugaron juntos " + str(top_tm_count) + " " + _plural(top_tm_count),
        })

    # 7. Total pentakills
    penta_opts_base = total_pentas
    opts_pool = list({str(max(0, penta_opts_base - 2)), str(max(0, penta_opts_base - 1)),
                      str(penta_opts_base + 1), str(penta_opts_base + 2)} - {str(penta_opts_base)})
    penta_fact = str(total_pentas) + " pentakill" + ("s" if total_pentas != 1 else "")
    if penta_champs:
        best_penta_champ = penta_champs.most_common(1)[0][0]
        penta_fact += " — la mayoría con " + best_penta_champ
    questions.append({
        "id":         "total_pentas",
        "question":   "¿Cuántas pentakills hiciste en este historial?",
        "options":    _make_options(str(penta_opts_base), opts_pool),
        "correct":    str(penta_opts_base),
        "raccoon": RACCOON_HINTS["total_pentas"],
        "hint":       "El número está entre " + str(max(0, penta_opts_base - 1)) + " y " + str(penta_opts_base + 1),
        "fact":       penta_fact,
    })

    # 8. Racha ganadora máxima
    if max_streak > 0:
        base = max_streak
        opts_pool = list({str(max(1, base - 2)), str(max(1, base - 1)),
                          str(base + 1), str(base + 2)} - {str(base)})
        questions.append({
            "id":         "win_streak",
            "question":   "¿Cuál fue tu racha ganadora más larga?",
            "options":    _make_options(str(base), opts_pool),
            "correct":    str(base),
            "raccoon": RACCOON_HINTS["win_streak"],
            "hint":       "Fue más de " + str(max(1, base - 1)) + " victorias seguidas",
            "fact":       str(base) + " victorias consecutivas",
        })

    # 9. Record de kills
    if max_kills_info["kills"] > 0:
        base = max_kills_info["kills"]
        opts_pool = list({str(max(0, base - 3)), str(max(0, base - 2)),
                          str(base + 1), str(base + 3)} - {str(base)})
        questions.append({
            "id":         "highest_kills",
            "question":   "¿Cuántos kills fue tu mejor partida? (con " + max_kills_info["champion"] + ")",
            "options":    _make_options(str(base), opts_pool),
            "correct":    str(base),
            "raccoon": RACCOON_HINTS["highest_kills"],
            "hint":       "Fue más de " + str(max(0, base - 2)) + " kills",
            "fact":       str(base) + " kills con " + max_kills_info["champion"] + " el " + max_kills_info["date"],
        })

    # 10. Rival más enfrentado
    if len(opponent_games) >= 2:
        top_opp, top_opp_count = opponent_games.most_common(1)[0]
        questions.append({
            "id":         "most_played_vs",
            "question":   "¿Contra qué campeón te enfrentaste más veces en línea?",
            "options":    _make_options(top_opp, list(opponent_games.keys()) + champ_pool),
            "correct":    top_opp,
            "raccoon": RACCOON_HINTS["most_played_vs"],
            "hint":       _first_letter_hint(top_opp),
            "fact":       "Te enfrentaste " + str(top_opp_count) + " " + _plural(top_opp_count) + " contra " + top_opp,
        })

    # 11. Mejor winrate (mín. 5 partidas)
    eligible_wr = {c: champ_wins.get(c, 0) / champ_games[c]
                   for c in champ_games if champ_games[c] >= 5}
    if eligible_wr:
        best_wr_champ = max(eligible_wr, key=eligible_wr.get)
        best_wr_pct   = round(eligible_wr[best_wr_champ] * 100)
        questions.append({
            "id":         "best_winrate_champ",
            "question":   "¿Con qué campeón tuviste el mejor winrate? (mín. 5 partidas)",
            "options":    _make_options(best_wr_champ, played_champs + champ_pool),
            "correct":    best_wr_champ,
            "raccoon": RACCOON_HINTS["best_winrate_champ"],
            "hint":       _first_letter_hint(best_wr_champ) + " — ganaste más del " + str(best_wr_pct - 10) + "%",
            "fact":       str(best_wr_pct) + "% de victorias con " + best_wr_champ,
        })

    # 12. Record CS
    if max_cs_info["cs"] > 0:
        base = max_cs_info["cs"]
        opts_pool = list({str(max(0, base - 50)), str(max(0, base - 20)),
                          str(base + 15), str(base + 40)} - {str(base)})
        questions.append({
            "id":         "most_cs_game",
            "question":   "¿Cuál fue tu CS más alto en una sola partida? (con " + max_cs_info["champion"] + ")",
            "options":    _make_options(str(base), opts_pool),
            "correct":    str(base),
            "raccoon": RACCOON_HINTS["most_cs_game"],
            "hint":       "Superaste los " + str(max(0, base - 30)) + " CS en esa partida",
            "fact":       str(base) + " CS con " + max_cs_info["champion"] + " el " + max_cs_info["date"],
        })

    # 13. Campeón favorito por línea
    # Generamos una pregunta por cada posición donde el jugador jugó ≥4 partidas,
    # preguntando cuál fue su campeón más jugado ahí.
    ROLE_LABEL = {
        "TOP":     "en Top",
        "JUNGLE":  "en Jungla",
        "MIDDLE":  "en Mid",
        "BOTTOM":  "en Bot",
        "UTILITY": "como Support",
    }
    for role, champ_counter in role_champ_games.items():
        if role_games[role] < 4 or len(champ_counter) < 2:
            continue
        top_role_champ, top_role_champ_count = champ_counter.most_common(1)[0]
        all_in_role = list(champ_counter.keys())
        # Completar opciones con campeones del pool global si hay menos de 4 en ese rol
        opts = _make_options(top_role_champ, all_in_role + champ_pool)
        role_label = ROLE_LABEL.get(role, "en " + role)
        questions.append({
            "id":         "fav_champ_role_" + role.lower(),
            "question":   "¿Cuál fue tu campeón más jugado " + role_label + "?",
            "options":    opts,
            "correct":    top_role_champ,
            "raccoon": "raccoon-spy",
            "hint":       _first_letter_hint(top_role_champ),
            "fact":       "Jugaste " + str(top_role_champ_count) + " " + _plural(top_role_champ_count) + " con " + top_role_champ + " " + role_label,
        })

    # 14. Tilt pick
    # Campeón que más eligieron después de ≥2 derrotas seguidas
    if tilt_picks:
        top_tilt, top_tilt_count = tilt_picks.most_common(1)[0]
        questions.append({
            "id":         "tilt_pick",
            "question":   "¿Cuál es tu 'tilt pick'? (el que jugaste después de perder 2+ seguidas)",
            "options":    _make_options(top_tilt, played_champs + champ_pool),
            "correct":    top_tilt,
            "raccoon": "raccoon-sad",
            "hint":       _first_letter_hint(top_tilt),
            "fact":       "Lo elegiste " + str(top_tilt_count) + " " + _plural(top_tilt_count) + " estando en tilt",
        })

    random.shuffle(questions)
    return questions[:10]
