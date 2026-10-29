"""One run of the agent. GitHub runs this every 15 minutes.

Each run does a cheap check (Yahoo rosters + free agents + ESPN injuries).
Only when something changed, or a scheduled brief is due, does it pull the
full picture and ask Claude what to do.

Usage:
  python -m agent.main                 # normal run
  python -m agent.main --dry-run       # print instead of sending, don't save state
  python -m agent.main --force pretip  # force a brief (reset / pretip) for testing
"""
import argparse
import datetime as dt
import json
import os
import sys
import traceback

from . import brain, config, espn, telegram, timing
from .yahoo import Yahoo

STATE_FILE = os.environ.get("STATE_FILE", "state.json")
UTC = dt.timezone.utc
SOON = dt.timedelta(hours=36)


# ---------------- state ----------------
def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)


def now_utc():
    override = os.environ.get("AGENT_NOW")  # for testing, e.g. 2026-10-30T23:00:00Z
    if override:
        return dt.datetime.fromisoformat(override.replace("Z", "+00:00")).astimezone(UTC)
    return dt.datetime.now(UTC)


# ---------------- helpers ----------------
def week_end_guess(now):
    """Yahoo weeks run Monday-Sunday (Pacific)."""
    d = now.astimezone(timing.PT).date()
    return d + dt.timedelta(days=6 - d.weekday())


def team_games(games, team, now, until_date=None):
    t = espn.norm_team(team)
    out = [g for g in games if t in (g["home"], g["away"]) and g["state"] == "pre" and g["tip_utc"] > now]
    if until_date:
        out = [g for g in out if g["et_date"] <= until_date.isoformat()]
    return sorted(out, key=lambda g: g["tip_utc"])


def plays_soon(games, team, now):
    nxt = team_games(games, team, now)
    return bool(nxt) and nxt[0]["tip_utc"] - now < SOON


def espn_info(injuries, name):
    return injuries.get(espn.norm_name(name))


# ---------------- triggers ----------------
def find_triggers(state, now, my_players, rosters, injuries, games, fa_keys):
    """Compare against the last run. Returns (triggers, new_signatures)."""
    triggers = []
    my_keys = {p["key"] for p in my_players}
    sigs = {}

    for tk, team in rosters.items():
        for p in team["players"]:
            inj = espn_info(injuries, p["name"]) or {}
            sig = f"{p['status']}|{inj.get('status', '')}|{inj.get('updated', '')}"
            sigs[p["key"]] = sig
            old = state.get("sigs", {}).get(p["key"])
            if old is None or old == sig or not plays_soon(games, p["team"], now):
                continue
            if p["key"] in my_keys:
                triggers.append(f"YOUR player {p['name']} ({p['team']}) status changed: "
                                f"Yahoo '{p['status'] or 'healthy'}', ESPN '{inj.get('status', 'healthy')}'"
                                f"{' - ' + inj['news'] if inj.get('news') else ''}")
            elif p["status"] in ("O", "INJ") or inj.get("status") == "Out":
                triggers.append(f"Rostered player {p['name']} ({p['team']}, on '{team['name']}') is now OUT"
                                f"{' - ' + inj['news'] if inj.get('news') else ''}. "
                                f"Check if a {p['team']} teammate who gains minutes is a free agent.")

    # Players who were on a league roster last run and now aren't = just dropped.
    prev_rostered = set(state.get("rostered", []))
    now_rostered = {p["key"] for t in rosters.values() for p in t["players"]}
    dropped = sorted(prev_rostered - now_rostered) if prev_rostered else []
    for k in dropped:
        name = state.get("names", {}).get(k, k)
        triggers.append(f"{name} was just DROPPED by a leaguemate and is now a free agent (no waivers).")

    return triggers, sigs, sorted(now_rostered), dropped


# ---------------- full context for Claude ----------------
def build_context(y, now, rosters, injuries, games, fas_lastweek, extra_keys, kind, triggers, state,
                  slate=None):
    settings = y.load_settings()
    adds = y.adds_used()
    mu = y.matchup() or {}
    week_end = dt.date.fromisoformat(mu["week_end"]) if mu.get("week_end") else week_end_guess(now)

    # Make sure the schedule covers the whole fantasy week.
    have = {g["et_date"] for g in games}
    d = now.astimezone(timing.ET).date()
    while d <= week_end:
        if d.isoformat() not in have:
            games = games + espn.games_on(d)
        d += dt.timedelta(days=1)

    fas_season = y.free_agents("season", 40)
    fa = {p["key"]: p for p in fas_lastweek + fas_season}
    mine = rosters[y.team_key]["players"]
    opp_key = (mu.get("opponent") or {}).get("team_key")
    opp = rosters.get(opp_key, {}).get("players", [])

    keys = [p["key"] for p in mine + opp] + list(fa) + list(extra_keys)
    season = y.stats(keys, "average_season")
    lastweek = y.stats(keys, "lastweek")
    for k in extra_keys:  # just-dropped players may not be in the top free-agent lists
        if k not in fa and k in season:
            fa[k] = season[k]["info"]

    def line(p):
        s = season.get(p["key"], {})
        lw = lastweek.get(p["key"], {})
        gl = team_games(games, p["team"], now, week_end)
        nxt = timing.fmt_local(gl[0]["tip_utc"]) if gl else "none this week"
        inj = espn_info(injuries, p["name"])
        parts = [
            f"{p['name']} ({p['team']}, {p['positions']})",
            f"slot={p['slot']}" if p.get("slot") else None,
            f"status={p['status'] or 'healthy'}",
            f"{s.get('fp', '?')} FP/G season",
            f"{lw.get('fp', '?')} FP last week" + (f" in {int(lw['line']['GP'])} G" if lw.get("line", {}).get("GP") else ""),
            f"{len(gl)} games left this week",
            f"next game {nxt} KST",
            f"injury: {inj['status']} - {inj['injury']} - {inj['news'][:220]}" if inj else None,
        ]
        return " | ".join(x for x in parts if x)

    fa_sorted = sorted(fa.values(), key=lambda p: -(season.get(p["key"], {}).get("fp") or 0))
    local_now = now.astimezone(timing.LOCAL)
    out = [
        f"NOW: {local_now:%a %Y-%m-%d %H:%M} KST (Pacific: {now.astimezone(timing.PT):%a %H:%M})",
        f"Scoring: {settings['scoring']}",
        f"Fantasy week {mu.get('week', '?')}: {mu.get('week_start', '?')} to {mu.get('week_end', '?')}. "
        f"Adds used this week: {adds.get('adds_used', '?')} of 6.",
    ]
    if mu:
        me, op = mu.get("me") or {}, mu.get("opponent") or {}
        out.append(f"MATCHUP: Andy ({me.get('name')}) {me.get('points')} pts (proj {me.get('projected')}) vs "
                   f"{op.get('name')} {op.get('points')} pts (proj {op.get('projected')})")
    if slate:
        out.append(f"TONIGHT'S SLATE: first tip {timing.fmt_local(slate[1])} KST "
                   f"({len([g for g in games if g['et_date'] == slate[0]])} games).")
    out.append("\nANDY'S ROSTER:")
    out += ["- " + line(p) for p in mine]
    if opp:
        out.append(f"\nOPPONENT'S ROSTER ({rosters[opp_key]['name']}):")
        out += ["- " + line(p) for p in opp]
    out.append("\nAVAILABLE FREE AGENTS (sorted by season FP/G):")
    out += ["- " + line(p) for p in fa_sorted]
    if triggers:
        out.append("\nTRIGGERS (what just changed):")
        out += ["- " + t for t in triggers]
    recent = state.get("recent_alerts", [])[-5:]
    if recent:
        out.append("\nALERTS ALREADY SENT RECENTLY (don't repeat unless something changed):")
        out += [f"- [{a['at']}] {a['text'][:300]}" for a in recent]
    return "\n".join(out)


# ---------------- main ----------------
def run(dry=False, force=None):
    now = now_utc()
    state = load_state()

    injuries = espn.injuries()
    et_today = now.astimezone(timing.ET).date()
    games = espn.schedule(et_today - dt.timedelta(days=1), max(week_end_guess(now), et_today + dt.timedelta(days=1)))

    y = Yahoo()
    if state.get("team_key"):
        y.team_key, y.league_key = state["team_key"], state["league_key"]
    else:
        y.find_team()
    rosters = y.all_rosters()
    fas = y.free_agents("lastweek", 25)
    my_players = rosters[y.team_key]["players"]

    triggers, sigs, rostered, dropped = find_triggers(
        state, now, my_players, rosters, injuries, games, {p["key"] for p in fas})
    if not state.get("sigs"):  # first run: just learn the baseline, don't alert on everything
        triggers, dropped = [], []

    jobs = []
    reset_key = timing.reset_alert_due(now, state)
    pretip = timing.pretip_due(now, games, state)
    if force == "reset" or reset_key:
        jobs.append(("reset", None))
    if force == "pretip" or pretip:
        jobs.append(("pretip", pretip or timing.next_slate(now, games)))
    if triggers and not jobs:
        jobs.append(("live", None))

    for kind, slate in jobs:
        ctx = build_context(y, now, rosters, injuries, games, fas, dropped, kind, triggers, state, slate)
        msg = brain.write(kind, ctx)
        if dry:
            print(f"===== {kind} context =====\n{ctx}\n===== {kind} message =====\n{msg}")
            continue
        if msg:
            telegram.send(msg)
            state.setdefault("recent_alerts", []).append({"at": timing.fmt_local(now), "text": msg})
            state["recent_alerts"] = state["recent_alerts"][-10:]
        if kind == "reset":
            state["reset_sent"] = reset_key or timing.next_reset(now).astimezone(timing.PT).date().isoformat()
        if kind == "pretip" and slate and slate[0]:
            state["pretip_sent"] = slate[0]
    if not jobs:
        print(f"{now:%H:%M}Z: nothing new.")

    names = {p["key"]: p["name"] for t in rosters.values() for p in t["players"]}
    state.update(team_key=y.team_key, league_key=y.league_key, sigs=sigs, rostered=rostered,
                 names={**state.get("names", {}), **names}, last_run=now.isoformat())
    if not dry:
        save_state(state)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", choices=["reset", "pretip"])
    args = ap.parse_args()
    try:
        run(dry=args.dry_run, force=args.force)
    except Exception as e:
        traceback.print_exc()
        # Tell Andy once in a while if the agent is broken, instead of failing silently.
        state = load_state()
        now = now_utc()
        last = state.get("last_error_alert")
        if not args.dry_run and (not last or now - dt.datetime.fromisoformat(last) > dt.timedelta(hours=12)):
            try:
                telegram.send(f"⚠️ Fantasy Agent hit an error and skipped this check:\n{str(e)[:300]}")
                state["last_error_alert"] = now.isoformat()
                save_state(state)
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
