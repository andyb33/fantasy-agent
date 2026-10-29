"""When the fixed briefs are due. Pure functions, easy to test."""
import datetime as dt
from zoneinfo import ZoneInfo

from . import config

UTC = dt.timezone.utc
PT = ZoneInfo("America/Los_Angeles")
ET = ZoneInfo("America/New_York")
LOCAL = ZoneInfo(config.USER_TZ)


def next_reset(now):
    """Next midnight Pacific after `now` (aware datetime)."""
    pt = now.astimezone(PT)
    nxt = dt.datetime.combine(pt.date() + dt.timedelta(days=1), dt.time(0, 0), PT)
    return nxt.astimezone(UTC)


def reset_alert_due(now, state):
    """Due in the window ~40 min before reset (GitHub can run late). Returns the
    fantasy date it is for, or None."""
    reset = next_reset(now)
    minutes_left = (reset - now).total_seconds() / 60
    key = reset.astimezone(PT).date().isoformat()
    if 0 < minutes_left <= config.RESET_ALERT_MINUTES_BEFORE + 10 and state.get("reset_sent") != key:
        return key
    return None


def pretip_target(first_tip):
    """An hour before the first tip, unless that falls while you sleep: then the
    night before at NIGHT_BRIEF_TIME."""
    t = first_tip - dt.timedelta(minutes=config.PRETIP_MINUTES_BEFORE)
    local = t.astimezone(LOCAL)
    if config.SLEEP_START_HOUR <= local.hour < config.SLEEP_END_HOUR:
        h, m = config.NIGHT_BRIEF_TIME
        t = local.replace(hour=h, minute=m, second=0, microsecond=0).astimezone(UTC)
    return t


def next_slate(now, games):
    """(et_date, first_tip) of the next NBA night that hasn't tipped off yet."""
    upcoming = [g for g in games if g["tip_utc"] > now and g["state"] == "pre"]
    if not upcoming:
        return None, None
    et_date = min(upcoming, key=lambda g: g["tip_utc"])["et_date"]
    first_tip = min(g["tip_utc"] for g in games if g["et_date"] == et_date)
    return et_date, first_tip


def pretip_due(now, games, state):
    et_date, first_tip = next_slate(now, games)
    if not et_date or first_tip <= now:
        return None
    if now >= pretip_target(first_tip) and state.get("pretip_sent") != et_date:
        return et_date, first_tip
    return None


def fmt_local(t):
    return t.astimezone(LOCAL).strftime("%a %H:%M")
