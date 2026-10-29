"""NBA schedule and injury news from ESPN's public JSON feeds."""
import datetime as dt
import re
import unicodedata

from .net import get_json

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
UTC = dt.timezone.utc

# Yahoo and ESPN spell some team abbreviations differently; map both to ESPN's.
TEAM_ALIASES = {
    "GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH",
    "WAS": "WSH", "PHO": "PHX", "BRK": "BKN", "BKN": "BKN", "CHO": "CHA",
}


def norm_team(abbr):
    a = (abbr or "").upper()
    return TEAM_ALIASES.get(a, a)


def norm_name(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z ]", "", s.lower())
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", s)
    return " ".join(s.split())


def injuries():
    """Return {normalized player name: info} for every player on ESPN's injury list."""
    data = get_json(f"{BASE}/injuries")
    out = {}
    for team in data.get("injuries", []):
        for i in team.get("injuries", []):
            a = i.get("athlete", {})
            name = a.get("displayName", "")
            details = i.get("details") or {}
            out[norm_name(name)] = {
                "name": name,
                "team": norm_team((a.get("team") or {}).get("abbreviation")),
                "status": i.get("status", ""),             # Out / Day-To-Day
                "fantasy_status": (details.get("fantasyStatus") or {}).get("abbreviation", ""),
                "injury": " ".join(x for x in [details.get("side"), details.get("type"), details.get("detail")] if x),
                "return_date": details.get("returnDate"),
                "news": i.get("shortComment", ""),
                "updated": i.get("date", ""),
            }
    return out


def games_on(et_date):
    """Games for one US-Eastern calendar date."""
    data = get_json(f"{BASE}/scoreboard?dates={et_date:%Y%m%d}&limit=50")
    games = []
    for e in data.get("events", []):
        comp = e["competitions"][0]
        teams = {c["homeAway"]: norm_team(c["team"]["abbreviation"]) for c in comp["competitors"]}
        tip = dt.datetime.strptime(e["date"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
        games.append({
            "et_date": et_date.isoformat(),
            "home": teams.get("home"),
            "away": teams.get("away"),
            "tip_utc": tip,
            "state": e["status"]["type"]["state"],  # pre / in / post
        })
    return games


def schedule(start_et_date, end_et_date):
    """All games from start to end (inclusive), US-Eastern dates."""
    games, d = [], start_et_date
    while d <= end_et_date:
        games.extend(games_on(d))
        d += dt.timedelta(days=1)
    return games
