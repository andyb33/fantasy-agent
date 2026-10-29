"""Read-only Yahoo Fantasy Sports client for one league."""
import base64
import json
import os
import xml.etree.ElementTree as ET

from . import config
from .net import request

API = "https://fantasysports.yahooapis.com/fantasy/v2"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"


class YahooError(RuntimeError):
    pass


def _strip_ns(root):
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _t(el, path, default=None):
    if el is None:
        return default
    x = el.find(path)
    return x.text if x is not None and x.text is not None else default


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


class Yahoo:
    def __init__(self, client_id=None, client_secret=None, refresh_token=None):
        self.client_id = client_id or os.environ["YAHOO_CLIENT_ID"]
        self.client_secret = client_secret or os.environ["YAHOO_CLIENT_SECRET"]
        self.refresh_token = refresh_token or os.environ["YAHOO_REFRESH_TOKEN"]
        self.access_token = None
        self.scoring = dict(config.SCORING)
        self.team_key = self.league_key = None

    # ---------- auth & raw requests ----------
    def login(self):
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        status, body = request(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "redirect_uri": "https://localhost:8080",
            "refresh_token": self.refresh_token,
        }, headers={"Authorization": f"Basic {basic}"})
        if status != 200:
            raise YahooError(f"Yahoo login refresh failed (HTTP {status}): {body[:200]!r}")
        tok = json.loads(body)
        self.access_token = tok["access_token"]
        # Yahoo normally keeps the same refresh token; warn if it ever rotates.
        if tok.get("refresh_token") and tok["refresh_token"] != self.refresh_token:
            print("::warning::Yahoo issued a new refresh token; update the YAHOO_REFRESH_TOKEN secret.")

    def get(self, path):
        if not self.access_token:
            self.login()
        status, body = request(f"{API}/{path}", headers={"Authorization": f"Bearer {self.access_token}"})
        if status != 200:
            raise YahooError(f"Yahoo GET {path} -> HTTP {status}: {body[:300]!r}")
        return _strip_ns(ET.fromstring(body))

    # ---------- league structure ----------
    def find_team(self):
        root = self.get("users;use_login=1/games;game_keys=nba/teams")
        for team in root.iter("team"):
            tk = _t(team, "team_key", "")
            if f".l.{config.LEAGUE_ID}.t." in tk:
                self.team_key = tk
                self.league_key = tk.rsplit(".t.", 1)[0]
                return {"team_key": tk, "name": _t(team, "name")}
        raise YahooError(f"Couldn't find your team in league {config.LEAGUE_ID}.")

    def load_settings(self):
        root = self.get(f"league/{self.league_key}/settings")
        mods = {}
        modifiers = root.find(".//stat_modifiers")
        for s in (modifiers.iter("stat") if modifiers is not None else []):
            sid, val = _t(s, "stat_id"), _t(s, "value")
            if sid is not None and val is not None and s.find("value") is not None:
                try:
                    mods[int(sid)] = float(val)
                except ValueError:
                    pass
        if mods:
            self.scoring = mods
        league = root.find(".//league")
        return {
            "current_week": _t(league, "current_week"),
            "scoring": {config.STAT_NAMES.get(k, str(k)): v for k, v in self.scoring.items()},
        }

    def adds_used(self):
        root = self.get(f"team/{self.team_key}")
        ra = root.find(".//roster_adds")
        return {"week": _t(ra, "coverage_value"), "adds_used": _num(_t(ra, "value"))}

    def matchup(self):
        root = self.get(f"league/{self.league_key}/scoreboard")
        for m in root.iter("matchup"):
            teams = []
            for t in m.iter("team"):
                teams.append({
                    "team_key": _t(t, "team_key"),
                    "name": _t(t, "name"),
                    "points": _num(_t(t, "team_points/total")),
                    "projected": _num(_t(t, "team_projected_points/total")),
                })
            if any(t["team_key"] == self.team_key for t in teams):
                me = next(t for t in teams if t["team_key"] == self.team_key)
                opp = next((t for t in teams if t["team_key"] != self.team_key), None)
                return {
                    "week": _t(m, "week"),
                    "week_start": _t(m, "week_start"),
                    "week_end": _t(m, "week_end"),
                    "me": me,
                    "opponent": opp,
                }
        return None

    # ---------- players ----------
    @staticmethod
    def _player(p):
        return {
            "key": _t(p, "player_key"),
            "name": _t(p, "name/full"),
            "team": _t(p, "editorial_team_abbr"),
            "positions": _t(p, "display_position"),
            "status": _t(p, "status", ""),           # GTD / O / INJ / DTD / ''
            "injury_note": _t(p, "injury_note", ""),
            "slot": _t(p, "selected_position/position"),  # PG, Util, BN, IL ...
        }

    def all_rosters(self):
        """Every team's roster: {team_key: {"name":..., "players": [...]}}."""
        root = self.get(f"league/{self.league_key}/teams/roster")
        out = {}
        for team in root.iter("team"):
            tk = _t(team, "team_key")
            if not tk:
                continue
            out[tk] = {"name": _t(team, "name"),
                       "players": [self._player(p) for p in team.iter("player")]}
        return out

    def free_agents(self, sort_type="lastweek", count=25):
        root = self.get(f"league/{self.league_key}/players;status=FA;sort=AR;sort_type={sort_type};count={count}")
        return [self._player(p) for p in root.iter("player")]

    def stats(self, player_keys, stat_type="average_season"):
        """{player_key: {"fp": fantasy pts (per game for averages), "line": {...}}}"""
        out = {}
        keys = list(dict.fromkeys(k for k in player_keys if k))
        for i in range(0, len(keys), 25):
            chunk = ",".join(keys[i:i + 25])
            root = self.get(f"league/{self.league_key}/players;player_keys={chunk}/stats;type={stat_type}")
            for p in root.iter("player"):
                vals = {}
                for s in p.findall("player_stats/stats/stat"):
                    v = _num(_t(s, "value"))
                    if v is not None:
                        vals[int(_t(s, "stat_id"))] = v
                fp = sum(vals.get(sid, 0.0) * w for sid, w in self.scoring.items())
                line = {config.STAT_NAMES[k]: v for k, v in vals.items() if k in config.STAT_NAMES}
                out[_t(p, "player_key")] = {"fp": round(fp, 1), "line": line, "info": self._player(p)}
        return out

    def transactions(self, count=20):
        root = self.get(f"league/{self.league_key}/transactions;count={count}")
        out = []
        for tr in root.iter("transaction"):
            moves = []
            for p in tr.iter("player"):
                td = p.find("transaction_data")
                moves.append({
                    "player_key": _t(p, "player_key"),
                    "name": _t(p, "name/full"),
                    "type": _t(td, "type"),  # add / drop / trade
                    "team": _t(td, "destination_team_name") or _t(td, "source_team_name"),
                })
            out.append({"key": _t(tr, "transaction_key"), "type": _t(tr, "type"),
                        "timestamp": _t(tr, "timestamp"), "moves": moves})
        return out
