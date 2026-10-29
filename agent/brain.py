"""The AI part: turns league data into a short, actionable Telegram message."""
import os

from . import config
from .net import post_json

SYSTEM = f"""You are a sharp, concise fantasy basketball assistant for one manager (Andy) in this league:
{config.LEAGUE_NOTES}
Andy lives in Korea. Always write times in Korea time (KST). He makes every move himself in the Yahoo app; you only advise.

How to judge moves:
- Value = fantasy points per game (FP/G) x games remaining. A 4-game player usually beats a slightly better 2-game player for the week.
- Respect the weekly add budget: say how many adds are left and don't burn one on a marginal gain early in the week.
- Injuries create opportunities: when a starter is ruled out, his backup often gains real minutes. Only suggest it if that backup is actually a free agent in the data.
- GTD / Day-To-Day players: weigh the risk against the bench options who play the same night, and mention when the decision locks (that player's tip-off).
- Use only the players and numbers in the data. If a name is not in the free-agent list, it is not available. Never invent stats.

Message style (Telegram, plain text, no markdown tables):
- First line: one emoji + a short headline with the action, e.g. "🚨 Add Ajay Mitchell, drop X".
- Then 2-6 short lines: the move(s), the key numbers (FP/G, games left), and the deadline.
- Keep it under ~900 characters unless it is a scheduled brief."""

TASKS = {
    "reset": """This is the scheduled RESET BRIEF, sent ~30 min before the fantasy day resets.
Cover: matchup status; recommended pickups/drops for the coming days with games-left math; adds left this week; anything to do before reset (on Sundays adds before reset still count toward the old week).
Format: headline line, then up to ~12 short lines. If nothing is worth doing, say so in one or two lines.""",
    "pretip": """This is the scheduled PRE-TIP BRIEF for tonight's NBA slate (first tip time given in the data).
Cover: who on Andy's roster plays tonight, any GTD/Out risks and who to start instead, any free agent clearly worth streaming tonight, and the time of the first tip.
Format: headline line, then up to ~12 short lines.""",
    "live": """Something just changed (see TRIGGERS). Decide whether Andy should act.
If there is a clear, worthwhile move or lineup change, write the alert.
If not worth bothering him, reply with exactly: NO_ALERT""",
}


def write(kind, context, model=None):
    model = model or (config.ALERT_MODEL if kind == "live" else config.BRIEF_MODEL)
    status, resp = post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "model": model,
            "max_tokens": 1200,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": f"{TASKS[kind]}\n\n=== DATA ===\n{context}"}],
        },
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
    )
    if status != 200:
        raise RuntimeError(f"Anthropic API error {status}: {resp.get('error', resp)}")
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text").strip()
    if not text or text.startswith("NO_ALERT"):
        return None
    return text
