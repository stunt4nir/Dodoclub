# Club Dodo — Product Requirements (MVP v1)

## Vision
A custom matchday app for amateur football team **Club Dodo**: organize fixtures, vote availability, auto-generate balanced lineups on a tactical pitch view, and track player stats across seasons.

## Core Features (shipped)
1. **Authentication** — JWT Bearer tokens (AsyncStorage); register, login, /me
2. **Player Profiles** — Editable name, shirt number (1-99), profile picture (base64 via gallery pick)
3. **Match Voting** — Any user can create a fixture (title, date/time, location, team size 3–11). Other players vote **Yes / Reserve / No**.
4. **Auto-Generated Lineup** — Admin/editor triggers a snake-draft lineup from `yes` voters ranked by rating, splitting into Team Dodo vs Team Orange. Overflow + `reserve` voters go to reserves. Rendered on a tactical pitch with formation markers per team size.
5. **Result Recording** — Editor enters final score + per-player goals/assists. Stats & `matches_played` update automatically for participants. Editing a result safely reverts prior contributions.
6. **Player Rating (transparent)** — `rating = goals × 3 + assists × 2 + matches_played`.
7. **Club Customisation** — Admin can update club name & logo (base64).
8. **Squad Leaderboard** — All players ranked by rating with quick stats.
9. **Match History** — Past matches with scores and lineups preserved.
10. **Access Control** — First seeded user is admin; admin can grant "match-editor" access to any player.

## Architecture
- **Backend**: FastAPI + Motor (async MongoDB). All routes prefixed `/api`. UUID string ids only; `_id` never returned.
- **Frontend**: Expo Router with 4 bottom tabs (Home, Squad, Matches, Profile) and `/match/[id]` detail screen.
- **Theme**: Performance-Pro dark archetype, zinc surfaces + Blaze Orange (`#FF4500`) accent. Uppercase athletic typography.

## Smart Enhancement (shareability hook)
The tactical **pitch-view lineup** is screenshot-worthy and designed to be shared in the team group chat the moment it's generated — driving repeat usage and new sign-ups ahead of every fixture.

## Seeded Admin
- Email: `admin@clubdodo.com`
- Password: `dodo2026`
