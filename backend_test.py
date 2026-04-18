"""Backend tests for Club Dodo - team_size validation, match comments CRUD, cascade delete."""
import os
import uuid
import requests
from datetime import datetime, timezone, timedelta

BASE = os.environ.get("BACKEND_URL", "https://dodo-roster-build.preview.emergentagent.com") + "/api"
ADMIN_EMAIL = "admin@clubdodo.com"
ADMIN_PASSWORD = "dodo2026"

results = []
def record(case, ok, detail=""):
    results.append((case, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {case} — {detail}")


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def login(email, password):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()


def register(email, password, name, shirt_number=None):
    body = {"email": email, "password": password, "name": name}
    if shirt_number is not None:
        body["shirt_number"] = shirt_number
    r = requests.post(f"{BASE}/auth/register", json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def iso_future(days=7):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def main():
    admin = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    admin_token = admin["token"]
    admin_id = admin["user"]["id"]
    record("admin login", True, f"admin_id={admin_id}")

    # ---------- A) team_size validation ----------
    r = requests.post(f"{BASE}/matches", headers=auth_headers(admin_token),
                      json={"title": "Invalid 3v3", "date": iso_future(3), "team_size": 3, "match_type": "friendly"}, timeout=30)
    record("A.2 team_size=3 rejected", r.status_code == 422, f"status={r.status_code} body={r.text[:200]}")

    r = requests.post(f"{BASE}/matches", headers=auth_headers(admin_token),
                      json={"title": "Valid 4v4", "date": iso_future(3), "team_size": 4, "match_type": "friendly"}, timeout=30)
    ok4 = r.status_code == 200 and r.json().get("team_size") == 4
    record("A.3 team_size=4 accepted", ok4, f"status={r.status_code}")
    match4_id = r.json().get("id") if r.status_code == 200 else None

    r = requests.post(f"{BASE}/matches", headers=auth_headers(admin_token),
                      json={"title": "Valid 11v11", "date": iso_future(4), "team_size": 11, "match_type": "friendly"}, timeout=30)
    ok11 = r.status_code == 200 and r.json().get("team_size") == 11
    record("A.4a team_size=11 accepted", ok11, f"status={r.status_code}")
    match11_id = r.json().get("id") if r.status_code == 200 else None

    r = requests.post(f"{BASE}/matches", headers=auth_headers(admin_token),
                      json={"title": "Invalid 12v12", "date": iso_future(4), "team_size": 12, "match_type": "friendly"}, timeout=30)
    record("A.4b team_size=12 rejected", r.status_code == 422, f"status={r.status_code}")

    # ---------- B) Comments CRUD ----------
    r = requests.get(f"{BASE}/matches/{match4_id}/comments", headers=auth_headers(admin_token), timeout=30)
    record("B.5 GET comments empty", r.status_code == 200 and r.json() == [], f"status={r.status_code}")

    r = requests.post(f"{BASE}/matches/{match4_id}/comments", headers=auth_headers(admin_token),
                      json={"text": "Hello match!"}, timeout=30)
    admin_comment_id = None
    if r.status_code == 200:
        body = r.json()
        checks = {
            "id_present": bool(body.get("id")),
            "user_id==admin": body.get("user_id") == admin_id,
            "name_present": "name" in body,
            "profile_picture_present": "profile_picture" in body,
            "text_correct": body.get("text") == "Hello match!",
            "created_at_present": bool(body.get("created_at")),
        }
        admin_comment_id = body.get("id")
        record("B.6 POST admin comment + fields", all(checks.values()), f"checks={checks}")
    else:
        record("B.6 POST admin comment + fields", False, f"status={r.status_code} body={r.text[:200]}")

    r = requests.get(f"{BASE}/matches/{match4_id}/comments", headers=auth_headers(admin_token), timeout=30)
    record("B.6b GET after admin post = 1", r.status_code == 200 and len(r.json()) == 1,
           f"n={len(r.json()) if r.status_code==200 else 'ERR'}")

    # Register + login regular user
    uniq = uuid.uuid4().hex[:8]
    user_email = f"marco.rossi.{uniq}@example.com"
    user_password = "Str0ngP@ss!"
    reg = register(user_email, user_password, "Marco Rossi", shirt_number=9)
    user_id = reg["user"]["id"]
    usr = login(user_email, user_password)
    user_token = usr["token"]
    record("B.7a register+login user", True, f"user_id={user_id}")

    r = requests.post(f"{BASE}/matches/{match4_id}/comments", headers=auth_headers(user_token),
                      json={"text": "I'm in"}, timeout=30)
    user_comment_id = r.json().get("id") if r.status_code == 200 else None
    record("B.7b POST user comment", r.status_code == 200 and r.json().get("user_id") == user_id, f"status={r.status_code}")

    r = requests.get(f"{BASE}/matches/{match4_id}/comments", headers=auth_headers(user_token), timeout=30)
    if r.status_code == 200:
        items = r.json()
        ok7c = (len(items) == 2 and items[0]["user_id"] == admin_id
                and items[1]["user_id"] == user_id
                and items[0]["created_at"] <= items[1]["created_at"])
        record("B.7c GET 2 items oldest-first", ok7c, f"n={len(items)}")
    else:
        record("B.7c GET 2 items oldest-first", False, f"status={r.status_code}")

    # validation
    r = requests.post(f"{BASE}/matches/{match4_id}/comments", headers=auth_headers(user_token), json={"text": ""}, timeout=30)
    record("B.8a empty 422", r.status_code == 422, f"status={r.status_code}")

    r = requests.post(f"{BASE}/matches/{match4_id}/comments", headers=auth_headers(user_token), json={"text": "x" * 501}, timeout=30)
    record("B.8b 501 chars 422", r.status_code == 422, f"status={r.status_code}")

    r = requests.post(f"{BASE}/matches/{match4_id}/comments", headers=auth_headers(user_token), json={"text": "y" * 500}, timeout=30)
    len500_id = r.json().get("id") if r.status_code == 200 else None
    record("B.8c 500 chars 200", r.status_code == 200, f"status={r.status_code}")

    # clean up len-500 so the counts for steps 10/11 are deterministic
    if len500_id:
        requests.delete(f"{BASE}/matches/{match4_id}/comments/{len500_id}",
                        headers=auth_headers(user_token), timeout=30)

    # 9. user deletes admin's -> 403
    r = requests.delete(f"{BASE}/matches/{match4_id}/comments/{admin_comment_id}",
                        headers=auth_headers(user_token), timeout=30)
    record("B.9 user deletes admin comment 403", r.status_code == 403, f"status={r.status_code}")

    # 10. user deletes own -> 200
    r = requests.delete(f"{BASE}/matches/{match4_id}/comments/{user_comment_id}",
                        headers=auth_headers(user_token), timeout=30)
    record("B.10a user deletes own 200", r.status_code == 200, f"status={r.status_code}")

    r = requests.get(f"{BASE}/matches/{match4_id}/comments", headers=auth_headers(admin_token), timeout=30)
    record("B.10b GET after 1 item", r.status_code == 200 and len(r.json()) == 1,
           f"n={len(r.json()) if r.status_code==200 else 'ERR'}")

    # 11. admin deletes remaining
    r = requests.delete(f"{BASE}/matches/{match4_id}/comments/{admin_comment_id}",
                        headers=auth_headers(admin_token), timeout=30)
    record("B.11a admin deletes remaining 200", r.status_code == 200, f"status={r.status_code}")

    r = requests.get(f"{BASE}/matches/{match4_id}/comments", headers=auth_headers(admin_token), timeout=30)
    record("B.11b GET returns []", r.status_code == 200 and r.json() == [], f"body={r.text[:100]}")

    # 12. non-existent match id -> 404
    fake = str(uuid.uuid4())
    r = requests.get(f"{BASE}/matches/{fake}/comments", headers=auth_headers(admin_token), timeout=30)
    record("B.12a GET nonexistent 404", r.status_code == 404, f"status={r.status_code}")
    r = requests.post(f"{BASE}/matches/{fake}/comments", headers=auth_headers(admin_token), json={"text": "hi"}, timeout=30)
    record("B.12b POST nonexistent 404", r.status_code == 404, f"status={r.status_code}")
    r = requests.delete(f"{BASE}/matches/{fake}/comments/{fake}", headers=auth_headers(admin_token), timeout=30)
    record("B.12c DELETE nonexistent 404", r.status_code == 404, f"status={r.status_code}")

    # 13. no auth -> 401
    r = requests.get(f"{BASE}/matches/{match4_id}/comments", timeout=30)
    record("B.13a GET no-auth 401", r.status_code == 401, f"status={r.status_code}")
    r = requests.post(f"{BASE}/matches/{match4_id}/comments", json={"text": "no auth"}, timeout=30)
    record("B.13b POST no-auth 401", r.status_code == 401, f"status={r.status_code}")
    r = requests.delete(f"{BASE}/matches/{match4_id}/comments/{fake}", timeout=30)
    record("B.13c DELETE no-auth 401", r.status_code == 401, f"status={r.status_code}")

    # ---------- C) Cascade delete ----------
    r = requests.post(f"{BASE}/matches", headers=auth_headers(admin_token),
                      json={"title": "Cascade Test", "date": iso_future(5), "team_size": 5, "match_type": "friendly"}, timeout=30)
    cmid = r.json()["id"]
    requests.post(f"{BASE}/matches/{cmid}/comments", headers=auth_headers(admin_token), json={"text": "c1"}, timeout=30)
    requests.post(f"{BASE}/matches/{cmid}/comments", headers=auth_headers(user_token), json={"text": "c2"}, timeout=30)

    r = requests.get(f"{BASE}/matches/{cmid}/comments", headers=auth_headers(admin_token), timeout=30)
    record("C.14a 2 comments before delete", r.status_code == 200 and len(r.json()) == 2,
           f"n={len(r.json()) if r.status_code==200 else 'ERR'}")

    r = requests.delete(f"{BASE}/matches/{cmid}", headers=auth_headers(admin_token), timeout=30)
    record("C.14b DELETE match 200", r.status_code == 200, f"status={r.status_code}")

    r = requests.get(f"{BASE}/matches/{cmid}/comments", headers=auth_headers(admin_token), timeout=30)
    record("C.14c GET comments after match delete 404", r.status_code == 404, f"status={r.status_code}")

    # cleanup remaining matches
    for mid in (match4_id, match11_id):
        if mid:
            requests.delete(f"{BASE}/matches/{mid}", headers=auth_headers(admin_token), timeout=30)

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n==== {passed}/{total} passed ====")
    for case, ok, detail in results:
        if not ok:
            print(f"  FAIL: {case} — {detail}")
    return passed == total


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)
