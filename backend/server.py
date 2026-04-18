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
    # simple transparent formula
    return round(goals * 3 + assists * 2 + matches_played * 1, 2)


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


# ---------- Startup ----------
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.matches.create_index("id", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_tokens.create_index("email")
    await db.match_comments.create_index([("match_id", 1), ("created_at", 1)])
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
    """Dev-mode flow: generate 6-digit code, store it, and return it
    in the response so the user can enter it on the reset screen.
    Still silently succeeds when email doesn't exist to avoid leaking
    registered emails."""
    import secrets
    email = data.email.lower()
    u = await db.users.find_one({"email": email}, {"_id": 0})
    # Clean up expired tokens for this email to avoid collisions
    await db.password_reset_tokens.delete_many({"email": email})
    if not u:
        return {"ok": True, "dev_code": None, "message": "If that email is registered, a code has been generated."}
    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.password_reset_tokens.insert_one(
        {
            "email": email,
            "code_hash": hash_password(code),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "used": False,
        }
    )
    logger.info("Password reset code for %s: %s (dev mode)", email, code)
    return {
        "ok": True,
        "dev_code": code,  # dev-mode: returned so the UI can display it
        "message": "Code generated. It expires in 60 minutes.",
    }


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
                        "preferred_position": None,
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


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
