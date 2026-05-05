"""Backend tests for Tournament team_rosters feature.

Verifies POST /api/tournaments accepts an optional team_rosters mapping that
pre-populates each fixture's lineup and votes, plus all validation, auth,
backward-compat, regression and cascade-delete scenarios from the review
request.
"""
import sys
import uuid
import json as _json
import requests

BACKEND_URL = "https://dodo-roster-build.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@clubdodo.com"
ADMIN_PASSWORD = "dodo2026"

PASS = []
FAIL = []


def record(name: str, ok: bool, detail: str = ""):
    line = f"{'PASS' if ok else 'FAIL'} | {name}"
    if detail:
        line += f" :: {detail}"
    print(line)
    (PASS if ok else FAIL).append(line)


def login(email: str, password: str) -> str:
    r = requests.post(f"{BACKEND_URL}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


def register(email: str, password: str, name: str, shirt_number: int, preferred_position=None):
    body = {"email": email, "password": password, "name": name, "shirt_number": shirt_number}
    if preferred_position:
        body["preferred_position"] = preferred_position
    r = requests.post(f"{BACKEND_URL}/auth/register", json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def admin_delete_user(admin_token: str, uid: str):
    return requests.delete(
        f"{BACKEND_URL}/users/{uid}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )


def admin_delete_tournament(admin_token: str, tid: str):
    return requests.delete(
        f"{BACKEND_URL}/tournaments/{tid}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )


def main():
    suffix = uuid.uuid4().hex[:8]
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    record("Admin login", bool(admin_token))
    H_ADMIN = {"Authorization": f"Bearer {admin_token}"}

    # ----- Register 6 fresh users -----
    positions = ["CB", "LB", "CDM", "CAM", "LW", "ST"]
    user_ids = []
    user_tokens = {}
    for i in range(1, 7):
        email = f"trtest_{suffix}_{i}@example.com"
        pwd = "Passw0rd!"
        name = f"TR Test {i}"
        try:
            res = register(email, pwd, name, 30 + i, positions[i - 1])
        except Exception as e:
            record(f"Register trtest_{i}", False, str(e))
            return
        uid = res["user"]["id"]
        user_ids.append(uid)
        user_tokens[uid] = res["token"]
        record(f"Register trtest_{i} ({positions[i-1]})", True, f"id={uid[:8]}")
    u1, u2, u3, u4, u5, u6 = user_ids

    sample_response = None

    # ===========================================================
    # SCENARIO 1: HAPPY PATH WITH ROSTERS
    # ===========================================================
    try:
        body = {
            "name": "Test Cup",
            "team_names": ["Red", "Black", "White"],
            "team_size": 5,
            "match_type": "friendly",
            "team_rosters": {
                "Red": [u1, u2],
                "Black": [u3, u4],
                "White": [u5, u6],
            },
        }
        r = requests.post(f"{BACKEND_URL}/tournaments", json=body, headers=H_ADMIN, timeout=30)
        record("S1: POST /tournaments with rosters returns 200", r.status_code == 200,
               f"status={r.status_code} body={r.text[:300]}")
        if r.status_code != 200:
            return
        t = r.json()
        sample_response = t
        tid = t["id"]
        fixtures = t.get("fixtures") or []
        record("S1: tournament has 3 fixtures (round-robin C(3,2)=3)", len(fixtures) == 3,
               f"got {len(fixtures)} fixtures")
        pair_set = {tuple(sorted([fx["home"], fx["away"]])) for fx in fixtures}
        expected_pairs = {("Black", "Red"), ("Red", "White"), ("Black", "White")}
        record("S1: round-robin covers every pairing once", pair_set == expected_pairs,
               f"got pairs={pair_set}")
        record("S1: response echoes team_rosters", t.get("team_rosters") == body["team_rosters"],
               f"got={t.get('team_rosters')}")

        roster_map = {"Red": [u1, u2], "Black": [u3, u4], "White": [u5, u6]}
        required_player_keys = {"name", "shirt_number", "profile_picture",
                                "preferred_position", "preferred_positions",
                                "rating", "vote"}
        for fx in fixtures:
            mid = fx["match_id"]
            home, away = fx["home"], fx["away"]
            mr = requests.get(f"{BACKEND_URL}/matches/{mid}", headers=H_ADMIN, timeout=30)
            record(f"S1: GET /matches/{mid[:8]} ({home} vs {away}) -> 200", mr.status_code == 200,
                   f"status={mr.status_code}")
            if mr.status_code != 200:
                continue
            m = mr.json()
            lineup = m.get("lineup") or {}
            ta = lineup.get("team_a") or []
            tb = lineup.get("team_b") or []
            home_ids = [p.get("user_id") for p in ta]
            away_ids = [p.get("user_id") for p in tb]
            record(f"S1: ({home} vs {away}) team_a == roster[{home}] (len 2)",
                   sorted(home_ids) == sorted(roster_map[home]),
                   f"team_a uids={home_ids} expected={roster_map[home]}")
            record(f"S1: ({home} vs {away}) team_b == roster[{away}] (len 2)",
                   sorted(away_ids) == sorted(roster_map[away]),
                   f"team_b uids={away_ids} expected={roster_map[away]}")
            votes = m.get("votes") or []
            expected_voters = set(roster_map[home] + roster_map[away])
            # API serialises votes as list[dict] via _match_public
            actual_voters = {v.get("user_id") for v in votes}
            record(f"S1: ({home} vs {away}) votes has exactly 4 rostered ids",
                   actual_voters == expected_voters,
                   f"votes={actual_voters} expected={expected_voters}")
            record(f"S1: ({home} vs {away}) every vote == 'yes'",
                   all(v.get("vote") == "yes" for v in votes),
                   f"votes={votes}")
            for p in ta + tb:
                missing = required_player_keys - set(p.keys())
                record(f"S1: player {(p.get('user_id') or '?')[:8]} has all required keys",
                       not missing, f"missing={missing}")
                record(f"S1: player {(p.get('user_id') or '?')[:8]} vote=='yes'",
                       p.get("vote") == "yes", f"got={p.get('vote')}")

        # ===== Cascade delete =====
        dr = admin_delete_tournament(admin_token, tid)
        record("S1: DELETE /tournaments/{tid} -> 200", dr.status_code == 200,
               f"status={dr.status_code} body={dr.text[:200]}")
        for fx in fixtures:
            mid = fx["match_id"]
            mr = requests.get(f"{BACKEND_URL}/matches/{mid}", headers=H_ADMIN, timeout=30)
            record(f"S1: cascade match {mid[:8]} -> 404 after tournament delete",
                   mr.status_code == 404, f"status={mr.status_code}")
    except Exception as e:
        record("S1 happy path", False, f"exception: {e}")

    # ===========================================================
    # SCENARIO 2: DUPLICATE PLAYER ACROSS TEAMS
    # ===========================================================
    body = {
        "name": "Dup Cup",
        "team_names": ["A", "B", "C"],
        "team_size": 5,
        "team_rosters": {
            "A": [u1, u2],
            "B": [u3, u1],  # u1 duplicated
            "C": [u5, u6],
        },
    }
    r = requests.post(f"{BACKEND_URL}/tournaments", json=body, headers=H_ADMIN, timeout=30)
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    record("S2: duplicate player across teams -> 400", r.status_code == 400, f"status={r.status_code}")
    record("S2: detail mentions 'more than one team'",
           "more than one team" in (detail or "").lower(),
           f"detail={detail!r}")

    # ===========================================================
    # SCENARIO 3: TEAM EXCEEDING TEAM_SIZE
    # ===========================================================
    body = {
        "name": "Big Cup",
        "team_names": ["X", "Y"],
        "team_size": 4,
        "team_rosters": {
            "X": [u1, u2, u3, u4, u5],  # 5 > team_size=4
            "Y": [u6],
        },
    }
    r = requests.post(f"{BACKEND_URL}/tournaments", json=body, headers=H_ADMIN, timeout=30)
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    record("S3: team exceeding team_size -> 400", r.status_code == 400, f"status={r.status_code}")
    record("S3: detail mentions team name 'X' and limit '4'",
           ("'X'" in (detail or "")) and ("4" in (detail or "")),
           f"detail={detail!r}")

    # ===========================================================
    # SCENARIO 4: UNKNOWN TEAM NAME
    # ===========================================================
    body = {
        "name": "Mystery Cup",
        "team_names": ["Red", "Blue"],
        "team_size": 5,
        "team_rosters": {
            "Red": [u1, u2],
            "Purple": [u3, u4],  # not in team_names
        },
    }
    r = requests.post(f"{BACKEND_URL}/tournaments", json=body, headers=H_ADMIN, timeout=30)
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    record("S4: unknown team in rosters -> 400", r.status_code == 400, f"status={r.status_code}")
    record("S4: detail says 'Roster references unknown team'",
           "roster references unknown team" in (detail or "").lower(),
           f"detail={detail!r}")

    # ===========================================================
    # SCENARIO 5: BACKWARD COMPAT - NO ROSTERS
    # ===========================================================
    body = {
        "name": "Plain Cup",
        "team_names": ["Alpha", "Beta", "Gamma"],
        "team_size": 5,
        "match_type": "friendly",
    }
    r = requests.post(f"{BACKEND_URL}/tournaments", json=body, headers=H_ADMIN, timeout=30)
    record("S5: POST without team_rosters -> 200", r.status_code == 200,
           f"status={r.status_code} body={r.text[:200]}")
    plain_tid = None
    if r.status_code == 200:
        t = r.json()
        plain_tid = t["id"]
        fixtures = t.get("fixtures") or []
        record("S5: 3 fixtures generated", len(fixtures) == 3, f"got {len(fixtures)}")
        record("S5: response includes fixtures and standings",
               "fixtures" in t and "standings" in t, f"keys={list(t.keys())}")
        record("S5: team_rosters in response is empty {}",
               t.get("team_rosters") == {}, f"got={t.get('team_rosters')}")
        for fx in fixtures:
            mid = fx["match_id"]
            mr = requests.get(f"{BACKEND_URL}/matches/{mid}", headers=H_ADMIN, timeout=30)
            if mr.status_code != 200:
                record(f"S5: GET match {mid[:8]}", False, f"status={mr.status_code}")
                continue
            m = mr.json()
            record(f"S5: match {mid[:8]} lineup is null/falsy",
                   not m.get("lineup"), f"lineup={m.get('lineup')}")
            record(f"S5: match {mid[:8]} votes is empty",
                   m.get("votes") in (None, {}, []), f"votes={m.get('votes')}")
            record(f"S5: match {mid[:8]} status=='scheduled'",
                   m.get("status") == "scheduled", f"status={m.get('status')}")

    # ===========================================================
    # SCENARIO 6: AUTH
    # ===========================================================
    body_auth = {"name": "Auth Cup", "team_names": ["P", "Q"], "team_size": 5}
    r = requests.post(f"{BACKEND_URL}/tournaments", json=body_auth, timeout=30)
    record("S6a: POST /tournaments without auth -> 401", r.status_code == 401,
           f"status={r.status_code}")
    nonadmin_token = user_tokens[u1]
    r = requests.post(f"{BACKEND_URL}/tournaments", json=body_auth,
                      headers={"Authorization": f"Bearer {nonadmin_token}"}, timeout=30)
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    record("S6b: POST /tournaments as non-admin -> 403", r.status_code == 403,
           f"status={r.status_code}")
    record("S6b: detail == 'Admin only'", "admin only" in (detail or "").lower(),
           f"detail={detail!r}")

    # ===========================================================
    # SCENARIO 7: REGRESSION
    # ===========================================================
    if plain_tid:
        r = requests.get(f"{BACKEND_URL}/tournaments", headers=H_ADMIN, timeout=30)
        record("S7: GET /tournaments -> 200", r.status_code == 200, f"status={r.status_code}")
        if r.status_code == 200:
            ids = [t["id"] for t in r.json()]
            record("S7: created plain tournament listed", plain_tid in ids,
                   f"plain_tid in list={plain_tid in ids}")
        r = requests.get(f"{BACKEND_URL}/tournaments/{plain_tid}", headers=H_ADMIN, timeout=30)
        record(f"S7: GET /tournaments/{plain_tid[:8]} -> 200", r.status_code == 200,
               f"status={r.status_code}")
        if r.status_code == 200:
            t = r.json()
            record("S7: response includes team_rosters key",
                   "team_rosters" in t, f"keys={list(t.keys())}")

    # ===========================================================
    # CLEANUP
    # ===========================================================
    if plain_tid:
        admin_delete_tournament(admin_token, plain_tid)
    for uid in user_ids:
        try:
            admin_delete_user(admin_token, uid)
        except Exception:
            pass

    # ===========================================================
    # SUMMARY
    # ===========================================================
    print("\n" + "=" * 70)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        print("\n--- FAILURES ---")
        for f in FAIL:
            print(f)
    print("\n--- Sample S1 happy-path response (truncated) ---")
    if sample_response:
        s = _json.dumps(sample_response, default=str)
        print(s[:800] + ("..." if len(s) > 800 else ""))


if __name__ == "__main__":
    main()
    sys.exit(0 if not FAIL else 1)
