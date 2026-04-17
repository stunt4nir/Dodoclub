# Club Dodo — Product Requirements (v1.1)

## Vision
Custom matchday app for amateur football team **Club Dodo**: organize fixtures, vote availability, auto-generate balanced lineups on a tactical pitch view, track player stats and league standings across seasons.

## Features
1. **Authentication** — JWT Bearer tokens (AsyncStorage); register, login, /me, **forgot-password + reset-password** (dev-mode 6-digit code shown on screen, single-use, 1-hour expiry, no email enumeration).
2. **Player Profiles** — Editable name, shirt number (1-99), **preferred position (GK / DEF / MID / FWD / ANY)**, profile picture (base64 via gallery pick).
3. **Match Voting** — Any user can create a fixture with **exact date & kick-off time (HH:MM)**, title, location, team size 3–11. Other players vote **Yes / Reserve / No**.
4. **Match Types**
   - **Friendly** — casual, no points
   - **League** — Win = 3 pts · Draw = 1 pt · Loss = 0 pts, tallied per participant
5. **Team Colours** — Default teams **Team Red** and **Team Black**; optional **Team White** as a third team (friendly matches only, rotating substitute team for larger squads).
6. **Auto-Generated Lineup** — Editor triggers snake-draft lineup from `yes` voters ranked by rating, splitting into 2 teams (Red / Black) or 3 teams (Red / Black / White). Overflow + `reserve` voters → reserves. Rendered on a tactical pitch with formation markers per team size.
7. **Result Recording** — Editor enters final score per team (incl. 3rd team if enabled) + per-player goals/assists. Stats, `matches_played`, and league W/D/L/points update automatically. Editing or deleting a result safely reverts prior contributions.
8. **Player Rating (transparent)** — `rating = goals × 3 + assists × 2 + matches_played`.
9. **Club Customisation** — Admin can update club name & logo (base64).
10. **Squad Leaderboard** — Tabbed view: **FORM** (sorted by rating) or **LEAGUE** (sorted by league points) with W/D/L/PTS column.
11. **Match History + Delete** — Past matches preserved with scores and lineups. Editors can delete any match (with safe stat reversal) from the match list or detail.
12. **Access Control** — First seeded user = admin; admin grants "match-editor" access to any player.

## Architecture
- Backend: FastAPI + Motor (async MongoDB), UUID string ids, no `_id` in responses.
- Frontend: Expo Router, 4 tabs + `/match/[id]` detail.
- Theme: Dark Performance-Pro + Blaze Orange accent (#FF4500).

## Smart Enhancement
Tactical pitch-view lineup remains the shareability hook — screenshot and drop into team chat on matchday. League table adds return-visit cadence ("Am I still top?").

## Seeded Admin
- Email: `admin@clubdodo.com`  
- Password: `dodo2026`
