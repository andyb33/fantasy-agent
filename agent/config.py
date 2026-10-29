"""League settings and personal preferences. Edit freely."""

LEAGUE_ID = "99840"  # basketball.fantasysports.yahoo.com/nba/99840

# Fallback scoring (Yahoo stat_id -> points). The live values are read from
# your league settings when Yahoo access works; these are only a backup.
SCORING = {
    12: 1.0,   # Points
    15: 1.2,   # Total rebounds
    16: 1.5,   # Assists
    17: 3.0,   # Steals
    18: 3.0,   # Blocks
    19: -1.0,  # Turnovers
}
STAT_NAMES = {0: "GP", 12: "PTS", 15: "REB", 16: "AST", 17: "STL", 18: "BLK", 19: "TO"}

LEAGUE_NOTES = """\
- 8-team Yahoo NBA league, Head-to-Head Points, weekly matchups (Mon-Sun, Pacific time).
- Scoring: PTS 1, REB 1.2, AST 1.5, STL 3, BLK 3, TO -1. Bigs who rebound and block are very valuable.
- 6 adds per week. No waivers: free agents are added instantly, first come first served.
- Added players are active right away (the same day), so a pickup before tip-off counts that night.
- Injured players can be added straight to the roster. 4 IL spots. Yahoo usually only allows
  Out/Injured players in IL slots; a healthy or day-to-day player left on IL can block adds.
- Daily lineups; the fantasy day resets at midnight Pacific.
"""

# Used only until Yahoo approves API access (then your roster is read live).
# (name, NBA team, lineup slot). Update when you make moves.
MANUAL_ROSTER = [
    ("Darius Acuff Jr.", "SAC", "PG"),
    ("Ty Jerome", "MEM", "SG"),
    ("Jaylen Brown", "PHI", "G"),
    ("Jalen Johnson", "ATL", "SF"),
    ("Karl-Anthony Towns", "NYK", "PF"),
    ("Paul Reed", "DET", "F"),
    ("Isaiah Hartenstein", "OKC", "C"),
    ("Giannis Antetokounmpo", "MIA", "C"),
    ("Derik Queen", "NOP", "Util"),
    ("Peyton Watson", "CLE", "Util"),
    ("Trae Young", "WAS", "BN"),
    ("Stephon Castle", "SAS", "BN"),
    ("Ajay Mitchell", "OKC", "BN"),
    ("Matas Buzelis", "CHI", "BN"),
    ("Payton Pritchard", "BOS", "BN"),
    ("Paul George", "BOS", "BN"),
    ("Jalen Suggs", "ORL", "IL"),
    ("Ivica Zubac", "IND", "IL"),
    ("Jusuf Nurkic", "UTA", "IL"),
]

# Where you live and when you sleep (alerts still buzz during sleep, but the
# pre-tip brief is moved earlier so it lands before you go to bed).
USER_TZ = "Asia/Seoul"
SLEEP_START_HOUR = 2   # 2AM local
SLEEP_END_HOUR = 8     # 8AM local
NIGHT_BRIEF_TIME = (1, 30)  # send the brief at 1:30AM when the normal time falls in sleep

# Timing
RESET_ALERT_MINUTES_BEFORE = 30   # reset alert ~30 min before midnight Pacific
PRETIP_MINUTES_BEFORE = 60        # pre-tip brief ~1 hour before the first game

# Live-alert sensitivity
FA_UPGRADE_MARGIN = 2.0  # a free agent must beat your weakest player by this many FP/G

# Models: a stronger model for the two daily briefs, a cheaper one for live alerts.
BRIEF_MODEL = "claude-sonnet-5-5"
ALERT_MODEL = "claude-haiku-5-5"
