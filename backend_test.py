"""Backend test suite for tournament expansion + manual scheduling features.

Covers:
  A) TournamentCreateIn: start_time, all_same_date, double_round_robin
  B) POST /api/tournaments/{tid}/matches (admin-only)
  C) PATCH /api/matches/{mid}/datetime (editor)
  D) POST /api/matches/{mid}/finish (editor)
  E) POST /api/matches/{mid}/lineup/positions (editor)
"""
import os
import sys
import time
import uuid
import json
import requests

BASE_URL = "https://dodo-roster-build.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@clubdodo.com"
ADMIN_PASSWORD = "dodo2026"

passes = []
failures = []


def record(name, ok, detail=""):
    if ok:
        passes.append(name)
        print(f"  PASS  {name}")
    else:
        failures.append(f"{name} :: {detail}")
        print(f"  FAIL  {name} :: {detail}")


def h(token):
    return {"Authorization": f"Bearer {token}"} if token else {}


def login(email, password):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()["token"], r.json()["user"]


def register(email, password, name, shirt_number=None, preferred_position=None):
    body = {"email": email, "password": password, "name": name}
    if shirt_number is not None:
        body["shirt_number"] = shirt_number
    if preferred_position is not None:
        body["preferred_position"] = preferred_position
    r = requests.post(f"{BASE_URL}/auth/register", json=body, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"register failed {r.status_code}: {r.text}")
    j = r.json()
    return j["token"], j["user"]


def admin_delete_user(admin_token, user_id):
    try:
        requests.delete(f"{BASE_URL}/users/{user_id}", headers=h(admin_token), timeout=30)
    except Exception:
        pass


def admin_delete_tournament(admin_token, tid):
    try:
        requests.delete(f"{BASE_URL}/tournaments/{tid}", headers=h(admin_token), timeout=30)
    except Exception:
        pass


def admin_delete_match(admin_token, mid):
    try:
        requests.delete(f"{BASE_URL}/matches/{mid}", headers=h(admin_token), timeout=30)
    except Exception:
        pass


def main():
    print(f"\n=== Backend tests against {BASE_URL} ===\n")

    # --- admin login ---
    admin_tok, admin_user = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    admin_id = admin_user["id"]
    record("Admin login", True)

    suf = uuid.uuid4().hex[:8]
    created_user_ids = []
    created_tournament_ids = []
    created_match_ids = []

    try:
        # ============================================================
        # 1) DOUBLE ROUND-ROBIN GENERATION
        # ============================================================
        print("\n--- 1) Double round-robin ---")

        # 4 fresh users (spec says 4; rosters optional here)
        for i in range(1, 5):
            _, u = register(f"drr_{suf}_{i}@example.com", "passw0rd", f"DRRTest {suf} {i}", preferred_position="CM")
            created_user_ids.append(u["id"])

        body = {
            "name": f"DRR Cup {suf}",
            "team_names": ["Red", "Black", "White"],
            "team_size": 5,
            "match_type": "friendly",
            "double_round_robin": True,
        }
        r = requests.post(f"{BASE_URL}/tournaments", json=body, headers=h(admin_tok), timeout=30)
        record("1b POST /tournaments double_round_robin 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        if r.status_code == 200:
            t = r.json()
            tid = t["id"]
            created_tournament_ids.append(tid)
            fixtures = t["fixtures"]
            record("1b fixtures.length == 6", len(fixtures) == 6, f"len={len(fixtures)}")
            if len(fixtures) == 6:
                first = [(f["home"], f["away"]) for f in fixtures[:3]]
                second = [(f["home"], f["away"]) for f in fixtures[3:]]
                expected_swapped = [(a, ha) for (ha, a) in first]
                record(
                    "1b second-leg swapped home/away",
                    second == expected_swapped,
                    f"first={first} second={second}",
                )

            admin_delete_tournament(admin_tok, tid)
            r2 = requests.get(f"{BASE_URL}/tournaments/{tid}", headers=h(admin_tok), timeout=30)
            record("1c DELETE tournament cascade", r2.status_code == 404, f"get after delete={r2.status_code}")
            created_tournament_ids.remove(tid)

        # ============================================================
        # 2) ALL_SAME_DATE + START_TIME
        # ============================================================
        print("\n--- 2) all_same_date + start_time ---")
        body = {
            "name": f"Same Day Cup {suf}",
            "team_names": ["Red", "Black", "White"],
            "team_size": 5,
            "match_type": "friendly",
            "start_date": "2026-07-01",
            "start_time": "20:30",
            "all_same_date": True,
        }
        r = requests.post(f"{BASE_URL}/tournaments", json=body, headers=h(admin_tok), timeout=30)
        record("2a POST /tournaments all_same_date 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        if r.status_code == 200:
            t = r.json()
            tid = t["id"]
            created_tournament_ids.append(tid)
            fixtures = t["fixtures"]
            # need to fetch actual match dates via GET tournament (scheduled_at from match)
            # fixtures in tournament response include scheduled_at derived from the match.date
            record("2a exactly 3 fixtures", len(fixtures) == 3, f"len={len(fixtures)}")
            if len(fixtures) == 3:
                t0 = fixtures[0]["scheduled_at"]
                t1 = fixtures[1]["scheduled_at"]
                t2 = fixtures[2]["scheduled_at"]
                # All on 2026-07-01
                record("2a fixture0 starts 2026-07-01T20:30", t0.startswith("2026-07-01T20:30"), f"t0={t0}")
                record("2a fixture1 starts 2026-07-01T21:30", t1.startswith("2026-07-01T21:30"), f"t1={t1}")
                record("2a fixture2 starts 2026-07-01T22:30", t2.startswith("2026-07-01T22:30"), f"t2={t2}")

            admin_delete_tournament(admin_tok, tid)
            created_tournament_ids.remove(tid)
            record("2b DELETE tournament ok", True)

        # ============================================================
        # 3) ADD MATCH (B)
        # ============================================================
        print("\n--- 3) Add match endpoint ---")

        # Register 6 fresh users for rosters
        roster_uids = []
        for i in range(1, 7):
            _, u = register(f"addm_{suf}_{i}@example.com", "passw0rd", f"AddMatchTest {suf} {i}", preferred_position="CM")
            roster_uids.append(u["id"])
            created_user_ids.append(u["id"])

        body = {
            "name": f"Add Match Cup {suf}",
            "team_names": ["Red", "Black", "White"],
            "team_size": 5,
            "match_type": "friendly",
            "team_rosters": {
                "Red": roster_uids[0:2],
                "Black": roster_uids[2:4],
                "White": roster_uids[4:6],
            },
        }
        r = requests.post(f"{BASE_URL}/tournaments", json=body, headers=h(admin_tok), timeout=30)
        record("3a POST /tournaments with rosters 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        if r.status_code != 200:
            return

        t = r.json()
        tid = t["id"]
        created_tournament_ids.append(tid)
        record("3a initial fixtures.length == 3", len(t["fixtures"]) == 3, f"len={len(t['fixtures'])}")

        # Add a new match
        add_body = {"home": "Red", "away": "Black", "scheduled_at": "2026-08-15T18:00:00+00:00"}
        r = requests.post(f"{BASE_URL}/tournaments/{tid}/matches", json=add_body, headers=h(admin_tok), timeout=30)
        record("3b POST add-match 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        if r.status_code == 200:
            t2 = r.json()
            record("3b fixtures.length == 4", len(t2["fixtures"]) == 4, f"len={len(t2['fixtures'])}")
            # Locate new fixture (round==4)
            new_fx = None
            for fx in t2["fixtures"]:
                if fx["round"] == 4:
                    new_fx = fx
                    break
            record("3b new fixture has round=4", new_fx is not None, "no round=4 fixture")
            if new_fx:
                record("3b new fixture home==Red, away==Black",
                       new_fx["home"] == "Red" and new_fx["away"] == "Black",
                       f"home={new_fx['home']} away={new_fx['away']}")
                # GET match
                mid = new_fx["match_id"]
                rm = requests.get(f"{BASE_URL}/matches/{mid}", headers=h(admin_tok), timeout=30)
                record("3b GET new match 200", rm.status_code == 200, f"status={rm.status_code}")
                if rm.status_code == 200:
                    m = rm.json()
                    record("3b match title contains 'Red vs Black'", "Red vs Black" in m["title"], f"title={m['title']}")
                    record("3b match status scheduled", m["status"] == "scheduled", f"status={m['status']}")
                    lineup = m.get("lineup") or {}
                    team_a_ids = [p["user_id"] for p in (lineup.get("team_a") or [])]
                    team_b_ids = [p["user_id"] for p in (lineup.get("team_b") or [])]
                    record("3b lineup team_a == Red roster",
                           set(team_a_ids) == set(roster_uids[0:2]),
                           f"team_a={team_a_ids}")
                    record("3b lineup team_b == Black roster",
                           set(team_b_ids) == set(roster_uids[2:4]),
                           f"team_b={team_b_ids}")
                    record("3b lineup has 4 players total", (len(team_a_ids) + len(team_b_ids)) == 4,
                           f"count={len(team_a_ids)+len(team_b_ids)}")
                    votes = m.get("votes") or []
                    record("3b 4 votes set to yes",
                           len(votes) == 4 and all(v.get("vote") == "yes" for v in votes),
                           f"votes_len={len(votes)}")

        # 3c Validation
        r = requests.post(f"{BASE_URL}/tournaments/{tid}/matches",
                          json={"home": "Red", "away": "Red", "scheduled_at": "2026-08-15T18:00:00+00:00"},
                          headers=h(admin_tok), timeout=30)
        record("3c same team → 400", r.status_code == 400, f"status={r.status_code} body={r.text[:150]}")
        if r.status_code == 400:
            record("3c error mentions 'different'", "different" in r.text.lower(), f"body={r.text[:100]}")

        r = requests.post(f"{BASE_URL}/tournaments/{tid}/matches",
                          json={"home": "Yellow", "away": "Black", "scheduled_at": "2026-08-15T18:00:00+00:00"},
                          headers=h(admin_tok), timeout=30)
        record("3c unknown team → 400", r.status_code == 400, f"status={r.status_code}")
        if r.status_code == 400:
            record("3c error mentions 'one of'", "one of" in r.text.lower() or "home/away" in r.text.lower(), f"body={r.text[:100]}")

        r = requests.post(f"{BASE_URL}/tournaments/{tid}/matches",
                          json={"home": "Red", "away": "Black", "scheduled_at": "not-a-date"},
                          headers=h(admin_tok), timeout=30)
        record("3c bad ISO → 400", r.status_code == 400, f"status={r.status_code}")

        # 3d Non-admin
        regtok, reguser = register(f"regular_{suf}@example.com", "passw0rd", f"Regular {suf}")
        created_user_ids.append(reguser["id"])
        r = requests.post(f"{BASE_URL}/tournaments/{tid}/matches",
                          json={"home": "Red", "away": "Black", "scheduled_at": "2026-08-15T19:00:00+00:00"},
                          headers=h(regtok), timeout=30)
        record("3d non-admin add-match → 403", r.status_code == 403, f"status={r.status_code}")

        # 3e delete tournament
        admin_delete_tournament(admin_tok, tid)
        created_tournament_ids.remove(tid)
        record("3e tournament cleanup", True)

        # ============================================================
        # 4) DATETIME PATCH (C)
        # ============================================================
        print("\n--- 4) PATCH /api/matches/{mid}/datetime ---")

        r = requests.post(f"{BASE_URL}/matches",
                          json={"title": f"DateTest {suf}", "date": "2026-09-01T19:00:00+00:00",
                                "team_size": 5, "match_type": "friendly"},
                          headers=h(admin_tok), timeout=30)
        record("4a create match 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        if r.status_code == 200:
            mid = r.json()["id"]
            created_match_ids.append(mid)

            r = requests.patch(f"{BASE_URL}/matches/{mid}/datetime",
                               json={"scheduled_at": "2027-12-31T23:45:00+00:00"},
                               headers=h(admin_tok), timeout=30)
            record("4b PATCH datetime 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
            if r.status_code == 200:
                rm = requests.get(f"{BASE_URL}/matches/{mid}", headers=h(admin_tok), timeout=30)
                date_str = rm.json().get("date", "")
                # Normalized via python datetime.isoformat(); input was +00:00 so should match
                record("4b date updated to 2027-12-31T23:45",
                       "2027-12-31T23:45" in date_str,
                       f"date={date_str}")

            r = requests.patch(f"{BASE_URL}/matches/{mid}/datetime",
                               json={"scheduled_at": "not-a-date"},
                               headers=h(admin_tok), timeout=30)
            record("4c bad ISO → 400", r.status_code == 400, f"status={r.status_code}")

            r = requests.patch(f"{BASE_URL}/matches/{mid}/datetime",
                               json={"scheduled_at": "2027-12-31T23:45:00+00:00"},
                               headers=h(regtok), timeout=30)
            record("4d non-editor → 403", r.status_code == 403, f"status={r.status_code}")

            admin_delete_match(admin_tok, mid)
            created_match_ids.remove(mid)

        # ============================================================
        # 5) FINISH MATCH (D)
        # ============================================================
        print("\n--- 5) POST /api/matches/{mid}/finish ---")

        # Need 4 registered users to put 2 on each team via lineup override
        finish_uids = []
        for i in range(1, 5):
            _, u = register(f"finish_{suf}_{i}@example.com", "passw0rd", f"FinishTest {suf} {i}", preferred_position="CM")
            finish_uids.append(u["id"])
            created_user_ids.append(u["id"])

        # Create league match
        r = requests.post(f"{BASE_URL}/matches",
                          json={"title": f"League Test {suf}", "date": "2027-10-01T19:00:00+00:00",
                                "team_size": 5, "match_type": "league"},
                          headers=h(admin_tok), timeout=30)
        record("5a create league match 200", r.status_code == 200, f"body={r.text[:200]}")
        if r.status_code == 200:
            mid = r.json()["id"]
            created_match_ids.append(mid)
            # Set lineup: 2 users on each team
            r = requests.put(f"{BASE_URL}/matches/{mid}/lineup",
                             json={"team_a": finish_uids[0:2], "team_b": finish_uids[2:4]},
                             headers=h(admin_tok), timeout=30)
            record("5a PUT lineup 200", r.status_code == 200, f"body={r.text[:200]}")

            # Set live score
            r = requests.post(f"{BASE_URL}/matches/{mid}/live-score",
                              json={"team_a_score": 2, "team_b_score": 0},
                              headers=h(admin_tok), timeout=30)
            record("5a live-score 2-0 200", r.status_code == 200, f"status={r.status_code}")

            # Get baseline stats for team_a[0] and team_b[0]
            r = requests.get(f"{BASE_URL}/users", headers=h(admin_tok), timeout=30)
            users = r.json()
            ua0_baseline = next(u for u in users if u["id"] == finish_uids[0])
            ub0_baseline = next(u for u in users if u["id"] == finish_uids[2])

            # Finish
            r = requests.post(f"{BASE_URL}/matches/{mid}/finish", headers=h(admin_tok), timeout=30)
            record("5b POST /finish 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
            if r.status_code == 200:
                m = r.json()
                record("5b status == played", m["status"] == "played", f"status={m['status']}")
                res = m.get("result") or {}
                record("5b result.team_a_score == 2", res.get("team_a_score") == 2, f"result={res}")
                record("5b result.team_b_score == 0", res.get("team_b_score") == 0, f"result={res}")
                record("5b result.stats == []", res.get("stats") == [], f"stats={res.get('stats')}")

            # Check team_a user stats
            r = requests.get(f"{BASE_URL}/users", headers=h(admin_tok), timeout=30)
            users = r.json()
            ua0_after = next(u for u in users if u["id"] == finish_uids[0])
            ub0_after = next(u for u in users if u["id"] == finish_uids[2])
            record("5c team_a user matches_played +=1",
                   ua0_after["matches_played"] == ua0_baseline["matches_played"] + 1,
                   f"before={ua0_baseline['matches_played']} after={ua0_after['matches_played']}")
            record("5c team_a user wins +=1",
                   ua0_after["wins"] == ua0_baseline["wins"] + 1,
                   f"before={ua0_baseline['wins']} after={ua0_after['wins']}")
            record("5c team_a user league_points +=3",
                   ua0_after["league_points"] == ua0_baseline["league_points"] + 3,
                   f"before={ua0_baseline['league_points']} after={ua0_after['league_points']}")
            record("5c team_b user matches_played +=1",
                   ub0_after["matches_played"] == ub0_baseline["matches_played"] + 1,
                   f"before={ub0_baseline['matches_played']} after={ub0_after['matches_played']}")
            record("5c team_b user losses +=1",
                   ub0_after["losses"] == ub0_baseline["losses"] + 1,
                   f"before={ub0_baseline['losses']} after={ub0_after['losses']}")
            record("5c team_b user league_points unchanged",
                   ub0_after["league_points"] == ub0_baseline["league_points"],
                   f"before={ub0_baseline['league_points']} after={ub0_after['league_points']}")

            # second /finish → 400
            r = requests.post(f"{BASE_URL}/matches/{mid}/finish", headers=h(admin_tok), timeout=30)
            record("5d second /finish → 400", r.status_code == 400, f"status={r.status_code} body={r.text[:150]}")
            if r.status_code == 400:
                record("5d error mentions 'already'", "already" in r.text.lower(), f"body={r.text[:150]}")

            admin_delete_match(admin_tok, mid)
            created_match_ids.remove(mid)

        # 5e DRAW scenario on friendly match
        r = requests.post(f"{BASE_URL}/matches",
                          json={"title": f"Draw Test {suf}", "date": "2027-10-02T19:00:00+00:00",
                                "team_size": 5, "match_type": "friendly"},
                          headers=h(admin_tok), timeout=30)
        record("5e create friendly match 200", r.status_code == 200, f"body={r.text[:200]}")
        if r.status_code == 200:
            mid = r.json()["id"]
            created_match_ids.append(mid)
            requests.put(f"{BASE_URL}/matches/{mid}/lineup",
                         json={"team_a": finish_uids[0:2], "team_b": finish_uids[2:4]},
                         headers=h(admin_tok), timeout=30)
            requests.post(f"{BASE_URL}/matches/{mid}/live-score",
                          json={"team_a_score": 1, "team_b_score": 1},
                          headers=h(admin_tok), timeout=30)
            # baseline (after previous finish)
            r = requests.get(f"{BASE_URL}/users", headers=h(admin_tok), timeout=30)
            users = r.json()
            ua0_pre = next(u for u in users if u["id"] == finish_uids[0])

            r = requests.post(f"{BASE_URL}/matches/{mid}/finish", headers=h(admin_tok), timeout=30)
            record("5e friendly /finish 200", r.status_code == 200, f"status={r.status_code}")

            r = requests.get(f"{BASE_URL}/users", headers=h(admin_tok), timeout=30)
            users = r.json()
            ua0_post = next(u for u in users if u["id"] == finish_uids[0])
            record("5e friendly draw: matches_played +=1",
                   ua0_post["matches_played"] == ua0_pre["matches_played"] + 1,
                   f"before={ua0_pre['matches_played']} after={ua0_post['matches_played']}")
            record("5e friendly draw: draws +=1",
                   ua0_post["draws"] == ua0_pre["draws"] + 1,
                   f"before={ua0_pre['draws']} after={ua0_post['draws']}")
            record("5e friendly draw: league_points UNCHANGED",
                   ua0_post["league_points"] == ua0_pre["league_points"],
                   f"before={ua0_pre['league_points']} after={ua0_post['league_points']}")

            admin_delete_match(admin_tok, mid)
            created_match_ids.remove(mid)

        # ============================================================
        # 6) LINEUP POSITIONS (E)
        # ============================================================
        print("\n--- 6) POST /api/matches/{mid}/lineup/positions ---")

        r = requests.post(f"{BASE_URL}/matches",
                          json={"title": f"PosTest {suf}", "date": "2027-11-01T19:00:00+00:00",
                                "team_size": 5, "match_type": "friendly"},
                          headers=h(admin_tok), timeout=30)
        record("6a create match 200", r.status_code == 200)
        if r.status_code == 200:
            mid = r.json()["id"]
            created_match_ids.append(mid)
            # Build lineup with 2 on each team
            r = requests.put(f"{BASE_URL}/matches/{mid}/lineup",
                             json={"team_a": finish_uids[0:2], "team_b": finish_uids[2:4]},
                             headers=h(admin_tok), timeout=30)
            record("6a PUT lineup 200", r.status_code == 200, f"body={r.text[:200]}")

            target_uid = finish_uids[0]
            r = requests.post(f"{BASE_URL}/matches/{mid}/lineup/positions",
                              json={"positions": {target_uid: {"x": 0.42, "y": 0.69}}},
                              headers=h(admin_tok), timeout=30)
            record("6a POST positions 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
            if r.status_code == 200:
                m = r.json()
                team_a = (m.get("lineup") or {}).get("team_a") or []
                target_p = next((p for p in team_a if p["user_id"] == target_uid), None)
                record("6b target player has x=0.42",
                       target_p is not None and abs(target_p.get("x", 0) - 0.42) < 1e-6,
                       f"p={target_p}")
                record("6b target player has y=0.69",
                       target_p is not None and abs(target_p.get("y", 0) - 0.69) < 1e-6,
                       f"p={target_p}")
                # Other players unchanged (no x/y)
                other_a = next((p for p in team_a if p["user_id"] == finish_uids[1]), None)
                record("6b other player has no x/y",
                       other_a is not None and "x" not in other_a and "y" not in other_a,
                       f"p={other_a}")

            # 6c x > 1.0 → 422
            r = requests.post(f"{BASE_URL}/matches/{mid}/lineup/positions",
                              json={"positions": {target_uid: {"x": 1.5, "y": 0.5}}},
                              headers=h(admin_tok), timeout=30)
            record("6c x>1.0 → 422", r.status_code == 422, f"status={r.status_code} body={r.text[:150]}")

            # 6d non-editor → 403
            r = requests.post(f"{BASE_URL}/matches/{mid}/lineup/positions",
                              json={"positions": {target_uid: {"x": 0.5, "y": 0.5}}},
                              headers=h(regtok), timeout=30)
            record("6d non-editor → 403", r.status_code == 403, f"status={r.status_code}")

            admin_delete_match(admin_tok, mid)
            created_match_ids.remove(mid)

    finally:
        # ============================================================
        # 7) CLEANUP
        # ============================================================
        print("\n--- 7) Cleanup ---")
        for tid in list(created_tournament_ids):
            admin_delete_tournament(admin_tok, tid)
        for mid in list(created_match_ids):
            admin_delete_match(admin_tok, mid)
        for uid in list(created_user_ids):
            admin_delete_user(admin_tok, uid)
        record("7 cleanup complete", True)

    print(f"\n=== RESULTS: {len(passes)} PASS / {len(failures)} FAIL ===")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
