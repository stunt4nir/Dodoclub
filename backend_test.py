"""Backend tests for Availability poll + auto-match creation + GuestRef preferred_position.

Uses EXPO_PUBLIC_BACKEND_URL from /app/frontend/.env as base and /api prefix.
Cleans relevant Mongo collections before running so counts are deterministic.
"""
import os
import sys
import uuid
import re
from datetime import datetime, timezone, timedelta

import requests
from pymongo import MongoClient

# ---- Base URL ----
BASE = None
try:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break
except Exception as e:
    print("could not read frontend/.env", e)
if not BASE:
    print("No backend URL found"); sys.exit(1)
API = BASE + "/api"
print("Using API base:", API)

# ---- Mongo cleanup ----
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "club_dodo"
_mc = MongoClient(MONGO_URL)
_db = _mc[DB_NAME]

_db.availability.delete_many({})
_db.matches.delete_many({"auto_from_availability_date": {"$exists": True}})
_db.users.delete_many({"email": {"$regex": r"^avtest_"}})
_db.users.delete_many({"email": {"$regex": r"^guesttest_"}})
print("Mongo cleanup done")

ADMIN_EMAIL = "admin@clubdodo.com"
ADMIN_PASSWORD = "dodo2026"

results = []

def log(name, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name} — {detail}")
    results.append((name, ok, detail))
    return ok


def auth_header(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---- Admin login ----
r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
admin_tok = r.json()["token"]
admin = r.json()["user"]
admin_id = admin["id"]
print("Admin logged in:", admin_id)


def register_user(prefix, idx):
    email = f"{prefix}_{idx}_{uuid.uuid4().hex[:6]}@clubdodo.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email,
        "password": "password123",
        "name": f"{prefix.title()}{idx}",
        "shirt_number": (idx % 99) + 1,
    }, timeout=30)
    assert r.status_code == 200, f"register {email} failed: {r.status_code} {r.text}"
    return r.json()["token"], r.json()["user"]


# =====================================================
# A) Availability poll basics
# =====================================================

today = datetime.now(timezone.utc).date()
today_str = today.isoformat()
yesterday_str = (today - timedelta(days=1)).isoformat()
future8_str = (today + timedelta(days=8)).isoformat()

r = requests.get(f"{API}/availability", headers=auth_header(admin_tok), timeout=30)
ok = r.status_code == 200
data = r.json() if ok else {}
days = data.get("days") if ok else None
detail = f"status={r.status_code} threshold={data.get('threshold')} auto_team_size={data.get('auto_team_size')} days_len={len(days) if days else None}"
a1_ok = (
    ok and data.get("threshold") == 8 and data.get("auto_team_size") == 4
    and isinstance(days, list) and len(days) == 7
)
if a1_ok:
    d0 = days[0]
    required_keys = {"date", "yes_count", "no_count", "reserve_count", "my_vote", "yes", "no", "reserve", "auto_match_id"}
    missing = required_keys - set(d0.keys())
    a1_ok = not missing and re.match(r"^\d{4}-\d{2}-\d{2}$", d0["date"]) is not None
    detail += f" missing_keys={missing} first_day={d0.get('date')}"
log("A1 GET /availability structure", a1_ok, detail)

r = requests.post(f"{API}/availability", headers=auth_header(admin_tok),
                  json={"date": today_str, "vote": "yes"}, timeout=30)
a2a_ok = r.status_code == 200 and r.json().get("auto_match_id") is None
log("A2a POST today yes → auto_match_id null", a2a_ok, f"status={r.status_code} body={r.text[:200]}")

r = requests.get(f"{API}/availability", headers=auth_header(admin_tok), timeout=30)
day_today = next((d for d in r.json()["days"] if d["date"] == today_str), None)
a2b_ok = day_today is not None and day_today["my_vote"] == "yes" and day_today["yes_count"] == 1
log("A2b GET shows my_vote=yes, yes_count=1", a2b_ok, f"day={day_today}")

r = requests.post(f"{API}/availability", headers=auth_header(admin_tok),
                  json={"date": today_str, "vote": "no"}, timeout=30)
a3a_ok = r.status_code == 200
log("A3a POST update to no", a3a_ok, f"status={r.status_code}")

r = requests.get(f"{API}/availability", headers=auth_header(admin_tok), timeout=30)
day_today = next((d for d in r.json()["days"] if d["date"] == today_str), None)
a3b_ok = day_today["my_vote"] == "no" and day_today["yes_count"] == 0 and day_today["no_count"] == 1
log("A3b GET shows my_vote=no, yes=0 no=1", a3b_ok, f"day={day_today}")

r = requests.post(f"{API}/availability", headers=auth_header(admin_tok),
                  json={"date": yesterday_str, "vote": "yes"}, timeout=30)
a4a_ok = r.status_code == 400
log("A4a POST yesterday → 400", a4a_ok, f"status={r.status_code} body={r.text[:200]}")

r = requests.post(f"{API}/availability", headers=auth_header(admin_tok),
                  json={"date": future8_str, "vote": "yes"}, timeout=30)
a4b_ok = r.status_code == 400
log("A4b POST 8 days out → 400", a4b_ok, f"status={r.status_code} body={r.text[:200]}")

r = requests.post(f"{API}/availability", headers=auth_header(admin_tok),
                  json={"date": "2026/13/01", "vote": "yes"}, timeout=30)
a4c_ok = r.status_code == 400
log("A4c POST malformed '2026/13/01' → 400", a4c_ok, f"status={r.status_code} body={r.text[:200]}")

# =====================================================
# B) Auto-create match @ 8 yes votes
# =====================================================

date3_obj = today + timedelta(days=3)
date3 = date3_obj.isoformat()

p_tokens = []
p_users = []
for i in range(1, 8):
    tok, usr = register_user("avtest", i)
    p_tokens.append(tok); p_users.append(usr)
print(f"Registered 7 users: {[u['id'][:8] for u in p_users]}")

r = requests.post(f"{API}/availability", headers=auth_header(admin_tok),
                  json={"date": date3, "vote": "yes"}, timeout=30)
assert r.status_code == 200, r.text
for i in range(6):
    r = requests.post(f"{API}/availability", headers=auth_header(p_tokens[i]),
                      json={"date": date3, "vote": "yes"}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("auto_match_id") is None, f"should not auto-create yet: {r.json()}"

r = requests.get(f"{API}/availability", headers=auth_header(admin_tok), timeout=30)
day3 = next((d for d in r.json()["days"] if d["date"] == date3), None)
b5_ok = day3 is not None and day3["yes_count"] == 7 and day3["auto_match_id"] is None
log("B5 7 yes votes → yes_count=7, auto_match_id=null", b5_ok,
    f"yes_count={day3.get('yes_count') if day3 else None} auto_match_id={day3.get('auto_match_id') if day3 else None}")

r = requests.post(f"{API}/availability", headers=auth_header(p_tokens[6]),
                  json={"date": date3, "vote": "yes"}, timeout=30)
body = r.json() if r.status_code == 200 else {}
auto_mid = body.get("auto_match_id")
try:
    uuid.UUID(auto_mid)
    is_uuid = True
except Exception:
    is_uuid = False
b6a_ok = r.status_code == 200 and auto_mid is not None and is_uuid
log("B6a p7 yes → auto_match_id non-null UUID", b6a_ok, f"auto_match_id={auto_mid}")

r = requests.get(f"{API}/availability", headers=auth_header(admin_tok), timeout=30)
day3 = next((d for d in r.json()["days"] if d["date"] == date3), None)
b6b_ok = day3 and day3["auto_match_id"] == auto_mid and day3["yes_count"] == 8
log("B6b GET shows same auto_match_id, yes_count=8", b6b_ok,
    f"yes_count={day3['yes_count']} auto_match_id={day3['auto_match_id']}")

r = requests.get(f"{API}/matches/{auto_mid}", headers=auth_header(admin_tok), timeout=30)
b7_status_ok = r.status_code == 200
mdata = r.json() if b7_status_ok else {}
votes_list = mdata.get("votes", [])
vote_map = {v["user_id"]: v["vote"] for v in votes_list}
expected_ids = {admin_id} | {u["id"] for u in p_users}
dbm = _db.matches.find_one({"id": auto_mid})
b7_checks = {
    "status=200": b7_status_ok,
    "team_size=4": mdata.get("team_size") == 4,
    "match_type=friendly": mdata.get("match_type") == "friendly",
    "status=voting": mdata.get("status") == "voting",
    "auto_from_avail_date matches": bool(dbm) and dbm.get("auto_from_availability_date") == date3,
    "all 8 user_ids present": set(vote_map.keys()) == expected_ids,
    "all votes=yes": all(v == "yes" for v in vote_map.values()) and len(vote_map) == 8,
}
b7_ok = all(b7_checks.values())
log("B7 GET /matches/{auto_mid} correctness", b7_ok, f"checks={b7_checks}")

# B8. Idempotent
tok9, u9 = register_user("avtest", 9)
r = requests.post(f"{API}/availability", headers=auth_header(tok9),
                  json={"date": date3, "vote": "yes"}, timeout=30)
b8_ok = r.status_code == 200 and r.json().get("auto_match_id") == auto_mid
log("B8 another yes returns same auto_match_id (idempotent)", b8_ok,
    f"status={r.status_code} returned={r.json().get('auto_match_id')}")

# B9. Exactly one match
count = _db.matches.count_documents({"auto_from_availability_date": date3})
b9_ok = count == 1
log("B9 exactly one match auto-created for date3", b9_ok, f"count={count}")

# =====================================================
# C) GuestRef preferred_position
# =====================================================

future_match_date = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
r = requests.post(f"{API}/matches", headers=auth_header(admin_tok), json={
    "title": "Guest Lineup Test",
    "date": future_match_date,
    "team_size": 4,
    "match_type": "friendly",
}, timeout=30)
assert r.status_code == 200, r.text
gmid = r.json()["id"]
print("Created friendly match:", gmid)

dummies = []
for i in range(3):
    tok, usr = register_user("guesttest", i)
    dummies.append((tok, usr))
for tok, usr in [(admin_tok, admin)] + dummies:
    r = requests.post(f"{API}/matches/{gmid}/vote", headers=auth_header(tok), json={"vote": "yes"}, timeout=30)
    assert r.status_code == 200, r.text

reg_ids = [u["id"] for _, u in dummies]
# C11
lineup_body = {
    "team_a": [{"name": "Alice Guest", "shirt_number": 99, "preferred_position": "CAM"}],
    "team_b": reg_ids,
    "team_c": [],
    "reserves": [],
}
r = requests.put(f"{API}/matches/{gmid}/lineup", headers=auth_header(admin_tok),
                 json=lineup_body, timeout=30)
c11a_ok = r.status_code == 200
log("C11a PUT lineup with guest preferred_position=CAM → 200", c11a_ok,
    f"status={r.status_code} body={r.text[:300]}")

r = requests.get(f"{API}/matches/{gmid}", headers=auth_header(admin_tok), timeout=30)
match = r.json()
team_a = match["lineup"]["team_a"]
guest = team_a[0] if team_a else None
c11b_ok = bool(guest) and guest.get("preferred_position") == "CAM" and guest.get("preferred_positions") == ["CAM"]
log("C11b guest has preferred_position=CAM and preferred_positions=['CAM']", c11b_ok, f"guest={guest}")

# C12
lineup_body2 = {
    "team_a": [{"name": "Bob Guest", "shirt_number": 88}],
    "team_b": reg_ids,
    "team_c": [],
    "reserves": [],
}
r = requests.put(f"{API}/matches/{gmid}/lineup", headers=auth_header(admin_tok),
                 json=lineup_body2, timeout=30)
c12a_ok = r.status_code == 200
log("C12a PUT lineup with guest preferred_position omitted → 200", c12a_ok, f"status={r.status_code}")

r = requests.get(f"{API}/matches/{gmid}", headers=auth_header(admin_tok), timeout=30)
match = r.json()
guest2 = match["lineup"]["team_a"][0] if match["lineup"]["team_a"] else None
c12b_ok = bool(guest2) and guest2.get("preferred_position") is None and guest2.get("preferred_positions") == []
log("C12b guest has preferred_position=null and preferred_positions=[]", c12b_ok, f"guest={guest2}")

# C13
lineup_body3 = {
    "team_a": [{"name": "Bad Guest", "shirt_number": 77, "preferred_position": "ZZZ"}],
    "team_b": reg_ids,
    "team_c": [],
    "reserves": [],
}
r = requests.put(f"{API}/matches/{gmid}/lineup", headers=auth_header(admin_tok),
                 json=lineup_body3, timeout=30)
c13_ok = r.status_code == 422
log("C13 invalid preferred_position=ZZZ → 422", c13_ok, f"status={r.status_code} body={r.text[:200]}")

# =====================================================
# D) Unauth
# =====================================================

r = requests.get(f"{API}/availability", timeout=30)
d14_ok = r.status_code == 401
log("D14 GET /availability without auth → 401", d14_ok, f"status={r.status_code}")

r = requests.post(f"{API}/availability", json={"date": today_str, "vote": "yes"}, timeout=30)
d15_ok = r.status_code == 401
log("D15 POST /availability without auth → 401", d15_ok, f"status={r.status_code}")

# =====================================================
# Cleanup
# =====================================================
try:
    _db.availability.delete_many({})
    _db.matches.delete_many({"auto_from_availability_date": {"$exists": True}})
    _db.users.delete_many({"email": {"$regex": r"^avtest_"}})
    _db.users.delete_many({"email": {"$regex": r"^guesttest_"}})
    requests.delete(f"{API}/matches/{gmid}", headers=auth_header(admin_tok), timeout=30)
except Exception as e:
    print("cleanup warn:", e)

# ---- Summary ----
passed = sum(1 for _, ok, _ in results if ok)
failed = [name for name, ok, _ in results if not ok]
print(f"\n==== SUMMARY ====")
print(f"Total: {len(results)}  Passed: {passed}  Failed: {len(failed)}")
if failed:
    print("Failed tests:")
    for n in failed:
        print(" -", n)
sys.exit(0 if not failed else 1)
