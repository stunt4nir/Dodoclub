"""Backend tests for POST /api/admin/reset/players and related permissions.

Covers the full specification from the review request:
- Admin-only reset wipes non-admin users, scrubs votes/lineup/comments,
  preserves matches and admin stats.
- Permission (401/403) and idempotency edge cases.
- Regression checks for the two other admin reset endpoints.
"""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import requests

BASE = "https://dodo-roster-build.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@clubdodo.com"
ADMIN_PASSWORD = "dodo2026"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def rand_email(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"


results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name} {('- ' + detail) if detail else ''}")


def login(email, password):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    return r


def register(email, name, pwd="password123"):
    return requests.post(
        f"{BASE}/auth/register",
        json={"email": email, "password": pwd, "name": name, "preferred_position": "CM"},
    )


def main():
    # Clean slate: first login admin & reset fully
    r = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    admin_token = r.json()["token"]
    admin_id = r.json()["user"]["id"]

    # Full reset to clear previous test data
    rr = requests.post(f"{BASE}/admin/reset", headers=auth(admin_token))
    assert rr.status_code == 200, rr.text
    print("Initial clean slate via /admin/reset OK")

    # --- Setup: 3 regular users ---
    p_emails = [rand_email("p1"), rand_email("p2"), rand_email("p3")]
    p_names = ["Lionel Parker", "Marco Duval", "Henrik Sorensen"]
    p_tokens = []
    p_ids = []
    for e, n in zip(p_emails, p_names):
        rr = register(e, n)
        ok = rr.status_code == 200
        record(f"Register {n}", ok, rr.text[:100] if not ok else "")
        if not ok:
            return
        p_tokens.append(rr.json()["token"])
        p_ids.append(rr.json()["user"]["id"])

    # --- Create friendly match team_size=4 ---
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    rr = requests.post(
        f"{BASE}/matches",
        headers=auth(admin_token),
        json={
            "title": "Reset Players Test Match",
            "date": future,
            "location": "Dodo Pitch",
            "team_size": 4,
            "match_type": "friendly",
        },
    )
    ok = rr.status_code == 200
    record("Create friendly match (team_size=4)", ok, rr.text[:200] if not ok else "")
    if not ok:
        return
    mid = rr.json()["id"]

    # --- Votes: admin + all 3 regulars vote yes ---
    for tok, label in zip([admin_token] + p_tokens, ["admin", "p1", "p2", "p3"]):
        rr = requests.post(
            f"{BASE}/matches/{mid}/vote", headers=auth(tok), json={"vote": "yes"}
        )
        record(f"Vote yes by {label}", rr.status_code == 200)

    # --- Comments: p1 x2, admin x1 ---
    cids_p1 = []
    for txt in ["Can't wait!", "Bringing the thunder"]:
        rr = requests.post(
            f"{BASE}/matches/{mid}/comments",
            headers=auth(p_tokens[0]),
            json={"text": txt},
        )
        record(f"p1 comment '{txt}'", rr.status_code == 200)
        if rr.status_code == 200:
            cids_p1.append(rr.json()["id"])
    rr = requests.post(
        f"{BASE}/matches/{mid}/comments",
        headers=auth(admin_token),
        json={"text": "See you all there."},
    )
    record("Admin comment", rr.status_code == 200)
    admin_cid = rr.json()["id"] if rr.status_code == 200 else None

    # --- Generate lineup ---
    rr = requests.post(
        f"{BASE}/matches/{mid}/generate-lineup", headers=auth(admin_token)
    )
    ok = rr.status_code == 200
    record("POST generate-lineup -> 200", ok, rr.text[:200] if not ok else "")

    # Capture admin stats baseline (should be untouched by reset/players)
    rr = requests.get(f"{BASE}/auth/me", headers=auth(admin_token))
    admin_before = rr.json()
    admin_stats_before = {
        k: admin_before.get(k)
        for k in ("goals", "assists", "matches_played", "wins", "draws", "losses", "league_points", "rating")
    }

    # --- 5. Call POST /api/admin/reset/players as admin ---
    rr = requests.post(f"{BASE}/admin/reset/players", headers=auth(admin_token))
    body = rr.json() if rr.headers.get("content-type", "").startswith("application/json") else {}
    ok = rr.status_code == 200 and body.get("ok") is True and body.get("users_deleted") == 3
    record(
        "POST /admin/reset/players -> 200 {ok:true, users_deleted:3}",
        ok,
        f"status={rr.status_code} body={body}",
    )

    # --- 6. GET /users -> only admin ---
    rr = requests.get(f"{BASE}/users", headers=auth(admin_token))
    users = rr.json() if rr.status_code == 200 else []
    ok = (
        rr.status_code == 200
        and len(users) == 1
        and users[0]["id"] == admin_id
        and users[0]["role"] == "admin"
    )
    record(
        "GET /users after reset -> only admin remains",
        ok,
        f"count={len(users)} ids={[u['id'] for u in users]}",
    )

    # --- 7. GET /matches/{mid} still exists, votes scrubbed, lineup scrubbed ---
    rr = requests.get(f"{BASE}/matches/{mid}", headers=auth(admin_token))
    ok_match = rr.status_code == 200
    record("Match still exists after reset", ok_match, rr.text[:200] if not ok_match else "")
    if ok_match:
        mdata = rr.json()
        vote_user_ids = [v["user_id"] for v in mdata.get("votes", [])]
        scrub_ok = all(pid not in vote_user_ids for pid in p_ids) and admin_id in vote_user_ids
        record(
            "Match votes contain only admin (no p1/p2/p3)",
            scrub_ok,
            f"vote_user_ids={vote_user_ids}",
        )
        lineup = mdata.get("lineup") or {}
        all_team_uids = []
        for k in ("team_a", "team_b", "team_c", "reserves"):
            for p in lineup.get(k) or []:
                all_team_uids.append(p.get("user_id"))
        lineup_scrub_ok = all(pid not in all_team_uids for pid in p_ids)
        admin_in_lineup = admin_id in all_team_uids
        record(
            "Lineup team_a/b/c/reserves no longer contain p1/p2/p3",
            lineup_scrub_ok,
            f"uids={all_team_uids}",
        )
        record("Lineup still contains admin", admin_in_lineup, f"uids={all_team_uids}")

    # --- 8. GET comments -> only admin's remains ---
    rr = requests.get(f"{BASE}/matches/{mid}/comments", headers=auth(admin_token))
    comments = rr.json() if rr.status_code == 200 else []
    ok = (
        rr.status_code == 200
        and len(comments) == 1
        and comments[0]["user_id"] == admin_id
    )
    record(
        "GET comments -> only admin's 1 comment remains",
        ok,
        f"count={len(comments)} ids={[c.get('user_id') for c in comments]}",
    )

    # --- 9. Admin career stats unchanged ---
    rr = requests.get(f"{BASE}/auth/me", headers=auth(admin_token))
    admin_after = rr.json()
    admin_stats_after = {
        k: admin_after.get(k)
        for k in ("goals", "assists", "matches_played", "wins", "draws", "losses", "league_points", "rating")
    }
    ok = admin_stats_before == admin_stats_after
    record(
        "Admin career stats unchanged by reset/players",
        ok,
        f"before={admin_stats_before} after={admin_stats_after}",
    )

    # --- 10. p1 login with old creds -> 401 ---
    rr = login(p_emails[0], "password123")
    record("p1 login after reset -> 401", rr.status_code == 401, f"got={rr.status_code}")

    # --- 11. Register a new regular user, then call reset/players as them -> 403 ---
    new_email = rand_email("reg")
    rr = register(new_email, "Sam Carter")
    record("Register post-reset regular user", rr.status_code == 200)
    reg_token = rr.json()["token"] if rr.status_code == 200 else None
    if reg_token:
        rr = requests.post(f"{BASE}/admin/reset/players", headers=auth(reg_token))
        record(
            "Non-admin POST /admin/reset/players -> 403",
            rr.status_code == 403,
            f"got={rr.status_code} body={rr.text[:120]}",
        )

    # --- 12. No Authorization header -> 401 ---
    rr = requests.post(f"{BASE}/admin/reset/players")
    record(
        "Unauthenticated POST /admin/reset/players -> 401",
        rr.status_code == 401,
        f"got={rr.status_code}",
    )

    # --- 13. Idempotent when 0 non-admins exist ---
    # First, clear the 1 regular user we just created via admin reset/players
    rr = requests.post(f"{BASE}/admin/reset/players", headers=auth(admin_token))
    # This should delete the new regular user (1)
    ok = rr.status_code == 200 and rr.json().get("users_deleted") == 1
    record(
        "Second /admin/reset/players removes new regular -> users_deleted=1",
        ok,
        f"body={rr.text[:120]}",
    )
    # Now with zero non-admins, call again
    rr = requests.post(f"{BASE}/admin/reset/players", headers=auth(admin_token))
    body = rr.json() if rr.status_code == 200 else {}
    ok = rr.status_code == 200 and body.get("ok") is True and body.get("users_deleted") == 0
    record(
        "Idempotent /admin/reset/players when no non-admins -> users_deleted=0",
        ok,
        f"body={body}",
    )

    # --- 14. Regression: /admin/reset/matches still works ---
    rr = requests.post(f"{BASE}/admin/reset/matches", headers=auth(admin_token))
    body = rr.json() if rr.status_code == 200 else {}
    ok = rr.status_code == 200 and body.get("ok") is True
    record(
        "Regression: POST /admin/reset/matches -> 200",
        ok,
        f"status={rr.status_code} body={body}",
    )

    # --- 15. Regression: /admin/reset still works ---
    rr = requests.post(f"{BASE}/admin/reset", headers=auth(admin_token))
    body = rr.json() if rr.status_code == 200 else {}
    ok = rr.status_code == 200 and body.get("ok") is True
    record(
        "Regression: POST /admin/reset -> 200",
        ok,
        f"status={rr.status_code} body={body}",
    )

    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} PASS")
    if passed != total:
        print("\nFailures:")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}: {detail}")
    return passed == total


if __name__ == "__main__":
    main()
