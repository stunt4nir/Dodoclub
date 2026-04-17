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
from typing import List, Optional, Literal

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
    return {
        "id": u["id"],
        "email": u.get("email"),
        "name": u.get("name"),
        "profile_picture": u.get("profile_picture"),
        "shirt_number": u.get("shirt_number"),
        "role": u.get("role", "user"),
        "can_edit_matches": u.get("can_edit_matches", False),
        "goals": u.get("goals", 0),
        "assists": u.get("assists", 0),
        "matches_played": u.get("matches_played", 0),
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
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=40)
    shirt_number: Optional[int] = Field(default=None, ge=1, le=99)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    profile_picture: Optional[str] = None  # base64
    shirt_number: Optional[int] = Field(default=None, ge=1, le=99)


class MatchCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    date: str  # ISO date "2026-03-01" or ISO datetime
    location: Optional[str] = Field(default=None, max_length=120)
    team_size: int = Field(default=5, ge=3, le=11)


class VoteIn(BaseModel):
    vote: Literal["yes", "no", "reserve"]


class PlayerStatLine(BaseModel):
    user_id: str
    goals: int = 0
    assists: int = 0


class MatchResultIn(BaseModel):
    team_a_score: int = Field(ge=0)
    team_b_score: int = Field(ge=0)
    stats: List[PlayerStatLine] = []


class ClubConfigUpdate(BaseModel):
    club_name: Optional[str] = Field(default=None, min_length=1, max_length=40)
    club_logo: Optional[str] = None  # base64


class GrantEditIn(BaseModel):
    user_id: str
    can_edit_matches: bool


# ---------- Startup ----------
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.matches.create_index("id", unique=True)
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
    doc = {
        "id": uid,
        "email": email,
        "password_hash": hash_password(data.password),
        "name": data.name,
        "profile_picture": None,
        "shirt_number": data.shirt_number,
        "role": "user",
        "can_edit_matches": False,
        "goals": 0,
        "assists": 0,
        "matches_played": 0,
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


# ---------- Users ----------
@api.get("/users")
async def list_users(user=Depends(get_current_user)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    pubs = [user_public(u) for u in users]
    pubs.sort(key=lambda x: x["rating"], reverse=True)
    return pubs


@api.put("/users/me")
async def update_profile(data: ProfileUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
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
        "status": m.get("status", "voting"),
        "created_by": m.get("created_by"),
        "created_at": m.get("created_at"),
        "votes": vote_list,
        "lineup": m.get("lineup"),
        "result": m.get("result"),
    }


async def _users_map():
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
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
        "status": "voting",
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "votes": {},
        "lineup": None,
        "result": None,
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


def _build_lineup(vote_list: list, team_size: int) -> dict:
    """Distribute 'yes' voters between Team A & Team B using snake draft by rating.
    Overflow go to reserves. Users who voted 'reserve' also go to reserves."""
    yes_voters = [v for v in vote_list if v["vote"] == "yes"]
    reserve_voters = [v for v in vote_list if v["vote"] == "reserve"]
    # Sort by rating desc
    yes_voters.sort(key=lambda x: x.get("rating", 0), reverse=True)

    team_a, team_b = [], []
    on_pitch = yes_voters[: team_size * 2]
    overflow = yes_voters[team_size * 2 :]

    # Snake draft
    for i, p in enumerate(on_pitch):
        round_num = i // 2
        if round_num % 2 == 0:
            (team_a if i % 2 == 0 else team_b).append(p)
        else:
            (team_b if i % 2 == 0 else team_a).append(p)

    return {
        "team_a": team_a,
        "team_b": team_b,
        "reserves": overflow + reserve_voters,
        "team_size": team_size,
    }


@api.post("/matches/{mid}/generate-lineup")
async def generate_lineup(mid: str, user=Depends(require_editor)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")
    umap = await _users_map()
    full = _match_public(m, umap)
    lineup = _build_lineup(full["votes"], m.get("team_size", 5))
    await db.matches.update_one(
        {"id": mid}, {"$set": {"lineup": lineup, "status": "scheduled"}}
    )
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    return _match_public(m, umap)


@api.post("/matches/{mid}/result")
async def record_result(mid: str, data: MatchResultIn, user=Depends(require_editor)):
    m = await db.matches.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Match not found")

    # If lineup not yet generated, auto-generate using current votes
    if not m.get("lineup"):
        umap = await _users_map()
        full = _match_public(m, umap)
        lineup = _build_lineup(full["votes"], m.get("team_size", 5))
        await db.matches.update_one({"id": mid}, {"$set": {"lineup": lineup}})
        m["lineup"] = lineup

    # If a prior result exists, revert previous stat contributions first
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

    # Compute participants = everyone in team_a + team_b of lineup
    lineup = m["lineup"]
    participants = [p["user_id"] for p in lineup.get("team_a", [])] + [
        p["user_id"] for p in lineup.get("team_b", [])
    ]

    # Apply new stats
    for uid in participants:
        await db.users.update_one({"id": uid}, {"$inc": {"matches_played": 1}})
    for s in data.stats:
        await db.users.update_one(
            {"id": s.user_id},
            {"$inc": {"goals": int(s.goals), "assists": int(s.assists)}},
        )

    result = {
        "team_a_score": data.team_a_score,
        "team_b_score": data.team_b_score,
        "stats": [s.dict() for s in data.stats],
        "participants": participants,
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
    await db.matches.delete_one({"id": mid})
    return {"ok": True}


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
