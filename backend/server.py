from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Union
import re

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

# ---------- Config ----------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_DAYS = 30  # mobile friendly long session

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="Club Dodo API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clubdodo")


# ---------- Helpers ----------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def compute_rating(goals: int, assists: int, matches_played: int) -> float:
    """Player rating on a 0–10 scale.

    Heuristic: `(goals*3 + assists*2 + matches*0.5) / 6`, capped at 10.0.
    A new player without any data sits at 0.0; ~6 league matches with a
    couple of goals each lifts them comfortably into the 7-8 range.
    """
    raw = (goals * 3 + assists * 2 + matches_played * 0.5) / 6
    return round(min(10.0, max(0.0, raw)), 1)


def user_public(u: dict) -> dict:
    # Primary + up to 2 positions for multi-position support (backward compat)
    positions = u.get("preferred_positions") or []
    if not positions and u.get("preferred_position"):
        positions = [u["preferred_position"]]
    primary = positions[0] if positions else u.get("preferred_position")
    return {
        "id": u["id"],
        "email": u.get("email"),
        "name": u.get("name"),
        "profile_picture": u.get("profile_picture"),
        "shirt_number": u.get("shirt_number"),
        "preferred_position": primary,
        "preferred_positions": positions,
        "role": u.get("role", "user"),
        "can_edit_matches": u.get("can_edit_matches", False),
        "goals": u.get("goals", 0),
        "assists": u.get("assists", 0),
        "matches_played": u.get("matches_played", 0),
        "wins": u.get("wins", 0),
        "draws": u.get("draws", 0),
        "losses": u.get("losses", 0),
        "league_points": u.get("league_points", 0),
        "rating": compute_rating(
            u.get("goals", 0), u.get("assists", 0), u.get("matches_played", 0)
        ),
        "created_at": u.get("created_at"),
    }


async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = auth[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    u = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not u:
        raise HTTPException(401, "User not found")
    return u


async def require_editor(request: Request) -> dict:
    u = await get_current_user(request)
    if u.get("role") != "admin" and not u.get("can_edit_matches", False):
        raise HTTPException(403, "Not authorized to edit matches")
    return u


async def require_admin(request: Request) -> dict:
    u = await get_current_user(request)
    if u.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    return u


# ---------- Models ----------
POSITION_LITERAL = Literal[
    "GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST",
    "DEF", "MID", "FWD", "ANY"
]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=40)
    shirt_number: Optional[int] = Field(default=None, ge=1, le=99)
    preferred_position: Optional[POSITION_LITERAL] = None  # legacy single
    preferred_positions: Optional[List[POSITION_LITERAL]] = Field(default=None, max_length=2)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    profile_picture: Optional[str] = None  # base64
    shirt_number: Optional[int] = Field(default=None, ge=1, le=99)
    preferred_position: Optional[POSITION_LITERAL] = None  # legacy single
    preferred_positions: Optional[List[POSITION_LITERAL]] = Field(default=None, max_length=2)


class MatchCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    date: str  # ISO datetime
    location: Optional[str] = Field(default=None, max_length=120)
    team_size: int = Field(default=5, ge=4, le=11)
    match_type: Literal["friendly", "league"] = "friendly"
    third_team_enabled: bool = False
    duration_minutes: int = Field(default=60, ge=10, le=180)


class VoteIn(BaseModel):
    vote: Literal["yes", "no", "reserve"]


class GuestRef(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    shirt_number: Optional[int] = Field(default=None, ge=1, le=99)
    preferred_position: Optional[POSITION_LITERAL] = None


class LineupOverrideIn(BaseModel):
    team_a: List[Union[str, GuestRef]] = []
    team_b: List[Union[str, GuestRef]] = []
    team_c: List[Union[str, GuestRef]] = []
    reserves: List[Union[str, GuestRef]] = []


class PlayerStatLine(BaseModel):
    user_id: str
    goals: int = 0
    assists: int = 0


class MatchResultIn(BaseModel):
    team_a_score: int = Field(ge=0)
    team_b_score: int = Field(ge=0)
    team_c_score: Optional[int] = Field(default=None, ge=0)
    stats: List[PlayerStatLine] = []


class ClubConfigUpdate(BaseModel):
    club_name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    club_logo: Optional[str] = None  # base64


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=6)


class GrantEditIn(BaseModel):
    user_id: str
    can_edit_matches: bool


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class AvailabilityIn(BaseModel):
    date: str  # YYYY-MM-DD (local club timezone)
    vote: Literal["yes", "no", "reserve"]


class MotmVoteIn(BaseModel):
    candidate_id: str  # user_id of the player being voted for


class TournamentCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    team_names: List[str] = Field(min_length=2, max_length=8)
    team_size: int = Field(default=5, ge=4, le=11)
    match_type: Literal["friendly", "league"] = "friendly"
    start_date: Optional[str] = None  # YYYY-MM-DD; first match scheduled here, others daily


# ---------- Startup ----------
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.matches.create_index("id", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_tokens.create_index("email")
    await db.match_comments.create_index([("match_id", 1), ("created_at", 1)])
    await db.availability.create_index([("date", 1)])
    await db.availability.create_index([("date", 1), ("user_id", 1)], unique=True)
    await db.tournaments.create_index("id", unique=True)
    # Seed admin
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one(
            {
                "id": str(uuid.uuid4()),
                "email": admin_email,
                "password_hash": hash_password(admin_password),
                "name": "Admin",
                "profile_picture": None,
                "shirt_number": 1,
                "role": "admin",
                "can_edit_matches": True,
                "goals": 0,
                "assists": 0,
                "matches_played": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        logger.info("Admin user seeded: %s", admin_email)
    # Seed config
    cfg = await db.config.find_one({"id": "club"})
    if not cfg:
        await db.config.insert_one(
            {"id": "club", "club_name": "Club Dodo", "club_logo": None}
        )


@app.on_event("shutdown")
async def shutdown():
    client.close()


# ---------- Auth ----------
@api.post("/auth/register")
async def register(data: RegisterIn):
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    uid = str(uuid.uuid4())
    # Normalize positions (multi takes precedence, fallback to singular)
    positions = list(data.preferred_positions or [])
    if not positions and data.preferred_position:
        positions = [data.preferred_position]
    primary = positions[0] if positions else None
    doc = {
        "id": uid,
        "email": email,
        "password_hash": hash_password(data.password),
        "name": data.name,
        "profile_picture": None,
        "shirt_number": data.shirt_number,
        "preferred_position": primary,
        "preferred_positions": positions,
        "role": "user",
        "can_edit_matches": False,
        "goals": 0,
        "assists": 0,
        "matches_played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "league_points": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    token = create_token(uid, email)
    return {"token": token, "user": user_public(doc)}


@api.post("/auth/login")
async def login(data: LoginIn):
    email = data.email.lower()
    u = await db.users.find_one({"email": email}, {"_id": 0})
    if not u or not verify_password(data.password, u["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(u["id"], email)
    return {"token": token, "user": user_public(u)}


@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user_public(user)


@api.post("/auth/forgot-password")
async def forgot_password(data: ForgotPasswordIn):
    """Generate a 6-digit reset code, store a salted hash, and only return the
    plaintext code when the server is in DEV_MODE **and not deployed to the
    emergent.host production domain**. The URL check is a defence-in-depth
    guard so that if `DEV_MODE=1` accidentally leaks into prod env vars, the
    code is still never returned to anonymous callers. In production, the
    code must be delivered via email/SMS (TODO)."""
    import secrets
    import os
    dev_mode_flag = os.getenv("DEV_MODE", "0").lower() in ("1", "true", "yes")
    app_url = (os.getenv("APP_URL") or "").lower()
    is_prod_host = any(
        marker in app_url
        for marker in ("emergent.host", "emergentagent.com/deploy", ".clubdodo.")
    )
    dev_mode = dev_mode_flag and not is_prod_host
    email = data.email.lower()
    u = await db.users.find_one({"email": email}, {"_id": 0})
    # Clean up expired tokens for this email to avoid collisions
    await db.password_reset_tokens.delete_many({"email": email})
    generic_msg = "If that email is registered, a code has been generated."
    if not u:
        return {"ok": True, "dev_code": None, "message": generic_msg}
    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.password_reset_tokens.insert_one(
        {
            "email": email,
            "code_hash": hash_password(code),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "used": False,
        }
    )
    if dev_mode:
        logger.info("Password reset code for %s: %s (DEV_MODE)", email, code)
        return {
            "ok": True,
            "dev_code": code,  # only returned in DEV_MODE
            "message": "Code generated. It expires in 60 minutes.",
        }
    # Production: never leak the code in the response
    # TODO: dispatch the code via email/SMS here.
    return {"ok": True, "dev_code": None, "message": generic_msg}


@api.post("/auth/reset-password")
async def reset_password(data: ResetPasswordIn):
    email = data.email.lower()
    token = await db.password_reset_tokens.find_one(
        {"email": email, "used": False}, sort=[("expires_at", -1)]
    )
    if not token:
        raise HTTPException(400, "No reset code has been requested for this email")
    expires_at = token["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "Code has expired, request a new one")
    if not verify_password(data.code, token["code_hash"]):
        raise HTTPException(400, "Invalid code")
    u = await db.users.find_one({"email": email}, {"_id": 0})
    if not u:
        raise HTTPException(400, "Account not found")
    await db.users.update_one(
        {"id": u["id"]},
        {"$set": {"password_hash": hash_password(data.new_password)}},
    )
    await db.password_reset_tokens.update_one(
        {"_id": token["_id"]}, {"$set": {"used": True}}
    )
    return {"ok": True, "message": "Password has been reset. You can log in now."}


# ---------- Users ----------
@api.get("/users")
async def list_users(user=Depends(get_current_user)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(5000)
    pubs = [user_public(u) for u in users]
    pubs.sort(key=lambda x: x["rating"], reverse=True)
    return pubs


@api.put("/users/me")
async def update_profile(data: ProfileUpdate, user=Depends(get_current_user)):
    raw = data.dict(exclude_unset=True)
    updates = {k: v for k, v in raw.items() if v is not None}

    # Keep primary (`preferred_position`) and list (`preferred_positions`) in sync.
    if "preferred_positions" in updates:
        positions = updates["preferred_positions"] or []
        updates["preferred_positions"] = positions[:2]  # safety cap
        updates["preferred_position"] = positions[0] if positions else None
    elif "preferred_position" in updates:
        # Legacy single-value update — rebuild list so both stay consistent.
        updates["preferred_positions"] = [updates["preferred_position"]] if updates["preferred_position"] else []

    if updates:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return user_public(u)


@api.post("/users/grant-edit")
async def grant_edit(data: GrantEditIn, admin=Depends(require_admin)):
    res = await db.users.update_one(
        {"id": data.user_id}, {"$set": {"can_edit_matches": data.can_edit_matches}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "User not found")
    u = await db.users.find_one({"id": data.user_id}, {"_id": 0})
    return user_public(u)


@api.delete("/users/{user_id}")
async def delete_user(user_id: str, admin=Depends(require_admin)):
    """Admin-only: remove a player from the squad. Cleans up their votes,
    lineup slots, and chat messages to avoid orphaned references. Protects
    the last admin and the acting admin from self-deletion."""
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found")
    if target["id"] == admin["id"]:
        raise HTTPException(400, "You cannot delete your own account")
    if target.get("role") == "admin":
        admin_count = await db.users.count_documents({"role": "admin"})
        if admin_count <= 1:
            raise HTTPException(400, "Cannot delete the last remaining admin")

    # Clean up references in matches (votes map + lineup arrays)
    async for m in db.matches.find({}, {"_id": 0}):
        changed = False
        votes = m.get("votes", {}) or {}
        if user_id in votes:
            votes.pop(user_id, None)
            changed = True
        lineup = m.get("lineup")
        if isinstance(lineup, dict):
            for k in ("team_a", "team_b", "team_c", "reserves"):
                arr = lineup.get(k) or []
                new_arr = [p for p in arr if (p or {}).get("user_id") != user_id]
                if len(new_arr) != len(arr):
                    lineup[k] = new_arr
                    changed = True
        if changed:
            await db.matches.update_one(
                {"id": m["id"]},
                {"$set": {"votes": votes, "lineup": lineup}},
            )

    # Wipe their chat messages
    await db.match_comments.delete_many({"user_id": user_id})

    await db.users.delete_one({"id": user_id})
    return {"ok": True, "deleted_user_id": user_id}


# ---------- Club Config ----------
@api.get("/config")
async def get_config():
    cfg = await db.config.find_one({"id": "club"}, {"_id": 0})
    return cfg or {"id": "club", "club_name": "Club Dodo", "club_logo": None}


@api.put("/config")
async def update_config(data: ClubConfigUpdate, admin=Depends(require_admin)):
    updates = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
    if updates:
        await db.config.update_one({"id": "club"}, {"$set": updates}, upsert=True)
    cfg = await db.config.find_one({"id": "club"}, {"_id": 0})
    return cfg


# ---------- Matches ----------
def _match_public(m: dict, users_by_id: dict) -> dict:
    votes = m.get("votes", {})
    vote_list = []
    for uid, v in votes.items():
        u = users_by_id.get(uid)
        if u:
            vote_list.append(
                {
                    "user_id": uid,
                    "name": u.get("name"),
                    "shirt_number": u.get("shirt_number"),
                    "profile_picture": u.get("profile_picture"),
                    "preferred_position": u.get("preferred_position"),
                    "preferred_positions": u.get("preferred_positions") or (
                        [u.get("preferred_position")] if u.get("preferred_position") else []
                    ),
                    "rating": compute_rating(
                        u.get("goals", 0),
                        u.get("assists", 0),
                        u.get("matches_played", 0),
                    ),
                    "vote": v,
                }
            )
    return {
        "id": m["id"],
        "title": m["title"],
        "date": m["date"],
        "location": m.get("location"),
        "team_size": m.get("team_size", 5),
        "match_type": m.get("match_type", "friendly"),
        "third_team_enabled": m.get("third_team_enabled", False),
        "duration_minutes": m.get("duration_minutes", 60),
        "timer_started_at": m.get("timer_started_at"),
        "timer_ended_at": m.get("timer_ended_at"),
        "status": m.get("status", "voting"),
        "created_by": m.get("created_by"),
        "created_at": m.get("created_at"),
        "votes": vote_list,
        "lineup": m.get("lineup"),
        "result": m.get("result"),
        "auto_from_availability_date": m.get("auto_from_availability_date"),
        "motm": _motm_summary(m),
    }


async def _users_map():
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(5000)
    return {u["id"]: u for u in users}


@api.post("/matches")
async def create_match(data: MatchCreate, user=Depends(get_current_user)):
    mid = str(uuid.uuid4())
    doc = {
        "id": mid,
        "title": data.title,
        "date": data.date,
        "location": data.location,
        "team_size": data.team_size,
        "match_type": data.match_type,
        "third_team_enabled": data.third_team_enabled,
        "duration_minutes": data.duration_minutes,
        "status": "voting",
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "votes": {},
        "lineup": None,
        "result": None,
        "timer_started_at": None,
        "timer_ended_at": None,
    }
    await db.matches.insert_one(doc)
    umap = await _users_map()
    return _match_public(doc, umap)


@api.get("/matches")
async def list_matches(user=Depends(get_current_user)):
    matches = await db.matches.find({}, {"_id": 0}).sort("date", -1).to_list(500)
    umap = await _users_map()
    return [_match_public(m, umap) for m in matches]


@api.get("/matches/{mid}")
async def get_match(mid: str, user=Depends(get_current_user)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    umap = await _users_map()
    return _match_public(m, umap)


@api.post("/matches/{mid}/vote")
async def vote_match(mid: str, data: VoteIn, user=Depends(get_current_user)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    await db.matches.update_one(
        {"id": mid}, {"$set": {f"votes.{user['id']}": data.vote}}
    )
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    umap = await _users_map()
    return _match_public(m, umap)


@api.delete("/matches/{mid}/vote")
async def clear_match_vote(mid: str, user=Depends(get_current_user)):
    """Toggle off — clear the caller's vote for this match."""
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    await db.matches.update_one(
        {"id": mid}, {"$unset": {f"votes.{user['id']}": ""}}
    )
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    umap = await _users_map()
    return _match_public(m, umap)


def _build_lineup(
    vote_list: list,
    team_size: int,
    third_team_enabled: bool = False,
    match_type: str = "friendly",
) -> dict:
    """Balanced snake draft by position + rating.

    - Yes voters are grouped by preferred_position (GK/DEF/MID/FWD/ANY).
    - Each bucket is sorted by rating desc; players are then assigned to the
      team with the fewest players, tie-broken by lowest total team rating.
      This naturally distributes both positions and skill.
    - A 3rd team auto-activates when yes voters >= team_size * 3 (unless this
      is a league match — league stays 2-team to keep points meaningful).
    - Any yes voter past the total capacity goes to reserves along with the
      users who explicitly voted 'reserve'.
    """
    yes_voters = [v for v in vote_list if v["vote"] == "yes"]
    reserve_voters = [v for v in vote_list if v["vote"] == "reserve"]

    auto_third = (
        len(yes_voters) >= team_size * 3 and match_type != "league"
    )
    num_teams = 3 if (third_team_enabled or auto_third) else 2

    position_order = ["GK", "DEF", "MID", "FWD", "ANY"]

    # Map specific positions (CB/CDM/ST/etc) to base buckets used for balancing
    position_bucket_map = {
        "GK": "GK",
        "CB": "DEF", "LB": "DEF", "RB": "DEF", "DEF": "DEF",
        "CDM": "MID", "CM": "MID", "CAM": "MID", "MID": "MID",
        "LW": "FWD", "RW": "FWD", "ST": "FWD", "FWD": "FWD",
        "ANY": "ANY",
    }

    def get_pos(p: dict) -> str:
        v = p.get("preferred_position")
        return position_bucket_map.get(v, "ANY")

    buckets: dict = {p: [] for p in position_order}
    for p in yes_voters:
        buckets[get_pos(p)].append(p)
    for pos in position_order:
        buckets[pos].sort(key=lambda x: x.get("rating", 0), reverse=True)

    teams: List[List[dict]] = [[] for _ in range(num_teams)]
    overflow: List[dict] = []

    for pos in position_order:
        for p in buckets[pos]:
            available = [i for i in range(num_teams) if len(teams[i]) < team_size]
            if not available:
                overflow.append(p)
                continue
            # Prefer team with fewest players; tie-break by lowest cumulative rating
            available.sort(
                key=lambda i: (
                    len(teams[i]),
                    sum(x.get("rating", 0) for x in teams[i]),
                )
            )
            teams[available[0]].append(p)

    # Cosmetic sort inside each team: GK → DEF → MID → FWD → ANY, then rating desc
    pos_rank = {p: i for i, p in enumerate(position_order)}
    for t in teams:
        t.sort(key=lambda p: (pos_rank.get(get_pos(p), 99), -p.get("rating", 0)))

    return {
        "team_a": teams[0],
        "team_b": teams[1],
        "team_c": teams[2] if num_teams == 3 else [],
        "reserves": overflow + reserve_voters,
        "team_size": team_size,
        "third_team_enabled": num_teams == 3,
    }


@api.post("/matches/{mid}/generate-lineup")
async def generate_lineup(mid: str, user=Depends(require_editor)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    umap = await _users_map()
    full = _match_public(m, umap)
    lineup = _build_lineup(
        full["votes"],
        m.get("team_size", 5),
        m.get("third_team_enabled", False),
        m.get("match_type", "friendly"),
    )
    update = {"lineup": lineup, "status": "scheduled"}
    # Persist auto-bump so the UI (and result modal) reflect 3-team mode
    if lineup["third_team_enabled"] and not m.get("third_team_enabled"):
        update["third_team_enabled"] = True
    await db.matches.update_one({"id": mid}, {"$set": update})
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    return _match_public(m, umap)


def _player_mini(u: dict) -> dict:
    return {
        "user_id": u["id"],
        "name": u.get("name"),
        "shirt_number": u.get("shirt_number"),
        "profile_picture": u.get("profile_picture"),
        "preferred_position": u.get("preferred_position"),
        "preferred_positions": u.get("preferred_positions") or (
            [u.get("preferred_position")] if u.get("preferred_position") else []
        ),
        "rating": compute_rating(
            u.get("goals", 0),
            u.get("assists", 0),
            u.get("matches_played", 0),
        ),
        "vote": "yes",
    }


@api.put("/matches/{mid}/lineup")
async def override_lineup(
    mid: str, data: LineupOverrideIn, user=Depends(require_editor)
):
    """Manual override of a match lineup. Entries can be either a user_id
    string (registered Club Dodo user) or a guest object {name, shirt_number}.
    Guests get synthetic ids prefixed with 'guest:' so stat updates can skip them."""
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    umap = await _users_map()
    votes = m.get("votes", {})

    def hydrate(entries: List[Union[str, GuestRef]]) -> List[dict]:
        out = []
        for entry in entries:
            if isinstance(entry, str):
                u = umap.get(entry)
                if not u:
                    continue
                mini = _player_mini(u)
                mini["vote"] = votes.get(u["id"], "yes")
                out.append(mini)
            else:
                # Guest player
                out.append(
                    {
                        "user_id": f"guest:{uuid.uuid4()}",
                        "name": entry.name,
                        "shirt_number": entry.shirt_number,
                        "profile_picture": None,
                        "preferred_position": entry.preferred_position,
                        "preferred_positions": [entry.preferred_position] if entry.preferred_position else [],
                        "rating": 0,
                        "vote": "guest",
                        "is_guest": True,
                    }
                )
        return out

    team_a = hydrate(data.team_a)
    team_b = hydrate(data.team_b)
    team_c = hydrate(data.team_c)
    reserves = hydrate(data.reserves)

    # Validate no duplicate user_ids (only meaningful for registered users)
    seen = set()
    for roster in (team_a, team_b, team_c, reserves):
        for p in roster:
            if p["user_id"].startswith("guest:"):
                continue
            if p["user_id"] in seen:
                raise HTTPException(400, f"Player {p['name']} appears in multiple teams")
            seen.add(p["user_id"])

    ts = m.get("team_size", 5)
    for label, roster in (("Team Red", team_a), ("Team Black", team_b), ("Team White", team_c)):
        if len(roster) > ts:
            raise HTTPException(400, f"{label} exceeds team size ({len(roster)} > {ts})")

    lineup = {
        "team_a": team_a,
        "team_b": team_b,
        "team_c": team_c,
        "reserves": reserves,
        "team_size": ts,
        "third_team_enabled": len(team_c) > 0,
    }
    update = {"lineup": lineup}
    if m.get("status") == "voting":
        update["status"] = "scheduled"
    if len(team_c) > 0 and not m.get("third_team_enabled"):
        update["third_team_enabled"] = True
    await db.matches.update_one({"id": mid}, {"$set": update})
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    return _match_public(m, umap)


@api.post("/matches/{mid}/timer/start")
async def start_timer(mid: str, user=Depends(require_editor)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    now = datetime.now(timezone.utc).isoformat()
    await db.matches.update_one(
        {"id": mid},
        {"$set": {"timer_started_at": now, "timer_ended_at": None}},
    )
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    umap = await _users_map()
    return _match_public(m, umap)


@api.post("/matches/{mid}/timer/stop")
async def stop_timer(mid: str, user=Depends(require_editor)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    now = datetime.now(timezone.utc).isoformat()
    await db.matches.update_one(
        {"id": mid}, {"$set": {"timer_ended_at": now}}
    )
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    umap = await _users_map()
    return _match_public(m, umap)


@api.post("/matches/{mid}/timer/reset")
async def reset_timer(mid: str, user=Depends(require_editor)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    await db.matches.update_one(
        {"id": mid},
        {"$set": {"timer_started_at": None, "timer_ended_at": None}},
    )
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    umap = await _users_map()
    return _match_public(m, umap)


def _league_points_per_team(a: int, b: int) -> tuple:
    """Return (team_a_points, team_b_points)."""
    if a > b:
        return 3, 0
    if b > a:
        return 0, 3
    return 1, 1


def _league_outcome(team_score: int, opponent_score: int) -> str:
    if team_score > opponent_score:
        return "win"
    if team_score < opponent_score:
        return "loss"
    return "draw"


async def _apply_league_delta(user_ids: List[str], outcome: str, sign: int):
    """sign=+1 to apply, -1 to revert. Skips guest IDs."""
    if not user_ids:
        return
    points_map = {"win": 3, "draw": 1, "loss": 0}
    field_map = {"win": "wins", "draw": "draws", "loss": "losses"}
    inc = {
        field_map[outcome]: 1 * sign,
        "league_points": points_map[outcome] * sign,
    }
    for uid in user_ids:
        if uid.startswith("guest:"):
            continue
        await db.users.update_one({"id": uid}, {"$inc": inc})


@api.post("/matches/{mid}/result")
async def record_result(mid: str, data: MatchResultIn, user=Depends(require_editor)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")

    # If lineup not yet generated, auto-generate using current votes
    if not m.get("lineup"):
        umap = await _users_map()
        full = _match_public(m, umap)
        lineup = _build_lineup(
            full["votes"],
            m.get("team_size", 5),
            m.get("third_team_enabled", False),
            m.get("match_type", "friendly"),
        )
        set_on_auto = {"lineup": lineup}
        if lineup["third_team_enabled"] and not m.get("third_team_enabled"):
            set_on_auto["third_team_enabled"] = True
            m["third_team_enabled"] = True
        await db.matches.update_one({"id": mid}, {"$set": set_on_auto})
        m["lineup"] = lineup

    # If a prior result exists, revert previous contributions first
    prev = m.get("result")
    if prev:
        for s in prev.get("stats", []):
            await db.users.update_one(
                {"id": s["user_id"]},
                {
                    "$inc": {
                        "goals": -int(s.get("goals", 0)),
                        "assists": -int(s.get("assists", 0)),
                    }
                },
            )
        for uid in prev.get("participants", []):
            await db.users.update_one(
                {"id": uid}, {"$inc": {"matches_played": -1}}
            )
        # revert league contributions if any
        if prev.get("match_type") == "league":
            for team_key, outcome in (prev.get("team_outcomes") or {}).items():
                uids = prev.get("team_rosters", {}).get(team_key, [])
                await _apply_league_delta(uids, outcome, sign=-1)

    # Compute team rosters from lineup
    lineup = m["lineup"]
    team_a_uids = [p["user_id"] for p in lineup.get("team_a", [])]
    team_b_uids = [p["user_id"] for p in lineup.get("team_b", [])]
    team_c_uids = [p["user_id"] for p in lineup.get("team_c", []) or []]
    participants = team_a_uids + team_b_uids + team_c_uids

    # Apply matches_played (skip guests)
    for uid in participants:
        if uid.startswith("guest:"):
            continue
        await db.users.update_one({"id": uid}, {"$inc": {"matches_played": 1}})
    # Apply per-player goal/assist stats (skip guests)
    for s in data.stats:
        if s.user_id.startswith("guest:"):
            continue
        await db.users.update_one(
            {"id": s.user_id},
            {"$inc": {"goals": int(s.goals), "assists": int(s.assists)}},
        )

    # League points (only for 2-team league matches)
    team_outcomes = {}
    team_rosters = {
        "team_a": team_a_uids,
        "team_b": team_b_uids,
        "team_c": team_c_uids,
    }
    is_league = m.get("match_type") == "league" and not m.get("third_team_enabled", False)
    if is_league:
        out_a = _league_outcome(data.team_a_score, data.team_b_score)
        out_b = _league_outcome(data.team_b_score, data.team_a_score)
        team_outcomes = {"team_a": out_a, "team_b": out_b}
        await _apply_league_delta(team_a_uids, out_a, sign=+1)
        await _apply_league_delta(team_b_uids, out_b, sign=+1)

    result = {
        "team_a_score": data.team_a_score,
        "team_b_score": data.team_b_score,
        "team_c_score": data.team_c_score,
        "stats": [s.dict() for s in data.stats],
        "participants": participants,
        "team_rosters": team_rosters,
        "team_outcomes": team_outcomes,
        "match_type": m.get("match_type", "friendly"),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "recorded_by": user["id"],
    }
    await db.matches.update_one(
        {"id": mid}, {"$set": {"result": result, "status": "played"}}
    )
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    umap = await _users_map()
    return _match_public(m, umap)


@api.delete("/matches/{mid}")
async def delete_match(mid: str, user=Depends(require_editor)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    # revert any stats contributions if already recorded
    prev = m.get("result")
    if prev:
        for s in prev.get("stats", []):
            await db.users.update_one(
                {"id": s["user_id"]},
                {
                    "$inc": {
                        "goals": -int(s.get("goals", 0)),
                        "assists": -int(s.get("assists", 0)),
                    }
                },
            )
        for uid in prev.get("participants", []):
            await db.users.update_one(
                {"id": uid}, {"$inc": {"matches_played": -1}}
            )
        if prev.get("match_type") == "league":
            for team_key, outcome in (prev.get("team_outcomes") or {}).items():
                uids = prev.get("team_rosters", {}).get(team_key, [])
                await _apply_league_delta(uids, outcome, sign=-1)
    await db.matches.delete_one({"id": mid})
    await db.match_comments.delete_many({"match_id": mid})
    return {"ok": True}


# ---------- Match Comments (chat) ----------
def _comment_public(c: dict) -> dict:
    return {
        "id": c["id"],
        "match_id": c["match_id"],
        "user_id": c["user_id"],
        "name": c.get("name"),
        "profile_picture": c.get("profile_picture"),
        "text": c.get("text", ""),
        "created_at": c.get("created_at"),
    }


@api.get("/matches/{mid}/comments")
async def list_comments(mid: str, user=Depends(get_current_user)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    cur = db.match_comments.find({"match_id": mid}, {"_id": 0}).sort("created_at", 1)
    items = [c async for c in cur]
    return [_comment_public(c) for c in items]


@api.post("/matches/{mid}/comments")
async def add_comment(mid: str, data: CommentIn, user=Depends(get_current_user)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    doc = {
        "id": str(uuid.uuid4()),
        "match_id": mid,
        "user_id": user["id"],
        "name": user.get("name"),
        "profile_picture": user.get("profile_picture"),
        "text": data.text.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.match_comments.insert_one(doc)
    return _comment_public(doc)


@api.delete("/matches/{mid}/comments/{cid}")
async def delete_comment(mid: str, cid: str, user=Depends(get_current_user)):
    c = await db.match_comments.find_one({"id": cid, "match_id": mid}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Comment not found")
    # Author, admin, or editor may delete
    if c["user_id"] != user["id"] and user.get("role") != "admin" and not user.get("can_edit_matches", False):
        raise HTTPException(403, "Not allowed to delete this comment")
    await db.match_comments.delete_one({"id": cid})
    return {"ok": True}


# ---------- Man of the Match voting ----------
def _motm_summary(m: dict) -> dict:
    """Tally MOTM votes stored in match.motm_votes: { voter_id -> candidate_id }."""
    votes: dict = m.get("motm_votes") or {}
    counts: dict = {}
    for cand in votes.values():
        counts[cand] = counts.get(cand, 0) + 1
    winner_id = None
    if counts:
        winner_id = max(counts.items(), key=lambda kv: kv[1])[0]
    return {
        "votes": dict(counts),  # { user_id: count }
        "winner_id": winner_id,
        "total": len(votes),
    }


def _candidates_for_match(m: dict) -> List[str]:
    """Players who actually played (team_a/b/c) — only registered users
    (guests excluded since they have no persistent identity)."""
    out: List[str] = []
    lineup = m.get("lineup") or {}
    for k in ("team_a", "team_b", "team_c"):
        for p in lineup.get(k) or []:
            uid = (p or {}).get("user_id") or ""
            if uid and not uid.startswith("guest:"):
                out.append(uid)
    return out


@api.get("/matches/{mid}/motm")
async def get_motm(mid: str, user=Depends(get_current_user)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    summary = _motm_summary(m)
    candidates = _candidates_for_match(m)
    my_choice = (m.get("motm_votes") or {}).get(user["id"])
    open_for_voting = m.get("status") == "completed" and len(candidates) > 0
    # Voter eligibility: any registered user who voted YES on the match
    eligible_voters = [
        uid for uid, v in (m.get("votes") or {}).items() if v == "yes"
    ]
    can_vote = open_for_voting and (user["id"] in eligible_voters or user.get("role") == "admin")
    return {
        "open": open_for_voting,
        "can_vote": can_vote,
        "candidates": candidates,
        "my_choice": my_choice,
        **summary,
    }


@api.post("/matches/{mid}/motm/vote")
async def cast_motm_vote(mid: str, data: MotmVoteIn, user=Depends(get_current_user)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    if m.get("status") != "completed":
        raise HTTPException(400, "MOTM voting opens once the match is completed")
    candidates = set(_candidates_for_match(m))
    if data.candidate_id not in candidates:
        raise HTTPException(400, "Candidate did not play in this match")
    if data.candidate_id == user["id"]:
        raise HTTPException(400, "You cannot vote for yourself")
    eligible = {uid for uid, v in (m.get("votes") or {}).items() if v == "yes"}
    if user["id"] not in eligible and user.get("role") != "admin":
        raise HTTPException(403, "Only players who voted YES can vote for MOTM")
    motm_votes = dict(m.get("motm_votes") or {})
    motm_votes[user["id"]] = data.candidate_id
    await db.matches.update_one({"id": mid}, {"$set": {"motm_votes": motm_votes}})
    refreshed = await db.matches.find_one({"id": mid}, {"_id": 0})
    summary = _motm_summary(refreshed)
    return {
        "ok": True,
        "my_choice": data.candidate_id,
        **summary,
    }


@api.delete("/matches/{mid}/motm/vote")
async def clear_motm_vote(mid: str, user=Depends(get_current_user)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    motm_votes = dict(m.get("motm_votes") or {})
    motm_votes.pop(user["id"], None)
    await db.matches.update_one({"id": mid}, {"$set": {"motm_votes": motm_votes}})
    return {"ok": True}


# ---------- Tournaments (Round-robin) ----------
def _round_robin_pairings(team_names: List[str]) -> List[tuple]:
    """Berger algorithm. Returns list of (home, away) pairs covering each
    pair once. Adds a BYE for odd team counts and skips those rounds."""
    teams = list(team_names)
    if len(teams) % 2 != 0:
        teams.append("__BYE__")
    n = len(teams)
    pairings: List[tuple] = []
    fixed = teams[0]
    rotating = teams[1:]
    for _ in range(n - 1):
        round_pairs = [(fixed, rotating[-1])] + [
            (rotating[i], rotating[-2 - i]) for i in range(n // 2 - 1)
        ]
        for h, a in round_pairs:
            if h != "__BYE__" and a != "__BYE__":
                pairings.append((h, a))
        rotating = [rotating[-1]] + rotating[:-1]
    return pairings


def _tournament_public(t: dict, matches: List[dict]) -> dict:
    """Compute standings on the fly from completed match results."""
    team_names: List[str] = t.get("team_names") or []
    standings = {
        n: {"team": n, "P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0, "Pts": 0}
        for n in team_names
    }
    by_id = {m["id"]: m for m in matches}
    fixtures_out = []
    for fx in t.get("fixtures") or []:
        m = by_id.get(fx.get("match_id"))
        result = (m or {}).get("result")
        home = fx.get("home")
        away = fx.get("away")
        played = bool(result)
        s_home = s_away = None
        if result and home in standings and away in standings:
            s_home = int(result.get("team_a_score") or 0)
            s_away = int(result.get("team_b_score") or 0)
            standings[home]["P"] += 1
            standings[away]["P"] += 1
            standings[home]["GF"] += s_home
            standings[home]["GA"] += s_away
            standings[away]["GF"] += s_away
            standings[away]["GA"] += s_home
            if s_home > s_away:
                standings[home]["W"] += 1
                standings[home]["Pts"] += 3
                standings[away]["L"] += 1
            elif s_home < s_away:
                standings[away]["W"] += 1
                standings[away]["Pts"] += 3
                standings[home]["L"] += 1
            else:
                standings[home]["D"] += 1
                standings[away]["D"] += 1
                standings[home]["Pts"] += 1
                standings[away]["Pts"] += 1
        # Per-fixture top scorers/assists derived from match.result.stats
        scorers = []
        assisters = []
        if result and isinstance(result.get("stats"), list):
            for s in result["stats"]:
                if (s.get("goals") or 0) > 0:
                    scorers.append({"user_id": s.get("user_id"), "goals": s.get("goals")})
                if (s.get("assists") or 0) > 0:
                    assisters.append({"user_id": s.get("user_id"), "assists": s.get("assists")})
            scorers.sort(key=lambda r: -r["goals"])
            assisters.sort(key=lambda r: -r["assists"])
        fixtures_out.append({
            "match_id": fx.get("match_id"),
            "home": home,
            "away": away,
            "round": fx.get("round"),
            "scheduled_at": (m or {}).get("date") if m else None,
            "played": played,
            "score_home": s_home,
            "score_away": s_away,
            "scorers": scorers,
            "assisters": assisters,
        })
    for s in standings.values():
        s["GD"] = s["GF"] - s["GA"]
    table = sorted(standings.values(), key=lambda r: (-r["Pts"], -r["GD"], -r["GF"], r["team"]))
    return {
        "id": t["id"],
        "name": t["name"],
        "team_names": team_names,
        "team_size": t.get("team_size"),
        "match_type": t.get("match_type"),
        "created_at": t.get("created_at"),
        "fixtures": fixtures_out,
        "standings": table,
        "winner": (table[0]["team"]
                   if table and all(f["played"] for f in fixtures_out) and len(fixtures_out) > 0
                   else None),
        "completed": all(f["played"] for f in fixtures_out) and len(fixtures_out) > 0,
    }


@api.post("/tournaments")
async def create_tournament(data: TournamentCreateIn, admin=Depends(require_admin)):
    names = [n.strip() for n in data.team_names if n.strip()]
    if len(set(names)) != len(names):
        raise HTTPException(400, "Team names must be unique")
    if len(names) < 2:
        raise HTTPException(400, "Need at least 2 teams")
    pairings = _round_robin_pairings(names)
    # Schedule one fixture per day starting from start_date (or tomorrow).
    if data.start_date and DAY_RE.match(data.start_date):
        try:
            base = datetime.fromisoformat(data.start_date + "T19:00:00+00:00")
        except Exception:
            base = datetime.now(timezone.utc) + timedelta(days=1)
    else:
        base = datetime.now(timezone.utc).replace(hour=19, minute=0, second=0, microsecond=0) + timedelta(days=1)

    tid = str(uuid.uuid4())
    fixtures = []
    for i, (home, away) in enumerate(pairings):
        match_id = str(uuid.uuid4())
        date_iso = (base + timedelta(days=i)).isoformat()
        await db.matches.insert_one({
            "id": match_id,
            "title": f"{data.name}: {home} vs {away}",
            "date": date_iso,
            "team_size": data.team_size,
            "match_type": data.match_type,
            "third_team_enabled": False,
            "votes": {},
            "lineup": None,
            "score_a": 0, "score_b": 0, "score_c": 0,
            "status": "scheduled",
            "result": None,
            "timer_running": False,
            "timer_started_at": None,
            "timer_total_seconds": 0,
            "tournament_id": tid,
            "tournament_home": home,
            "tournament_away": away,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": admin["id"],
        })
        fixtures.append({"match_id": match_id, "home": home, "away": away, "round": i + 1})

    doc = {
        "id": tid,
        "name": data.name,
        "team_names": names,
        "team_size": data.team_size,
        "match_type": data.match_type,
        "fixtures": fixtures,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": admin["id"],
    }
    await db.tournaments.insert_one(doc)
    matches = await db.matches.find({"tournament_id": tid}, {"_id": 0}).to_list(length=None)
    return _tournament_public(doc, matches)


@api.get("/tournaments")
async def list_tournaments(user=Depends(get_current_user)):
    cur = db.tournaments.find({}, {"_id": 0}).sort("created_at", -1)
    items = []
    async for t in cur:
        matches = await db.matches.find({"tournament_id": t["id"]}, {"_id": 0}).to_list(length=None)
        items.append(_tournament_public(t, matches))
    return items


@api.get("/tournaments/{tid}")
async def get_tournament(tid: str, user=Depends(get_current_user)):
    t = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    matches = await db.matches.find({"tournament_id": tid}, {"_id": 0}).to_list(length=None)
    return _tournament_public(t, matches)


@api.delete("/tournaments/{tid}")
async def delete_tournament(tid: str, admin=Depends(require_admin)):
    t = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    # Cascade delete linked matches and their comments
    match_ids = [fx["match_id"] for fx in (t.get("fixtures") or [])]
    if match_ids:
        await db.matches.delete_many({"id": {"$in": match_ids}})
        await db.match_comments.delete_many({"match_id": {"$in": match_ids}})
    await db.tournaments.delete_one({"id": tid})
    return {"ok": True}


# ---------- Availability (Week ahead poll) ----------
AUTO_MATCH_THRESHOLD = 8
AUTO_MATCH_KICKOFF_HOUR = 19
AUTO_MATCH_TEAM_SIZE = 4
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _next_seven_days() -> List[str]:
    today = datetime.now(timezone.utc).date()
    return [(today + timedelta(days=i)).isoformat() for i in range(7)]


async def _maybe_auto_create_match(date_str: str) -> Optional[dict]:
    """If a date has >= AUTO_MATCH_THRESHOLD 'yes' availability votes and no
    match yet auto-created for that date, build one and import yeses as votes."""
    existing = await db.matches.find_one(
        {"auto_from_availability_date": date_str}, {"_id": 0}
    )
    if existing:
        return existing
    cur = db.availability.find({"date": date_str, "vote": "yes"})
    yes_user_ids = [d["user_id"] async for d in cur]
    if len(yes_user_ids) < AUTO_MATCH_THRESHOLD:
        return None
    try:
        y, m, d = [int(p) for p in date_str.split("-")]
        kickoff = datetime(y, m, d, AUTO_MATCH_KICKOFF_HOUR, 0, tzinfo=timezone.utc)
    except Exception:
        return None
    new_match = {
        "id": str(uuid.uuid4()),
        "title": f"Auto match {date_str}",
        "date": kickoff.isoformat(),
        "team_size": AUTO_MATCH_TEAM_SIZE,
        "match_type": "friendly",
        "third_team_enabled": False,
        "votes": {uid: "yes" for uid in yes_user_ids},
        "lineup": None,
        "score_a": 0, "score_b": 0, "score_c": 0,
        "status": "voting",
        "result": None,
        "timer_running": False,
        "timer_started_at": None,
        "timer_total_seconds": 0,
        "auto_from_availability_date": date_str,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "system",
    }
    await db.matches.insert_one(new_match)
    return new_match


def _avail_doc_to_dict(d: dict) -> dict:
    return {
        "user_id": d["user_id"],
        "date": d["date"],
        "vote": d.get("vote"),
        "name": d.get("name"),
        "profile_picture": d.get("profile_picture"),
        "shirt_number": d.get("shirt_number"),
    }


@api.get("/availability")
async def list_availability(user=Depends(get_current_user)):
    """Return the next 7 days with per-day aggregated tallies, the caller's own
    vote per day, the full voter lists per day, and any auto-created match id."""
    days = _next_seven_days()
    out = []
    cur = db.availability.find({"date": {"$in": days}}, {"_id": 0})
    by_date: dict = {d: [] for d in days}
    async for doc in cur:
        by_date.setdefault(doc["date"], []).append(doc)
    auto_matches = {
        m["auto_from_availability_date"]: m["id"]
        async for m in db.matches.find(
            {"auto_from_availability_date": {"$in": days}}, {"_id": 0, "id": 1, "auto_from_availability_date": 1}
        )
    }
    for d in days:
        entries = by_date.get(d, [])
        yes = [e for e in entries if e.get("vote") == "yes"]
        no = [e for e in entries if e.get("vote") == "no"]
        reserve = [e for e in entries if e.get("vote") == "reserve"]
        my_vote = next((e.get("vote") for e in entries if e["user_id"] == user["id"]), None)
        out.append({
            "date": d,
            "yes_count": len(yes),
            "no_count": len(no),
            "reserve_count": len(reserve),
            "my_vote": my_vote,
            "yes": [_avail_doc_to_dict(e) for e in yes],
            "no": [_avail_doc_to_dict(e) for e in no],
            "reserve": [_avail_doc_to_dict(e) for e in reserve],
            "auto_match_id": auto_matches.get(d),
        })
    return {
        "days": out,
        "threshold": AUTO_MATCH_THRESHOLD,
        "auto_team_size": AUTO_MATCH_TEAM_SIZE,
    }


@api.post("/availability")
async def set_availability(data: AvailabilityIn, user=Depends(get_current_user)):
    if not DAY_RE.match(data.date):
        raise HTTPException(400, "date must be YYYY-MM-DD")
    today = datetime.now(timezone.utc).date()
    try:
        y, m, dd = [int(p) for p in data.date.split("-")]
        target = datetime(y, m, dd).date()
    except Exception:
        raise HTTPException(400, "Invalid date")
    delta_days = (target - today).days
    if delta_days < 0 or delta_days > 6:
        raise HTTPException(400, "Date must be within the next 7 days (today inclusive)")

    doc = {
        "user_id": user["id"],
        "date": data.date,
        "vote": data.vote,
        "name": user.get("name"),
        "profile_picture": user.get("profile_picture"),
        "shirt_number": user.get("shirt_number"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.availability.update_one(
        {"user_id": user["id"], "date": data.date},
        {"$set": doc},
        upsert=True,
    )

    auto_match = None
    if data.vote == "yes":
        auto_match = await _maybe_auto_create_match(data.date)

    return {
        "ok": True,
        "date": data.date,
        "vote": data.vote,
        "auto_match_id": auto_match["id"] if auto_match else None,
    }


@api.delete("/availability")
async def clear_availability(date: str, user=Depends(get_current_user)):
    """Clear the caller's availability vote for a given date (toggle off)."""
    if not DAY_RE.match(date):
        raise HTTPException(400, "date must be YYYY-MM-DD")
    await db.availability.delete_one({"user_id": user["id"], "date": date})
    return {"ok": True, "date": date}


@api.post("/admin/reset")
async def admin_reset(admin=Depends(require_admin)):
    """Wipe all matches and non-admin users, reset admin stats.
    The seeded admin, club config, and reset tokens are preserved (tokens expire)."""
    matches_deleted = await db.matches.delete_many({})
    users_deleted = await db.users.delete_many({"role": {"$ne": "admin"}})
    await db.match_comments.delete_many({})
    await db.users.update_many(
        {"role": "admin"},
        {
            "$set": {
                "goals": 0,
                "assists": 0,
                "matches_played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "league_points": 0,
            }
        },
    )
    return {
        "ok": True,
        "matches_deleted": matches_deleted.deleted_count,
        "users_deleted": users_deleted.deleted_count,
    }


@api.post("/admin/reset/matches")
async def admin_reset_matches(admin=Depends(require_admin)):
    """Delete every match (history + fixtures + votes), but keep all players
    and their career stats untouched."""
    res = await db.matches.delete_many({})
    await db.match_comments.delete_many({})
    return {"ok": True, "matches_deleted": res.deleted_count}


@api.post("/admin/reset/players")
async def admin_reset_players(admin=Depends(require_admin)):
    """Delete every non-admin player at once. Matches are preserved — but any
    references to deleted users (votes, lineup slots, chat messages) are
    cleaned up so the UI doesn't render orphaned ghost entries."""
    # Find all non-admin users first so we know which refs to scrub
    non_admins = await db.users.find(
        {"role": {"$ne": "admin"}}, {"_id": 0, "id": 1}
    ).to_list(length=None)
    ids = {u["id"] for u in non_admins}

    # Scrub match votes + lineup slots in bulk
    async for m in db.matches.find({}, {"_id": 0}):
        changed = False
        votes = m.get("votes", {}) or {}
        for uid in list(votes.keys()):
            if uid in ids:
                votes.pop(uid, None)
                changed = True
        lineup = m.get("lineup")
        if isinstance(lineup, dict):
            for k in ("team_a", "team_b", "team_c", "reserves"):
                arr = lineup.get(k) or []
                new_arr = [p for p in arr if (p or {}).get("user_id") not in ids]
                if len(new_arr) != len(arr):
                    lineup[k] = new_arr
                    changed = True
        if changed:
            await db.matches.update_one(
                {"id": m["id"]},
                {"$set": {"votes": votes, "lineup": lineup}},
            )

    # Wipe every comment by non-admin users
    if ids:
        await db.match_comments.delete_many({"user_id": {"$in": list(ids)}})

    res = await db.users.delete_many({"role": {"$ne": "admin"}})
    return {"ok": True, "users_deleted": res.deleted_count}


@api.post("/admin/reset/league")
async def admin_reset_league(admin=Depends(require_admin)):
    """Zero out league standings (wins, draws, losses, league_points) for all
    users. Goals, assists, matches_played, and match history are preserved."""
    res = await db.users.update_many(
        {},
        {"$set": {"wins": 0, "draws": 0, "losses": 0, "league_points": 0}},
    )
    return {"ok": True, "users_reset": res.modified_count}


@api.get("/")
async def root():
    return {"app": "Club Dodo", "status": "ok"}


@api.get("/download/web-bundle.zip", include_in_schema=False)
def download_web_bundle():
    """Download the latest static Expo web build (zipped)."""
    from fastapi.responses import FileResponse
    zip_path = "/app/club-dodo-web.zip"
    if not os.path.exists(zip_path):
        raise HTTPException(404, "Web bundle not built yet. Run: cd /app/frontend && npx expo export -p web && cd dist && zip -qr /app/club-dodo-web.zip .")
    return FileResponse(zip_path, filename="club-dodo-web.zip", media_type="application/zip")


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
