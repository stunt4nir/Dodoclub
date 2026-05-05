"""
Backend tests for the new live in-match scoring feature.

Covers:
  1. Endpoint basics (auth/role, score updates, pydantic bounds)
  2. Cannot update a finalised match
  3. Tournament standings reflect live scores (the main test)
  4. Purity of live-score (no stat side-effects)
  5. Cleanup
"""

import os
import sys
import uuid
from typing import Optional, Dict, Any, List

import requests


def _load_backend_url() -> str:
    fe_env = "/app/frontend/.env"
    url = None
    try:
        with open(fe_env, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("EXPO_PUBLIC_BACKEND_URL"):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except Exception as e:
        print(f"Could not read {fe_env}: {e}")
    if not url:
        url = os.environ.get("REACT_APP_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    if not url:
        raise RuntimeError("No backend URL configured")
    return url.rstrip("/")


BASE = _load_backend_url() + "/api"
print(f"[INFO] Base URL: {BASE}")

ADMIN_EMAIL = "admin@clubdodo.com"
ADMIN_PASSWORD = "dodo2026"

PASS = 0
FAIL = 0
FAILURES: List[str] = []


def check(cond: bool, label: str, details: Any = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        msg = f"FAIL  {label} :: {details}"
        print(f"  {msg}")
        FAILURES.append(msg)


def _hdrs(token: Optional[str] = None) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


print("\n== 0. Auth setup ==")
r = requests.post(f"{BASE}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
check(r.status_code == 200, "admin login 200", r.text[:200])
admin_token = r.json()["token"]
admin_user = r.json()["user"]
print(f"  admin id: {admin_user['id']}")

SUF = uuid.uuid4().hex[:6]
test_users = []
positions = ["CB", "LB", "CDM", "CAM", "LW", "ST"]
for i in range(1, 7):
    email = f"livetest_{SUF}_{i}@example.com"
    pwd = "test1234!"
    rr = requests.post(
        f"{BASE}/auth/register",
        json={
            "email": email,
            "password": pwd,
            "name": f"LiveTester {SUF}-{i}",
            "shirt_number": 10 + i,
            "preferred_positions": [positions[i - 1]],
        },
        timeout=30,
    )
    check(rr.status_code == 200, f"register user {i}", rr.text[:200])
    test_users.append({
        "id": rr.json()["user"]["id"],
        "email": email,
        "password": pwd,
        "token": rr.json()["token"],
    })

regular_token = test_users[0]["token"]


def create_tournament_with_rosters() -> Dict[str, Any]:
    body = {
        "name": f"Live Cup {SUF}",
        "team_names": ["Red", "Black", "White"],
        "team_size": 5,
        "match_type": "friendly",
        "team_rosters": {
            "Red":   [test_users[0]["id"], test_users[1]["id"]],
            "Black": [test_users[2]["id"], test_users[3]["id"]],
            "White": [test_users[4]["id"], test_users[5]["id"]],
        },
    }
    r = requests.post(f"{BASE}/tournaments", json=body, headers=_hdrs(admin_token), timeout=30)
    assert r.status_code == 200, f"tournament create failed: {r.status_code} {r.text}"
    return r.json()


print("\n== 1. Endpoint basics ==")
t = create_tournament_with_rosters()
tid = t["id"]
fixtures = t["fixtures"]
assert len(fixtures) == 3
m1 = fixtures[0]["match_id"]
home_team = fixtures[0]["home"]
away_team = fixtures[0]["away"]
print(f"  tournament={tid} fixture[0]={m1} ({home_team} vs {away_team})")

# Initial standings & fixture state
check(all(s["P"] == 0 for s in t["standings"]),
      "initial standings all zeros",
      t["standings"])
check(all(fx["live"] is False and fx["played"] is False for fx in t["fixtures"]),
      "initial fixtures all live=False played=False",
      t["fixtures"])

# 1a unauth → 401
r = requests.post(f"{BASE}/matches/{m1}/live-score", json={"team_a_score": 1, "team_b_score": 0}, timeout=30)
check(r.status_code == 401, "unauth live-score → 401", f"got {r.status_code}: {r.text[:200]}")

# 1b regular non-editor → 403
r = requests.post(f"{BASE}/matches/{m1}/live-score",
                  json={"team_a_score": 1, "team_b_score": 0},
                  headers=_hdrs(regular_token), timeout=30)
check(r.status_code == 403, "non-editor live-score → 403", f"got {r.status_code}: {r.text[:200]}")

# Confirm initial match status
r = requests.get(f"{BASE}/matches/{m1}", headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 200 and r.json().get("status") == "scheduled",
      "fixture starts as 'scheduled'", f"got {r.status_code} status={r.json().get('status')}")

# 1c admin 0-0 on fresh scheduled match → 200, status stays scheduled
r = requests.post(f"{BASE}/matches/{m1}/live-score",
                  json={"team_a_score": 0, "team_b_score": 0},
                  headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 200, "admin live-score 0-0 → 200", r.text[:200])
body0 = r.json() if r.status_code == 200 else {}
check(body0.get("status") == "scheduled",
      "status remains 'scheduled' after 0-0", f"got {body0.get('status')}")
tr = requests.get(f"{BASE}/tournaments/{tid}", headers=_hdrs(admin_token), timeout=30).json()
fx0 = tr["fixtures"][0]
check(fx0["score_home"] in (None, 0) and fx0["score_away"] in (None, 0),
      "after 0-0 no live contribution to standings (fx not counted)",
      f"fx live={fx0['live']} played={fx0['played']} s_home={fx0['score_home']} s_away={fx0['score_away']}")
check(all(s["P"] == 0 for s in tr["standings"]),
      "standings all P=0 after 0-0", tr["standings"])

# 1d admin 1-0 → status flips to in_progress
r = requests.post(f"{BASE}/matches/{m1}/live-score",
                  json={"team_a_score": 1, "team_b_score": 0},
                  headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 200, "admin live-score 1-0 → 200", r.text[:200])
body1 = r.json() if r.status_code == 200 else {}
check(body1.get("status") == "in_progress",
      "status flips to 'in_progress' on first goal", f"got {body1.get('status')}")
tr = requests.get(f"{BASE}/tournaments/{tid}", headers=_hdrs(admin_token), timeout=30).json()
fx0 = tr["fixtures"][0]
check(fx0["live"] is True and fx0["played"] is False,
      "fixture[0] live=True played=False after 1-0", fx0)
check(fx0["score_home"] == 1 and fx0["score_away"] == 0,
      "fixture[0] score_home=1 score_away=0", fx0)

# Standings after live 1-0
def stand_of(tr_obj, team):
    for row in tr_obj["standings"]:
        if row["team"] == team:
            return row
    return None

sh_row = stand_of(tr, home_team)
sa_row = stand_of(tr, away_team)
third_team = [n for n in tr["team_names"] if n not in (home_team, away_team)][0]
st_row = stand_of(tr, third_team)
check(sh_row["P"] == 1 and sh_row["W"] == 1 and sh_row["GF"] == 1 and sh_row["GA"] == 0
      and sh_row["GD"] == 1 and sh_row["Pts"] == 3,
      f"home {home_team}: P1 W1 GF1 GA0 GD1 Pts3 (live)", sh_row)
check(sa_row["P"] == 1 and sa_row["L"] == 1 and sa_row["GF"] == 0 and sa_row["GA"] == 1
      and sa_row["GD"] == -1 and sa_row["Pts"] == 0,
      f"away {away_team}: P1 L1 GF0 GA1 GD-1 Pts0 (live)", sa_row)
check(st_row["P"] == 0 and st_row["Pts"] == 0,
      f"third team {third_team}: all zeros", st_row)

# 1e admin 1-2 → score updates, status stays in_progress
r = requests.post(f"{BASE}/matches/{m1}/live-score",
                  json={"team_a_score": 1, "team_b_score": 2},
                  headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 200, "admin live-score 1-2 → 200", r.text[:200])
body2 = r.json() if r.status_code == 200 else {}
check(body2.get("status") == "in_progress",
      "status still 'in_progress'", f"got {body2.get('status')}")
tr = requests.get(f"{BASE}/tournaments/{tid}", headers=_hdrs(admin_token), timeout=30).json()
fx0 = tr["fixtures"][0]
check(fx0["score_home"] == 1 and fx0["score_away"] == 2,
      "fixture[0] score 1-2 via tournament GET", fx0)

# 1f upper cap: 100 → 422
r = requests.post(f"{BASE}/matches/{m1}/live-score",
                  json={"team_a_score": 100, "team_b_score": 0},
                  headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 422, "team_a_score=100 → 422 (le=99)", f"got {r.status_code}: {r.text[:200]}")

# 1g lower cap: -1 → 422
r = requests.post(f"{BASE}/matches/{m1}/live-score",
                  json={"team_a_score": -1, "team_b_score": 0},
                  headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 422, "team_a_score=-1 → 422 (ge=0)", f"got {r.status_code}: {r.text[:200]}")


print("\n== 3e. Live 1-1 (tied draw) on m1 ==")
r = requests.post(f"{BASE}/matches/{m1}/live-score",
                  json={"team_a_score": 1, "team_b_score": 1},
                  headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 200, "live-score 1-1 → 200", r.text[:200])
tr = requests.get(f"{BASE}/tournaments/{tid}", headers=_hdrs(admin_token), timeout=30).json()
fx0 = tr["fixtures"][0]
check(fx0["live"] is True and fx0["score_home"] == 1 and fx0["score_away"] == 1,
      "fixture[0] live=True score 1-1", fx0)
sh_row = stand_of(tr, home_team); sa_row = stand_of(tr, away_team)
check(sh_row["P"] == 1 and sh_row["D"] == 1 and sh_row["GF"] == 1 and sh_row["GA"] == 1
      and sh_row["GD"] == 0 and sh_row["Pts"] == 1,
      f"home draw: P1 D1 GF1 GA1 GD0 Pts1", sh_row)
check(sa_row["P"] == 1 and sa_row["D"] == 1 and sa_row["GF"] == 1 and sa_row["GA"] == 1
      and sa_row["GD"] == 0 and sa_row["Pts"] == 1,
      f"away draw: P1 D1 GF1 GA1 GD0 Pts1", sa_row)


print("\n== 4. Purity of live-score (no stat side-effects) ==")
r = requests.get(f"{BASE}/auth/me", headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 200, "GET /auth/me admin → 200", r.text[:200])
me_before = r.json()
watch_fields = ["goals", "assists", "matches_played", "league_points", "rating", "wins", "draws", "losses"]
baseline = {k: me_before.get(k) for k in watch_fields}
print(f"  baseline: {baseline}")

for sa, sb in [(2, 2), (3, 2), (3, 3)]:
    r = requests.post(f"{BASE}/matches/{m1}/live-score",
                      json={"team_a_score": sa, "team_b_score": sb},
                      headers=_hdrs(admin_token), timeout=30)
    check(r.status_code == 200, f"live-score {sa}-{sb} → 200", r.text[:200])

r = requests.get(f"{BASE}/auth/me", headers=_hdrs(admin_token), timeout=30)
me_after = r.json()
after = {k: me_after.get(k) for k in watch_fields}
check(baseline == after,
      "admin career stats UNCHANGED after live-score bumps",
      f"before={baseline} after={after}")

# Also verify none of the rostered players had their stats changed
for u in test_users[:2]:  # check the two Red players
    rr = requests.post(f"{BASE}/auth/login", json={"email": u["email"], "password": u["password"]}, timeout=30)
    if rr.status_code == 200:
        user_after = rr.json()["user"]
        check(all((user_after.get(k) or 0) == 0 for k in ("goals", "assists", "matches_played", "league_points")),
              f"roster player {u['email'].split('@')[0]}: stats still 0 after live-score",
              {k: user_after.get(k) for k in ("goals", "assists", "matches_played", "league_points")})


print("\n== 2. Cannot update a finalised match ==")
# Record final 3-1 result (matches review scenario 3f — verifies flip from live→final)
r = requests.post(f"{BASE}/matches/{m1}/result",
                  json={"team_a_score": 3, "team_b_score": 1, "stats": []},
                  headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 200, "record final result 3-1 → 200", r.text[:200])
res_body = r.json() if r.status_code == 200 else {}
check(res_body.get("status") == "played", "match status='played' after result", res_body.get("status"))

# Attempt live-score on played → 400
r = requests.post(f"{BASE}/matches/{m1}/live-score",
                  json={"team_a_score": 9, "team_b_score": 9},
                  headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 400, "live-score on played match → 400",
      f"got {r.status_code}: {r.text[:200]}")
detail = ""
try:
    detail = (r.json().get("detail") or "")
except Exception:
    pass
check("finalis" in detail.lower() or "already" in detail.lower(),
      "400 detail mentions finalised/already", detail)


print("\n== 3f. Tournament standings refresh to final result ==")
tr = requests.get(f"{BASE}/tournaments/{tid}", headers=_hdrs(admin_token), timeout=30).json()
fx0 = tr["fixtures"][0]
check(fx0["played"] is True and fx0["live"] is False,
      "fixture[0] played=true live=false after final result", fx0)
check(fx0["score_home"] == 3 and fx0["score_away"] == 1,
      "fixture[0] score_home=3 score_away=1 (final)", fx0)

sh_row = stand_of(tr, home_team); sa_row = stand_of(tr, away_team)
check(sh_row["P"] == 1 and sh_row["W"] == 1 and sh_row["L"] == 0 and sh_row["D"] == 0
      and sh_row["GF"] == 3 and sh_row["GA"] == 1 and sh_row["GD"] == 2 and sh_row["Pts"] == 3,
      f"home {home_team} final: P1 W1 GF3 GA1 GD2 Pts3", sh_row)
check(sa_row["P"] == 1 and sa_row["L"] == 1 and sa_row["W"] == 0 and sa_row["D"] == 0
      and sa_row["GF"] == 1 and sa_row["GA"] == 3 and sa_row["GD"] == -2 and sa_row["Pts"] == 0,
      f"away {away_team} final: P1 L1 GF1 GA3 GD-2 Pts0", sa_row)


print("\n== 3g. Bonus: trigger live on fixture[1] alongside played fixture[0] ==")
m2 = tr["fixtures"][1]["match_id"]
fx1_home = tr["fixtures"][1]["home"]
fx1_away = tr["fixtures"][1]["away"]
print(f"  m2={m2} ({fx1_home} vs {fx1_away}) → 0-2 live")
r = requests.post(f"{BASE}/matches/{m2}/live-score",
                  json={"team_a_score": 0, "team_b_score": 2},
                  headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 200, "live-score 0-2 on m2 → 200", r.text[:200])

tr = requests.get(f"{BASE}/tournaments/{tid}", headers=_hdrs(admin_token), timeout=30).json()
fx1 = tr["fixtures"][1]
check(fx1["live"] is True and fx1["played"] is False
      and fx1["score_home"] == 0 and fx1["score_away"] == 2,
      "fixture[1] live=True score 0-2", fx1)

# fixture[0] should STILL be played
fx0 = tr["fixtures"][0]
check(fx0["played"] is True and fx0["live"] is False
      and fx0["score_home"] == 3 and fx0["score_away"] == 1,
      "fixture[0] still played=true live=false 3-1 after m2 live", fx0)

# Dynamic expected standings from fixtures
expected = {n: {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "Pts": 0} for n in tr["team_names"]}
for fx in tr["fixtures"]:
    if fx["score_home"] is None:
        continue
    h = fx["home"]; a = fx["away"]
    sh_ = fx["score_home"]; sa_ = fx["score_away"]
    expected[h]["P"] += 1; expected[a]["P"] += 1
    expected[h]["GF"] += sh_; expected[h]["GA"] += sa_
    expected[a]["GF"] += sa_; expected[a]["GA"] += sh_
    if sh_ > sa_:
        expected[h]["W"] += 1; expected[h]["Pts"] += 3; expected[a]["L"] += 1
    elif sh_ < sa_:
        expected[a]["W"] += 1; expected[a]["Pts"] += 3; expected[h]["L"] += 1
    else:
        expected[h]["D"] += 1; expected[a]["D"] += 1
        expected[h]["Pts"] += 1; expected[a]["Pts"] += 1

all_ok = True
mismatch_report = []
for team, exp in expected.items():
    row = stand_of(tr, team)
    for k in ("P", "W", "D", "L", "GF", "GA", "Pts"):
        if row[k] != exp[k]:
            all_ok = False
            mismatch_report.append(f"{team}.{k}: got {row[k]} expected {exp[k]}")
check(all_ok, "combined standings (played fx0 + live fx1) match expected",
      "; ".join(mismatch_report) or "all match")


print("\n== 5. Cleanup ==")
r = requests.delete(f"{BASE}/tournaments/{tid}", headers=_hdrs(admin_token), timeout=30)
check(r.status_code == 200, "DELETE tournament → 200", r.text[:200])

for mid in (m1, m2):
    rr = requests.get(f"{BASE}/matches/{mid}", headers=_hdrs(admin_token), timeout=30)
    check(rr.status_code == 404, f"match {mid[:8]}.. cascaded deleted → 404",
          f"got {rr.status_code}")

for u in test_users:
    rr = requests.delete(f"{BASE}/users/{u['id']}", headers=_hdrs(admin_token), timeout=30)
    check(rr.status_code == 200, f"DELETE user {u['id'][:8]}.. → 200", rr.text[:200])


print("\n================================================")
print(f"RESULT: {PASS} passed, {FAIL} failed")
if FAILURES:
    print("\nFAILURES:")
    for f in FAILURES:
        print(f"  - {f}")
sys.exit(0 if FAIL == 0 else 1)
