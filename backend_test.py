"""
Backend tests for Club Dodo — player position expansion.

Covers:
1. Admin login
2. PUT profile with each new position (CDM, CAM, CB, LB, RB, LW, RW, ST) + GK legacy
3. Invalid position returns 422
4. Legacy positions (GK, DEF, MID, FWD, ANY) backward compatibility
5. Lineup smoke test with 6 users across new positions
"""
import os
import uuid
import requests
from datetime import datetime, timezone, timedelta

BASE = "https://dodo-roster-build.preview.emergentagent.com/api"

ADMIN_EMAIL = "admin@clubdodo.com"
ADMIN_PASSWORD = "dodo2026"

NEW_POSITIONS = ["CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST"]
LEGACY_POSITIONS = ["GK", "DEF", "MID", "FWD", "ANY"]

results = []


def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    results.append((name, passed, detail))


def auth_hdr(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    # 1) Admin login
    r = requests.post(
        f"{BASE}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        record("admin_login", False, f"HTTP {r.status_code} {r.text[:300]}")
        return
    admin_token = r.json()["token"]
    admin_id = r.json()["user"]["id"]
    record("admin_login", True, f"admin_id={admin_id}")

    # The review says PUT /api/auth/me but implementation is PUT /api/users/me.
    # Try /api/auth/me first, fallback to /api/users/me.
    probe = requests.put(
        f"{BASE}/auth/me",
        headers=auth_hdr(admin_token),
        json={"preferred_position": "CDM"},
        timeout=30,
    )
    if probe.status_code in (404, 405):
        profile_update_path = "/users/me"
        record(
            "profile_update_endpoint_probe",
            True,
            f"PUT /auth/me not defined (got {probe.status_code}); using /users/me (actual implementation)",
        )
    else:
        profile_update_path = "/auth/me"
        record(
            "profile_update_endpoint_probe",
            True,
            f"/auth/me responded {probe.status_code}",
        )

    # Helper to update then GET /auth/me
    def set_pos_and_check(pos, expect_ok):
        r = requests.put(
            f"{BASE}{profile_update_path}",
            headers=auth_hdr(admin_token),
            json={"preferred_position": pos},
            timeout=30,
        )
        if expect_ok:
            if r.status_code != 200:
                return False, f"update HTTP {r.status_code} {r.text[:200]}"
            g = requests.get(f"{BASE}/auth/me", headers=auth_hdr(admin_token), timeout=30)
            if g.status_code != 200:
                return False, f"GET /auth/me HTTP {g.status_code}"
            got = g.json().get("preferred_position")
            if got != pos:
                return False, f"expected {pos}, got {got}"
            return True, f"preferred_position={got}"
        else:
            if r.status_code != 422:
                return False, f"expected 422 got {r.status_code} {r.text[:200]}"
            return True, "validation error 422 as expected"

    # 2) New positions
    for pos in NEW_POSITIONS:
        ok, detail = set_pos_and_check(pos, expect_ok=True)
        record(f"set_new_position_{pos}", ok, detail)

    # 3) Invalid position
    ok, detail = set_pos_and_check("XYZ", expect_ok=False)
    record("invalid_position_XYZ_422", ok, detail)

    # 4) Legacy positions
    for pos in LEGACY_POSITIONS:
        ok, detail = set_pos_and_check(pos, expect_ok=True)
        record(f"legacy_position_{pos}", ok, detail)

    # Reset admin pref to something reasonable
    requests.put(
        f"{BASE}{profile_update_path}",
        headers=auth_hdr(admin_token),
        json={"preferred_position": "CAM"},
        timeout=30,
    )

    # 5) Lineup smoke test
    # Register 6 users: 2 CB, 2 CAM, 2 ST
    unique = uuid.uuid4().hex[:8]
    test_user_specs = [
        ("CB", f"ayoub.{unique}@test.clubdodo.io", "Ayoub Karim"),
        ("CB", f"samir.{unique}@test.clubdodo.io", "Samir Elattar"),
        ("CAM", f"mehdi.{unique}@test.clubdodo.io", "Mehdi Benali"),
        ("CAM", f"nabil.{unique}@test.clubdodo.io", "Nabil Chraibi"),
        ("ST", f"rayan.{unique}@test.clubdodo.io", "Rayan Tazi"),
        ("ST", f"yassine.{unique}@test.clubdodo.io", "Yassine Mansour"),
    ]
    test_users = []
    all_registered = True
    for pos, email, name in test_user_specs:
        r = requests.post(
            f"{BASE}/auth/register",
            json={
                "email": email,
                "password": "Pass123!",
                "name": name,
                "preferred_position": pos,
            },
            timeout=30,
        )
        if r.status_code != 200:
            record(f"register_{pos}_{email}", False, f"HTTP {r.status_code} {r.text[:200]}")
            all_registered = False
            continue
        data = r.json()
        test_users.append(
            {
                "pos": pos,
                "email": email,
                "name": name,
                "token": data["token"],
                "id": data["user"]["id"],
                "preferred_position_returned": data["user"].get("preferred_position"),
            }
        )
    record(
        "register_6_test_users_with_new_positions",
        all_registered,
        f"registered {len(test_users)}/6",
    )

    # Verify returned preferred_position preserved exactly
    for u in test_users:
        ok = u["preferred_position_returned"] == u["pos"]
        record(
            f"registered_user_preferred_position_preserved_{u['pos']}_{u['name']}",
            ok,
            f"returned={u['preferred_position_returned']}",
        )

    if not test_users:
        record("lineup_smoke_test", False, "no test users available")
        return

    # Create match as admin
    future_date = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    r = requests.post(
        f"{BASE}/matches",
        headers=auth_hdr(admin_token),
        json={
            "title": "Position Smoke Match",
            "date": future_date,
            "location": "Casablanca Pitch",
            "team_size": 3,
            "match_type": "friendly",
        },
        timeout=30,
    )
    if r.status_code != 200:
        record("create_match", False, f"HTTP {r.status_code} {r.text[:300]}")
        return
    match = r.json()
    mid = match["id"]
    record("create_match", True, f"mid={mid} team_size={match['team_size']}")

    # Cast 'yes' votes for admin + each test user
    vote_ok = True
    r = requests.post(
        f"{BASE}/matches/{mid}/vote",
        headers=auth_hdr(admin_token),
        json={"vote": "yes"},
        timeout=30,
    )
    if r.status_code != 200:
        vote_ok = False
        record("vote_admin", False, f"HTTP {r.status_code} {r.text[:200]}")
    else:
        record("vote_admin", True)
    for u in test_users:
        r = requests.post(
            f"{BASE}/matches/{mid}/vote",
            headers=auth_hdr(u["token"]),
            json={"vote": "yes"},
            timeout=30,
        )
        if r.status_code != 200:
            vote_ok = False
            record(f"vote_{u['pos']}_{u['name']}", False, f"HTTP {r.status_code} {r.text[:200]}")
        else:
            record(f"vote_{u['pos']}_{u['name']}", True)
    record("all_votes_cast", vote_ok)

    # Generate lineup
    r = requests.post(
        f"{BASE}/matches/{mid}/generate-lineup",
        headers=auth_hdr(admin_token),
        timeout=30,
    )
    if r.status_code != 200:
        record("generate_lineup", False, f"HTTP {r.status_code} {r.text[:400]}")
        return
    match_full = r.json()
    lineup = match_full.get("lineup")
    if not lineup:
        record("generate_lineup", False, "no lineup in response")
        return
    team_a = lineup.get("team_a", [])
    team_b = lineup.get("team_b", [])
    team_c = lineup.get("team_c", []) or []
    reserves = lineup.get("reserves", []) or []
    record(
        "generate_lineup",
        True,
        f"team_a={len(team_a)} team_b={len(team_b)} team_c={len(team_c)} reserves={len(reserves)}",
    )

    # Verify players distributed (no crash, team_a + team_b non-empty)
    distribution_ok = len(team_a) > 0 and len(team_b) > 0
    record(
        "lineup_has_both_teams_populated",
        distribution_ok,
        f"team_a={len(team_a)} team_b={len(team_b)}",
    )

    # Verify total placed = expected (7 yes voters, team_size=3 → 6 on field + 1 overflow)
    total_assigned = len(team_a) + len(team_b) + len(team_c)
    expected_on_field = min(7, 3 * (2 if len(team_c) == 0 else 3))
    record(
        "lineup_total_players_on_field_ok",
        total_assigned == expected_on_field,
        f"on_field={total_assigned} expected={expected_on_field} (yes_voters=7, team_size=3)",
    )

    # Verify each player's preferred_position is preserved (not coerced to ANY)
    all_players = team_a + team_b + team_c + reserves
    positions_by_uid = {u["id"]: u["pos"] for u in test_users}
    positions_by_uid[admin_id] = "CAM"  # we set admin to CAM above
    preservation_failures = []
    for p in all_players:
        uid = p.get("user_id")
        expected = positions_by_uid.get(uid)
        if expected is None:
            continue
        got = p.get("preferred_position")
        if got != expected:
            preservation_failures.append(f"{p.get('name')}: expected {expected} got {got}")
    record(
        "preferred_position_preserved_in_lineup",
        len(preservation_failures) == 0,
        "; ".join(preservation_failures) if preservation_failures else "all positions preserved",
    )

    # Specific check: no player has preferred_position == 'ANY' (unless they registered as ANY, none here)
    coerced_to_any = [p for p in all_players if p.get("preferred_position") == "ANY"]
    record(
        "no_player_coerced_to_ANY",
        len(coerced_to_any) == 0,
        f"coerced count={len(coerced_to_any)}",
    )

    # Summary
    print("\n======= SUMMARY =======")
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print(f"Passed {passed}/{total}")
    for name, ok, detail in results:
        if not ok:
            print(f"  FAIL: {name} — {detail}")


if __name__ == "__main__":
    main()
