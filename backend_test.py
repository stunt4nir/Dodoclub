"""
Backend tests for Club Dodo — multi-position (preferred_positions) feature.

Covers:
  1. Admin login
  2. PUT /api/users/me with preferred_positions=["CAM","CDM"]
  3. PUT /api/users/me with preferred_positions=["ST"]
  4. PUT /api/users/me with preferred_positions=[] (empty clears)
  5. PUT /api/users/me with preferred_positions=["GK","CB","CAM"] → 422
  6. Backward compat: PUT preferred_position="LW" → list auto-synced
  7. Register: POST /api/auth/register with preferred_positions
  8. Lineup smoke: 6 users + admin → generate-lineup preserves arrays
  9. Match payload: GET /api/matches/{id} votes contain both fields
"""
import os
import sys
import uuid
import requests

BASE = os.environ.get("BACKEND_URL", "https://dodo-roster-build.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "admin@clubdodo.com"
ADMIN_PASSWORD = "dodo2026"

results = []


def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}{' — ' + detail if detail else ''}")
    results.append((name, passed, detail))


def post(path, json=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.post(f"{API}{path}", json=json, headers=headers, timeout=30)


def put(path, json=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.put(f"{API}{path}", json=json, headers=headers, timeout=30)


def get(path, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.get(f"{API}{path}", headers=headers, timeout=30)


def t1_admin_login():
    r = post("/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        record("T1 admin login", False, f"status={r.status_code} body={r.text[:200]}")
        return None
    body = r.json()
    token = body.get("token")
    user = body.get("user", {})
    ok = bool(token) and "preferred_position" in user and "preferred_positions" in user
    record("T1 admin login returns token + both position fields on user", ok,
           f"keys={list(user.keys())[:12]}")
    return token


def t2_two_positions(token):
    r = put("/users/me", {"preferred_positions": ["CAM", "CDM"]}, token=token)
    if r.status_code != 200:
        record("T2 PUT /users/me [CAM,CDM]", False, f"status={r.status_code} body={r.text[:200]}")
        return
    me = get("/auth/me", token=token).json()
    ok = me.get("preferred_position") == "CAM" and me.get("preferred_positions") == ["CAM", "CDM"]
    record("T2 GET /auth/me → primary=CAM, list=[CAM,CDM]", ok,
           f"got primary={me.get('preferred_position')} list={me.get('preferred_positions')}")


def t3_single_position(token):
    r = put("/users/me", {"preferred_positions": ["ST"]}, token=token)
    if r.status_code != 200:
        record("T3 PUT /users/me [ST]", False, f"status={r.status_code}")
        return
    me = get("/auth/me", token=token).json()
    ok = me.get("preferred_position") == "ST" and me.get("preferred_positions") == ["ST"]
    record("T3 GET /auth/me → primary=ST, list=[ST]", ok,
           f"got primary={me.get('preferred_position')} list={me.get('preferred_positions')}")


def t4_empty_positions(token):
    r = put("/users/me", {"preferred_positions": []}, token=token)
    if r.status_code != 200:
        record("T4 PUT /users/me []", False, f"status={r.status_code} body={r.text[:200]}")
        return
    me = get("/auth/me", token=token).json()
    ok = me.get("preferred_position") is None and me.get("preferred_positions") == []
    record("T4 GET /auth/me → primary=None, list=[]", ok,
           f"got primary={me.get('preferred_position')} list={me.get('preferred_positions')}")


def t5_too_many_positions(token):
    r = put("/users/me", {"preferred_positions": ["GK", "CB", "CAM"]}, token=token)
    ok = r.status_code == 422
    record("T5 PUT /users/me [GK,CB,CAM] → 422", ok, f"status={r.status_code}")


def t6_legacy_single(token):
    r = put("/users/me", {"preferred_position": "LW"}, token=token)
    if r.status_code != 200:
        record("T6 PUT /users/me preferred_position=LW", False, f"status={r.status_code}")
        return
    me = get("/auth/me", token=token).json()
    ok = me.get("preferred_position") == "LW" and me.get("preferred_positions") == ["LW"]
    record("T6 Legacy single → list auto-synced to [LW]", ok,
           f"got primary={me.get('preferred_position')} list={me.get('preferred_positions')}")


def t7_register_with_positions():
    suffix = uuid.uuid4().hex[:8]
    email = f"pos7_{suffix}@clubdodo.example.com"
    pwd = "Pass12345!"
    body = {
        "email": email,
        "password": pwd,
        "name": "Pierre Lacroix",
        "shirt_number": 17,
        "preferred_positions": ["CAM", "CDM"],
    }
    r = post("/auth/register", body)
    if r.status_code != 200:
        record("T7 register w/ preferred_positions", False, f"status={r.status_code} body={r.text[:300]}")
        return
    resp = r.json()
    u = resp.get("user", {})
    ok_resp = u.get("preferred_position") == "CAM" and u.get("preferred_positions") == ["CAM", "CDM"]
    record("T7a Register response carries both fields correctly", ok_resp,
           f"got primary={u.get('preferred_position')} list={u.get('preferred_positions')}")
    login = post("/auth/login", {"email": email, "password": pwd})
    if login.status_code != 200:
        record("T7b Login newly registered user", False, f"status={login.status_code}")
        return
    tok = login.json()["token"]
    me = get("/auth/me", token=tok).json()
    ok_persist = me.get("preferred_position") == "CAM" and me.get("preferred_positions") == ["CAM", "CDM"]
    record("T7b Persistence via login + GET /auth/me", ok_persist,
           f"got primary={me.get('preferred_position')} list={me.get('preferred_positions')}")


def t8_and_9_lineup(admin_token):
    combos = [
        ("Marc Dubois",    ["CAM", "CDM"]),
        ("Julien Martin",  ["ST", "CAM"]),
        ("Thomas Leroy",   ["CB", "RB"]),
        ("Lucas Bernard",  ["GK"]),
        ("Antoine Moreau", ["LB", "CB"]),
        ("Nicolas Girard", ["LW", "RW"]),
    ]
    users = []
    for name, positions in combos:
        suffix = uuid.uuid4().hex[:8]
        email = f"lineup_{suffix}@clubdodo.example.com"
        pwd = "Pass12345!"
        body = {
            "email": email,
            "password": pwd,
            "name": name,
            "shirt_number": None,
            "preferred_positions": positions,
        }
        r = post("/auth/register", body)
        if r.status_code != 200:
            record(f"T8 register {name}", False, f"status={r.status_code} body={r.text[:200]}")
            return
        u = r.json()["user"]
        users.append((r.json()["token"], u["id"], email, name, positions))
    record("T8a Registered 6 lineup test users with preferred_positions", True,
           f"{len(users)} users")

    put("/users/me", {"preferred_positions": ["CAM", "CDM"]}, token=admin_token)

    future = "2030-06-15T18:00:00Z"
    m_body = {
        "title": "Multi-position smoke match",
        "date": future,
        "location": "Paris Parc des Princes",
        "team_size": 3,
        "match_type": "friendly",
        "third_team_enabled": False,
        "duration_minutes": 60,
    }
    r = post("/matches", m_body, token=admin_token)
    if r.status_code != 200:
        record("T8b Create friendly match", False, f"status={r.status_code} body={r.text[:200]}")
        return
    match = r.json()
    mid = match["id"]
    record("T8b Create friendly match team_size=3", True, f"mid={mid}")

    admin_vote = post(f"/matches/{mid}/vote", {"vote": "yes"}, token=admin_token)
    if admin_vote.status_code != 200:
        record("T8c Admin yes vote", False, f"status={admin_vote.status_code}")
        return
    for tok, uid, email, name, pos in users:
        rv = post(f"/matches/{mid}/vote", {"vote": "yes"}, token=tok)
        if rv.status_code != 200:
            record(f"T8c Vote yes by {name}", False, f"status={rv.status_code}")
            return
    record("T8c Collected 7 yes votes (admin + 6 users)", True)

    # Test 9 — match payload
    mresp = get(f"/matches/{mid}", token=admin_token).json()
    votes = mresp.get("votes", [])
    record("T9 Match payload has 7 vote entries", len(votes) == 7, f"got {len(votes)}")

    missing = []
    mismatched = []
    for v in votes:
        if "preferred_position" not in v or "preferred_positions" not in v:
            missing.append(v.get("name"))
            continue
        pp = v.get("preferred_positions") or []
        primary = v.get("preferred_position")
        if pp and primary != pp[0]:
            mismatched.append((v.get("name"), primary, pp))
    record("T9a Every vote entry includes BOTH preferred_position AND preferred_positions",
           len(missing) == 0, f"missing on: {missing}" if missing else "")
    record("T9b primary matches preferred_positions[0] in every vote entry",
           len(mismatched) == 0, f"mismatches: {mismatched}" if mismatched else "")

    # Test 8 — generate lineup
    r = post(f"/matches/{mid}/generate-lineup", token=admin_token)
    if r.status_code != 200:
        record("T8d POST /matches/{id}/generate-lineup", False,
               f"status={r.status_code} body={r.text[:400]}")
        return
    record("T8d POST /matches/{id}/generate-lineup returns 200 (no 500)", True)
    lineup = r.json().get("lineup") or {}
    team_a = lineup.get("team_a", [])
    team_b = lineup.get("team_b", [])
    team_c = lineup.get("team_c", []) or []
    reserves = lineup.get("reserves", []) or []
    all_players = team_a + team_b + team_c
    record("T8e Lineup populated (team_a + team_b have players)",
           len(team_a) > 0 and len(team_b) > 0,
           f"a={len(team_a)} b={len(team_b)} c={len(team_c)} reserves={len(reserves)}")

    fails = []
    for p in all_players:
        pp = p.get("preferred_positions")
        primary = p.get("preferred_position")
        if pp is None:
            fails.append((p.get("name"), "MISSING preferred_positions", primary, pp))
            continue
        if not isinstance(pp, list):
            fails.append((p.get("name"), "NOT A LIST", primary, pp))
            continue
        if pp and primary != pp[0]:
            fails.append((p.get("name"), "primary != list[0]", primary, pp))
    record("T8f team_a + team_b players preserve preferred_positions array (not lost/coerced)",
           len(fails) == 0, f"issues: {fails}" if fails else "")

    expected_by_name = {name: positions for _, _, _, name, positions in users}
    value_fails = []
    for p in all_players:
        name = p.get("name")
        if name in expected_by_name:
            exp = expected_by_name[name]
            got = p.get("preferred_positions") or []
            if got != exp:
                value_fails.append((name, exp, got))
    record("T8g Exact preferred_positions values preserved per player",
           len(value_fails) == 0, f"mismatches: {value_fails}" if value_fails else "")


def main():
    print(f"Testing backend @ {API}")
    token = t1_admin_login()
    if not token:
        print("Cannot proceed without admin token")
        sys.exit(2)
    t2_two_positions(token)
    t3_single_position(token)
    t4_empty_positions(token)
    t5_too_many_positions(token)
    t6_legacy_single(token)
    t7_register_with_positions()
    t8_and_9_lineup(token)

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"Total: {len(results)}  Passed: {passed}  Failed: {failed}")
    if failed:
        print("\nFailures:")
        for n, ok, d in results:
            if not ok:
                print(f"  ✗ {n}: {d}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
