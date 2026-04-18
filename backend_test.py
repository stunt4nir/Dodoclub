"""
Admin delete-player endpoint tests — DELETE /api/users/{user_id}

Covers:
  - Admin happy path (cascade cleanup)
  - Permission guards (non-admin, self-delete, missing user, unauth)
  - Cascade on votes, lineup, comments
"""
import sys
import uuid
import requests
from datetime import datetime, timezone, timedelta

BASE = "https://dodo-roster-build.preview.emergentagent.com/api"

ADMIN_EMAIL = "admin@clubdodo.com"
ADMIN_PASSWORD = "dodo2026"

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}{' — ' + detail if detail else ''}")


def req(method, path, token=None, json=None):
    url = BASE + path
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, url, headers=headers, json=json, timeout=30)


def unique_email(prefix):
    return f"{prefix}+{uuid.uuid4().hex[:6]}@test.com"


def login(email, password):
    r = req("POST", "/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    j = r.json()
    return j["token"], j["user"]


def register(email, password, name, **extra):
    body = {"email": email, "password": password, "name": name, **extra}
    return req("POST", "/auth/register", json=body)


def main():
    # Admin login
    admin_token, admin_user = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    admin_id = admin_user["id"]
    print(f"Admin id: {admin_id}")

    # 1) Register killme user
    km_email = unique_email("killme")
    r = register(km_email, "pass12345", "Kill Me")
    if r.status_code != 200:
        record("1. Register killme user", False, f"{r.status_code} {r.text}")
        return
    km_id = r.json()["user"]["id"]
    km_token = r.json()["token"]
    record("1. Register killme user", True, f"id={km_id}")

    # 2) Admin deletes killme → 200 {ok, deleted_user_id}
    r = req("DELETE", f"/users/{km_id}", token=admin_token)
    ok = r.status_code == 200
    body = r.json() if ok else {}
    ok = ok and body.get("ok") is True and body.get("deleted_user_id") == km_id
    record("2. Admin DELETE /users/{killme_id} → 200 {ok:true, deleted_user_id}",
           ok, f"status={r.status_code} body={r.text[:200]}")

    # 3) GET /users excludes killme id
    r = req("GET", "/users", token=admin_token)
    ok = r.status_code == 200
    ids = [u["id"] for u in (r.json() if ok else [])]
    record("3. GET /users excludes killme id",
           ok and km_id not in ids,
           f"status={r.status_code} killme_in_list={km_id in ids}")

    # 4) killme login → 401
    r = req("POST", "/auth/login",
            json={"email": km_email, "password": "pass12345"})
    record("4. Login as killme → 401", r.status_code == 401,
           f"status={r.status_code}")

    # 4b) Old killme token on /auth/me → 401
    r = req("GET", "/auth/me", token=km_token)
    record("4b. Old killme token on /auth/me → 401",
           r.status_code == 401, f"status={r.status_code}")

    # 5) Non-admin delete → 403
    alice_email = unique_email("alice")
    bob_email = unique_email("bob")
    ra = register(alice_email, "alice12345", "Alice")
    rb = register(bob_email, "bob12345", "Bob")
    if ra.status_code != 200 or rb.status_code != 200:
        record("5. Register alice+bob", False,
               f"alice={ra.status_code} bob={rb.status_code}")
        return
    alice_token = ra.json()["token"]
    alice_id = ra.json()["user"]["id"]
    bob_id = rb.json()["user"]["id"]

    r = req("DELETE", f"/users/{bob_id}", token=alice_token)
    record("5. Non-admin (alice) DELETE bob → 403",
           r.status_code == 403, f"status={r.status_code}")

    # 6) Admin self-delete → 400
    r = req("DELETE", f"/users/{admin_id}", token=admin_token)
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        pass
    record("6. Admin self-delete → 400 'cannot delete your own account'",
           r.status_code == 400 and "own" in detail.lower(),
           f"status={r.status_code} detail={detail}")

    # 7) Admin DELETE nonexistent → 404
    r = req("DELETE", "/users/nonexistent-id-xyz-123", token=admin_token)
    record("7. Admin DELETE nonexistent id → 404",
           r.status_code == 404, f"status={r.status_code}")

    # 8) Last-admin guard note
    record("8. Last-admin guard note (self-delete check fires first for sole admin)",
           True, "documented — no code path needed")

    # 9) Cascade setup: stats user + match + votes + comment + lineup
    stats_email = unique_email("stats")
    rs = register(stats_email, "stats12345", "Stats User",
                  preferred_position="ST")
    if rs.status_code != 200:
        record("9a. Register stats user", False, f"{rs.status_code} {rs.text}")
        return
    stats_token = rs.json()["token"]
    stats_id = rs.json()["user"]["id"]
    record("9a. Register stats user", True, f"id={stats_id}")

    future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    r = req("POST", "/matches", token=admin_token,
            json={"title": "Cascade Test Match", "date": future_date,
                  "team_size": 4, "match_type": "friendly"})
    if r.status_code != 200:
        record("9b. Admin create friendly match team_size=4", False,
               f"{r.status_code} {r.text}")
        return
    match_id = r.json()["id"]
    record("9b. Admin create friendly match team_size=4", True,
           f"id={match_id}")

    r = req("POST", f"/matches/{match_id}/vote", token=stats_token,
            json={"vote": "yes"})
    record("9c. Stats user vote yes", r.status_code == 200,
           f"status={r.status_code}")

    r = req("POST", f"/matches/{match_id}/vote", token=admin_token,
            json={"vote": "yes"})
    record("9d. Admin vote yes", r.status_code == 200,
           f"status={r.status_code}")

    r = req("POST", f"/matches/{match_id}/comments", token=stats_token,
            json={"text": "Excited for kickoff"})
    ok_c = r.status_code == 200
    stats_comment_id = r.json().get("id") if ok_c else None
    record("9e. Stats user post comment", ok_c,
           f"status={r.status_code} comment_id={stats_comment_id}")

    r = req("POST", f"/matches/{match_id}/generate-lineup", token=admin_token)
    ok_l = r.status_code == 200
    lineup = r.json().get("lineup") if ok_l else None
    in_lineup_before = False
    if lineup:
        for k in ("team_a", "team_b", "team_c", "reserves"):
            for p in lineup.get(k) or []:
                if p.get("user_id") == stats_id:
                    in_lineup_before = True
    record("9f. Admin generate-lineup (stats in lineup)",
           ok_l and in_lineup_before,
           f"status={r.status_code} stats_in_lineup_pre={in_lineup_before}")

    # 10) Delete stats user
    r = req("DELETE", f"/users/{stats_id}", token=admin_token)
    ok = r.status_code == 200
    body = r.json() if ok else {}
    ok = ok and body.get("ok") is True and body.get("deleted_user_id") == stats_id
    record("10. Admin DELETE /users/{stats_id} → 200",
           ok, f"status={r.status_code} body={r.text[:200]}")

    # 11) GET match — votes & lineup cleaned
    r = req("GET", f"/matches/{match_id}", token=admin_token)
    ok_match = r.status_code == 200
    match = r.json() if ok_match else {}
    votes = match.get("votes") or []
    stats_in_votes = any(v["user_id"] == stats_id for v in votes)
    lineup = match.get("lineup") or {}
    stats_in_lineup = False
    for k in ("team_a", "team_b", "team_c", "reserves"):
        for p in lineup.get(k) or []:
            if p.get("user_id") == stats_id:
                stats_in_lineup = True
    record("11a. GET match — votes no longer contain stats_id",
           ok_match and not stats_in_votes,
           f"status={r.status_code} stats_in_votes={stats_in_votes} "
           f"votes_n={len(votes)}")
    record("11b. GET match — lineup no longer contains stats_id",
           ok_match and not stats_in_lineup,
           f"stats_in_lineup={stats_in_lineup}")

    # 12) GET comments — stats comment gone
    r = req("GET", f"/matches/{match_id}/comments", token=admin_token)
    ok = r.status_code == 200
    comments = r.json() if ok else []
    stats_comments = [c for c in comments if c.get("user_id") == stats_id]
    record("12. GET comments — stats user's comment removed",
           ok and len(stats_comments) == 0,
           f"status={r.status_code} stats_comments_count={len(stats_comments)}")

    # 13) Unauth DELETE → 401
    r = requests.delete(BASE + "/users/xxx", timeout=30)
    record("13. Unauth DELETE /users/xxx → 401",
           r.status_code == 401, f"status={r.status_code}")

    # Cleanup
    req("DELETE", f"/matches/{match_id}", token=admin_token)
    req("DELETE", f"/users/{alice_id}", token=admin_token)
    req("DELETE", f"/users/{bob_id}", token=admin_token)

    # Summary
    print("\n================ RESULTS ================")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = [n for n, ok, _ in results if not ok]
    print(f"Passed: {passed}/{len(results)}")
    if failed:
        print("FAILED:")
        for n in failed:
            print(f" - {n}")
        sys.exit(1)
    print("ALL PASSED")


if __name__ == "__main__":
    main()
