"""
Review request tests:
- Test A: forgot-password DEV_MODE gating
- Test B: auth/matches/config regression smoke
Uses public backend URL (EXPO_PUBLIC_BACKEND_URL) with /api prefix.
"""

import os
import sys
import time
import subprocess
import requests

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://dodo-roster-build.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@clubdodo.com"
ORIG_PASSWORD = "dodo2026"
TEMP_PASSWORD = "TempDodoPass!42"

results = []


def record(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}  {detail}")
    results.append((name, passed, detail))


def forgot(email):
    return requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=15)


def reset(email, code, new_pw):
    return requests.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": code, "new_password": new_pw},
        timeout=15,
    )


def login(email, password):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)


def set_dev_mode(value: str):
    """Rewrite DEV_MODE in /app/backend/.env and restart backend."""
    env_path = "/app/backend/.env"
    with open(env_path, "r") as f:
        lines = f.readlines()
    new_lines = []
    found = False
    for ln in lines:
        if ln.strip().startswith("DEV_MODE"):
            new_lines.append(f'DEV_MODE="{value}"\n')
            found = True
        else:
            new_lines.append(ln)
    if not found:
        new_lines.append(f'DEV_MODE="{value}"\n')
    with open(env_path, "w") as f:
        f.writelines(new_lines)
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=False, capture_output=True)
    # wait for backend
    for _ in range(30):
        try:
            r = requests.get(f"{API}/config", timeout=3)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)


# --- Test A1: DEV_MODE=1 returns code ---
print("\n=== STEP 1: forgot-password with DEV_MODE=1 ===")
r = forgot(ADMIN_EMAIL)
code_dev = None
if r.status_code == 200:
    data = r.json()
    code_dev = data.get("dev_code")
    ok = isinstance(code_dev, str) and len(code_dev) == 6 and code_dev.isdigit()
    record("A1 forgot-password DEV_MODE=1 returns 6-digit dev_code", ok, f"dev_code={code_dev} body={data}")
else:
    record("A1 forgot-password DEV_MODE=1 returns 6-digit dev_code", False, f"status={r.status_code} body={r.text}")

# --- Test A2: reset with code + login with new password ---
print("\n=== STEP 2: reset to temp password, login ===")
if code_dev:
    r = reset(ADMIN_EMAIL, code_dev, TEMP_PASSWORD)
    record("A2a reset-password with dev_code succeeds", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    r2 = login(ADMIN_EMAIL, TEMP_PASSWORD)
    record("A2b login with new temp password succeeds", r2.status_code == 200, f"status={r2.status_code}")
else:
    record("A2a reset-password with dev_code succeeds", False, "no code available")
    record("A2b login with new temp password succeeds", False, "no code available")

# --- Test A3: flip DEV_MODE off, verify dev_code is null ---
print("\n=== STEP 3: DEV_MODE=0 → dev_code must be null ===")
set_dev_mode("0")
r = forgot(ADMIN_EMAIL)
if r.status_code == 200:
    data = r.json()
    dc = data.get("dev_code")
    has_key = "dev_code" in data
    record("A3 forgot-password DEV_MODE=0 returns dev_code=null for real email", has_key and dc is None, f"dev_code={dc!r} full={data}")
else:
    record("A3 forgot-password DEV_MODE=0 returns dev_code=null for real email", False, f"status={r.status_code} body={r.text}")

# Also test with a bogus email — should also be null
r = forgot("nosuchuser-xyz@clubdodo.com")
if r.status_code == 200:
    data = r.json()
    record("A3b forgot-password DEV_MODE=0 bogus email also returns dev_code=null", data.get("dev_code") is None, f"body={data}")
else:
    record("A3b forgot-password DEV_MODE=0 bogus email also returns dev_code=null", False, f"status={r.status_code}")

# --- Test A4: restore DEV_MODE=1 and restore admin password ---
print("\n=== STEP 4: restore DEV_MODE=1 and admin password ===")
set_dev_mode("1")

r = forgot(ADMIN_EMAIL)
if r.status_code == 200 and r.json().get("dev_code"):
    code2 = r.json()["dev_code"]
    record("A4a DEV_MODE=1 restored, forgot-password returns code", True, f"dev_code={code2}")
    # Reset back to original password. Temp password is currently live.
    r = reset(ADMIN_EMAIL, code2, ORIG_PASSWORD)
    record("A4b reset-password restores ORIG admin password", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
else:
    record("A4a DEV_MODE=1 restored, forgot-password returns code", False, f"status={r.status_code} body={r.text}")
    record("A4b reset-password restores ORIG admin password", False, "no code")

# --- Test B5: login with original password ---
print("\n=== STEP 5: Regression smoke ===")
r = login(ADMIN_EMAIL, ORIG_PASSWORD)
token = None
if r.status_code == 200:
    body = r.json()
    token = body.get("token")
    record("B5 login with original admin password (200)", True, "")
else:
    record("B5 login with original admin password (200)", False, f"status={r.status_code} body={r.text}")

# --- Test B6: /auth/me ---
if token:
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    ok = r.status_code == 200 and r.json().get("role") == "admin"
    record("B6 GET /auth/me returns 200 with role=admin", ok, f"status={r.status_code} body={r.text[:200]}")
else:
    record("B6 GET /auth/me returns 200 with role=admin", False, "no token")

# --- Test B7: /matches ---
if token:
    r = requests.get(f"{API}/matches", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    ok = r.status_code == 200 and isinstance(r.json(), list)
    record("B7 GET /matches returns 200 list", ok, f"status={r.status_code} count={len(r.json()) if ok else 'n/a'}")
else:
    record("B7 GET /matches returns 200 list", False, "no token")

# --- Test B8: /config (public) ---
r = requests.get(f"{API}/config", timeout=15)
ok = r.status_code == 200 and isinstance(r.json(), dict)
record("B8 GET /config returns 200 (public)", ok, f"status={r.status_code} body={r.text[:200]}")

# --- Summary ---
print("\n================ SUMMARY ================")
passed = sum(1 for _, p, _ in results if p)
total = len(results)
for name, p, detail in results:
    mark = "PASS" if p else "FAIL"
    print(f"  [{mark}] {name}")
print(f"\nTotal: {passed}/{total} passed")

sys.exit(0 if passed == total else 1)
