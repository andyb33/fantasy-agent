# Fantasy Agent

A personal assistant for one Yahoo Fantasy NBA league (8 teams, H2H points). It checks the league every 15 minutes and sends Telegram alerts when a move is worth making. It only reads data; every move is made by hand in the Yahoo app.

## What it sends

- **Reset brief**: about 30 minutes before the fantasy day resets at midnight Pacific. That's 3:30PM KST during US daylight time, and 4:30PM KST from November to March.
- **Pre-tip brief**: about an hour before the first NBA game of the night. If that time falls between 2AM and 8AM KST, the brief is sent at 1:30AM KST instead.
- **Live alerts**: sent any time one of these happens:
  - One of your players' injury status changes before his game.
  - A rostered starter is ruled out, so his backup may be worth adding.
  - A leaguemate drops a useful player.

  Claude decides whether each change is worth alerting you about. Most changes aren't.

## How it works

Each run follows the same steps:

1. A quick check reads your league's rosters and the top free agents from Yahoo, plus injury news from ESPN. It compares them with the last run.
2. The agent keeps its memory of the last run in `state.json` on the `state` branch.
3. If nothing changed and no brief is due, the run stops there. No AI is used and nothing is sent.
4. Otherwise, it builds the full picture and asks Claude what to do. The full picture covers your roster, your opponent's roster, the free agents, games left this week, adds used and the matchup score.
5. If Claude recommends something, it sends you a Telegram message.

## Files

| File | What it does |
|---|---|
| `agent/config.py` | League notes, sleep hours, timing and alert sensitivity. **Edit this to change behavior.** |
| `agent/main.py` | One run: checks for changes and decides what to send. |
| `agent/yahoo.py` | Read-only Yahoo Fantasy API client. |
| `agent/espn.py` | NBA schedule and injury news. |
| `agent/timing.py` | Decides when the briefs are due. |
| `agent/brain.py` | The instructions given to Claude. |
| `agent/telegram.py` | Sends the messages. |

## Secrets

Add these in Settings → Secrets and variables → Actions:

- `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET`, `YAHOO_REFRESH_TOKEN`
- `ANTHROPIC_API_KEY`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## Running it by hand

1. Go to the **Actions** tab and open **Fantasy Agent**.
2. Click **Run workflow**.
3. Optionally:
   - Set `force` to `reset` or `pretip` to get a brief right away.
   - Tick **dry run** to print the brief in the log without sending it.
