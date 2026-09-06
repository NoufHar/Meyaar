import os
import smtplib
import json
import re
import secrets
from pathlib import Path
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from fastapi import (
    FastAPI,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

from src.api.schemas import (
    ImageInspectionResponse,
    VectorProcessingResponse,
    VisionAnalysisResponse,
    ErrorReviewResponse,
    ErrorReviewUpdate,
    VoiceSynthesisRequest,
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    UserResponse,
    TeamInviteRequest,
    TeamCreateRequest,
    TeamJoinRequest,
    TeamRoleUpdate,
    PasswordChangeRequest,
    NewUserInterpretRequest,
    NewUserCreateRequest,
)
from src.api.auth import database_engine, ensure_app_tables, hash_password, verify_password, create_session, token_hash, current_user, save_analysis, new_invite_code, require_run_access

from src.vision.image_loader import InvalidImageError, inspect_image

from src.vision.vision_model import (
    VisionModelNotConfiguredError,
    VisionModelServiceError,
)

from src.vision.vision_pipeline import run_vision_pipeline

from agent.api.router import router as analysis_router
from agent.core.llm import get_llm

from src.api.vector_pipeline import (
    InvalidVectorFileError,
    VectorProcessingError,
    process_vector_upload,
)


app = FastAPI(
    title="Meyaar Backend API",
    version="0.1.0",
)

app.include_router(
    analysis_router,
    prefix="/api",
)


def _database_engine():
    database_url = os.getenv("MEYAAR_DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=503, detail="MEYAAR_DATABASE_URL is not configured.")
    return create_engine(database_url, pool_pre_ping=True)


@app.post("/auth/register", response_model=AuthResponse)
def register_user(body: RegisterRequest):
    email = body.email.strip().lower()
    engine = database_engine()
    with engine.begin() as connection:
        ensure_app_tables(connection)
        exists = connection.execute(text("SELECT 1 FROM public.app_users WHERE email = :email"), {"email": email}).scalar()
        if exists:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        user_id = str(__import__("uuid").uuid4())
        username_base = re.sub(r"[^a-z0-9._-]", "", email.split("@", 1)[0].lower()) or "user"
        username = username_base
        while connection.execute(text("SELECT 1 FROM public.app_users WHERE LOWER(username) = :username"), {"username": username}).scalar():
            username = f"{username_base}{secrets.randbelow(9000) + 1000}"
        connection.execute(text("INSERT INTO public.app_users (user_id, name, email, username, password_hash) VALUES (:user_id, :name, :email, :username, :password_hash)"), {
            "user_id": user_id, "name": body.name.strip(), "email": email, "username": username, "password_hash": hash_password(body.password),
        })
        token = create_session(connection, user_id)
    return {"token": token, "user": {"user_id": user_id, "name": body.name.strip(), "email": email, "username": username, "must_change_password": False, "role": None, "team_id": None, "team_name": None, "invite_code": None}}


@app.post("/auth/login", response_model=AuthResponse)
def login_user(body: LoginRequest):
    engine = database_engine()
    with engine.begin() as connection:
        ensure_app_tables(connection)
        row = connection.execute(text("""SELECT u.user_id, u.name, u.email, u.username, u.must_change_password, u.password_hash, u.active_team_id AS team_id, m.role, t.name AS team_name, t.invite_code FROM public.app_users u LEFT JOIN public.team_memberships m ON m.user_id = u.user_id AND m.team_id = u.active_team_id LEFT JOIN public.teams t ON t.team_id = u.active_team_id WHERE LOWER(u.email) = :identifier OR LOWER(u.username) = :identifier"""), {"identifier": body.email.strip().lower()}).mappings().first()
        if not row or not verify_password(body.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Incorrect email or password.")
        token = create_session(connection, str(row["user_id"]))
    return {"token": token, "user": {"user_id": str(row["user_id"]), "name": row["name"], "email": row["email"], "username": row["username"], "must_change_password": row["must_change_password"], "role": row["role"], "team_id": str(row["team_id"]) if row["team_id"] else None, "team_name": row["team_name"], "invite_code": row["invite_code"] if row["role"] in ("manager", "leader") else None}}


@app.get("/auth/me", response_model=UserResponse)
def get_current_user(user: dict = Depends(current_user)):
    return user


@app.post("/auth/presence", status_code=204)
def update_presence(user: dict = Depends(current_user)):
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        connection.execute(text("""
            INSERT INTO public.user_daily_activity (user_id, activity_date, active_seconds)
            VALUES (:user_id, CURRENT_DATE, 45)
            ON CONFLICT (user_id, activity_date) DO UPDATE
            SET active_seconds = LEAST(public.user_daily_activity.active_seconds + 45, 43200)
        """), {"user_id": user["user_id"]})
    return Response(status_code=204)


@app.post("/auth/logout", status_code=204)
def logout_user(authorization: str | None = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        engine = database_engine()
        with engine.begin() as connection:
            ensure_app_tables(connection)
            session_hash = token_hash(authorization.split(" ", 1)[1].strip())
            connection.execute(text("UPDATE public.app_users SET last_seen = NULL WHERE user_id = (SELECT user_id FROM public.auth_sessions WHERE token_hash = :token_hash)"), {"token_hash": session_hash})
            connection.execute(text("DELETE FROM public.auth_sessions WHERE token_hash = :token_hash"), {"token_hash": session_hash})
    return Response(status_code=204)


@app.put("/auth/password", status_code=204)
def change_password(body: PasswordChangeRequest, user: dict = Depends(current_user), authorization: str | None = Header(default=None)):
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="The new password must be different from the current password.")
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        stored = connection.execute(text("SELECT password_hash FROM public.app_users WHERE user_id = :user_id"), {"user_id": user["user_id"]}).scalar()
        if not stored or not verify_password(body.current_password, stored):
            raise HTTPException(status_code=401, detail="The current password is incorrect.")
        connection.execute(text("UPDATE public.app_users SET password_hash = :password_hash, must_change_password = FALSE WHERE user_id = :user_id"), {"password_hash": hash_password(body.new_password), "user_id": user["user_id"]})
        current_token = authorization.split(" ", 1)[1].strip() if authorization else ""
        connection.execute(text("DELETE FROM public.auth_sessions WHERE user_id = :user_id AND token_hash <> :current_token"), {"user_id": user["user_id"], "current_token": token_hash(current_token)})
    return Response(status_code=204)


@app.get("/teams")
def list_my_teams(user: dict = Depends(current_user)):
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        rows = connection.execute(text("""SELECT t.team_id, t.name, m.role, m.joined_at, t.invite_code FROM public.team_memberships m JOIN public.teams t ON t.team_id = m.team_id WHERE m.user_id = :user_id ORDER BY m.joined_at"""), {"user_id": user["user_id"]}).mappings().all()
    return [{**dict(row), "team_id": str(row["team_id"]), "joined_at": row["joined_at"].isoformat(), "invite_code": row["invite_code"] if row["role"] in ("manager", "leader") else None} for row in rows]


@app.post("/teams")
def create_team(body: TeamCreateRequest, user: dict = Depends(current_user)):
    team_id = str(__import__("uuid").uuid4())
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        code = new_invite_code(connection)
        connection.execute(text("INSERT INTO public.teams (team_id, name, invite_code, owner_user_id) VALUES (:team_id, :name, :code, :owner)"), {"team_id": team_id, "name": body.name.strip(), "code": code, "owner": user["user_id"]})
        connection.execute(text("INSERT INTO public.team_memberships (team_id, user_id, role) VALUES (:team_id, :user_id, 'manager')"), {"team_id": team_id, "user_id": user["user_id"]})
        connection.execute(text("UPDATE public.app_users SET active_team_id = :team_id WHERE user_id = :user_id"), {"team_id": team_id, "user_id": user["user_id"]})
    return {"team_id": team_id, "name": body.name.strip(), "role": "manager", "invite_code": code}


@app.post("/teams/join")
def join_team(body: TeamJoinRequest, user: dict = Depends(current_user)):
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        team = connection.execute(text("SELECT team_id, name FROM public.teams WHERE invite_code = :code"), {"code": body.invite_code.strip().upper()}).mappings().first()
        if not team:
            raise HTTPException(status_code=422, detail="Enter a valid team invitation code.")
        connection.execute(text("INSERT INTO public.team_memberships (team_id, user_id, role) VALUES (:team_id, :user_id, 'member') ON CONFLICT (team_id, user_id) DO NOTHING"), {"team_id": str(team["team_id"]), "user_id": user["user_id"]})
        connection.execute(text("UPDATE public.app_users SET active_team_id = :team_id WHERE user_id = :user_id"), {"team_id": str(team["team_id"]), "user_id": user["user_id"]})
    return {"team_id": str(team["team_id"]), "name": team["name"], "role": "member"}


@app.post("/teams/{team_id}/activate", response_model=UserResponse)
def activate_team(team_id: str, user: dict = Depends(current_user)):
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        membership = connection.execute(text("SELECT m.role, t.name, t.invite_code FROM public.team_memberships m JOIN public.teams t ON t.team_id = m.team_id WHERE m.team_id = :team_id AND m.user_id = :user_id"), {"team_id": team_id, "user_id": user["user_id"]}).mappings().first()
        if not membership:
            raise HTTPException(status_code=404, detail="Team membership not found.")
        connection.execute(text("UPDATE public.app_users SET active_team_id = :team_id WHERE user_id = :user_id"), {"team_id": team_id, "user_id": user["user_id"]})
    return {"user_id": user["user_id"], "name": user["name"], "email": user["email"], "username": user.get("username"), "must_change_password": user.get("must_change_password", False), "team_id": team_id, "team_name": membership["name"], "role": membership["role"], "invite_code": membership["invite_code"] if membership["role"] in ("manager", "leader") else None}


@app.delete("/teams/{team_id}", response_model=UserResponse)
def delete_team(team_id: str, user: dict = Depends(current_user)):
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        team = connection.execute(text("SELECT owner_user_id FROM public.teams WHERE team_id = :team_id"), {"team_id": team_id}).mappings().first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found.")
        if str(team["owner_user_id"]) != user["user_id"]:
            raise HTTPException(status_code=403, detail="Only the team creator can delete this team.")
        connection.execute(text("DELETE FROM public.saved_analyses WHERE team_id = :team_id"), {"team_id": team_id})
        connection.execute(text("DELETE FROM public.teams WHERE team_id = :team_id"), {"team_id": team_id})
        connection.execute(text("UPDATE public.app_users SET team_id = NULL WHERE team_id = :team_id"), {"team_id": team_id})
        connection.execute(text("""UPDATE public.app_users u SET active_team_id = (SELECT m.team_id FROM public.team_memberships m WHERE m.user_id = u.user_id ORDER BY m.joined_at LIMIT 1) WHERE u.active_team_id = :team_id"""), {"team_id": team_id})
        next_team = connection.execute(text("""SELECT t.team_id, t.name, t.invite_code, m.role FROM public.team_memberships m JOIN public.teams t ON t.team_id = m.team_id WHERE m.user_id = :user_id ORDER BY m.joined_at LIMIT 1"""), {"user_id": user["user_id"]}).mappings().first()
        next_team_id = str(next_team["team_id"]) if next_team else None
        connection.execute(text("UPDATE public.app_users SET active_team_id = :team_id WHERE user_id = :user_id"), {"team_id": next_team_id, "user_id": user["user_id"]})
    return {"user_id": user["user_id"], "name": user["name"], "email": user["email"], "username": user.get("username"), "must_change_password": user.get("must_change_password", False), "team_id": next_team_id, "team_name": next_team["name"] if next_team else None, "role": next_team["role"] if next_team else None, "invite_code": next_team["invite_code"] if next_team and next_team["role"] in ("manager", "leader") else None}


@app.get("/analyses")
def list_saved_analyses(user: dict = Depends(current_user)):
    engine = database_engine()
    with engine.begin() as connection:
        ensure_app_tables(connection)
        rows = connection.execute(text("""
            SELECT a.analysis_id, a.filename, a.analysis_type, a.status, a.compliance_score,
                   a.total_errors, a.created_at, a.user_id, u.name AS owner_name
            FROM public.saved_analyses a JOIN public.app_users u ON u.user_id = a.user_id
            WHERE (a.user_id = :user_id) OR (:is_manager AND a.team_id = :team_id)
            ORDER BY a.created_at DESC
        """), {"user_id": user["user_id"], "team_id": user["team_id"], "is_manager": user["role"] in ("manager", "leader")}).mappings().all()
    return [{**dict(row), "analysis_id": str(row["analysis_id"]), "created_at": row["created_at"].isoformat()} for row in rows]


@app.get("/analyses/{analysis_id}")
def get_saved_analysis(analysis_id: str, user: dict = Depends(current_user)):
    engine = database_engine()
    with engine.begin() as connection:
        ensure_app_tables(connection)
        payload = connection.execute(text("""SELECT result_payload FROM public.saved_analyses WHERE analysis_id = :analysis_id AND ((user_id = :user_id) OR (:is_manager AND team_id = :team_id))"""), {"analysis_id": analysis_id, "user_id": user["user_id"], "team_id": user["team_id"], "is_manager": user["role"] in ("manager", "leader")}).scalar()
    if payload is None:
        raise HTTPException(status_code=404, detail="Saved analysis not found.")
    return payload


@app.get("/team/dashboard")
def team_dashboard(user: dict = Depends(current_user)):
    if user["role"] not in ("manager", "leader"):
        raise HTTPException(status_code=403, detail="Manager or team leader access is required.")
    engine = database_engine()
    with engine.begin() as connection:
        ensure_app_tables(connection)
        members = connection.execute(text("""
            SELECT u.user_id, u.name, u.email, m.role, m.joined_at AS created_at, u.last_seen,
                   (u.last_seen IS NOT NULL AND u.last_seen >= CURRENT_TIMESTAMP - INTERVAL '2 minutes') AS is_online,
                   COALESCE((SELECT SUM(active_seconds) FROM public.user_daily_activity d WHERE d.user_id = u.user_id AND d.activity_date >= DATE_TRUNC('week', CURRENT_DATE)::date), 0)::int AS active_seconds_today,
                   COUNT(a.analysis_id)::int AS analyses_count,
                   COALESCE(SUM(a.total_errors), 0)::int AS total_errors
            FROM public.team_memberships m JOIN public.app_users u ON u.user_id = m.user_id
            LEFT JOIN public.saved_analyses a ON a.user_id = u.user_id AND a.team_id = m.team_id
            WHERE m.team_id = :team_id GROUP BY u.user_id, m.role, m.joined_at ORDER BY m.role, u.name
        """), {"team_id": user["team_id"]}).mappings().all()
        totals = connection.execute(text("""
            SELECT COUNT(DISTINCT user_id)::int AS active_members, COUNT(*)::int AS analyses_count,
                   COALESCE(SUM(total_errors), 0)::int AS total_errors,
                   ROUND(AVG(compliance_score)::numeric, 1) AS average_compliance
            FROM public.saved_analyses WHERE team_id = :team_id
        """), {"team_id": user["team_id"]}).mappings().one()
    return {"team": {"team_id": user["team_id"], "name": user["team_name"], "invite_code": user["invite_code"]}, "summary": dict(totals), "members": [{**dict(row), "user_id": str(row["user_id"]), "created_at": row["created_at"].isoformat()} for row in members]}


@app.get("/team/members/{member_id}/dashboard")
def member_work_dashboard(member_id: str, user: dict = Depends(current_user)):
    if user["role"] not in ("manager", "leader") or not user["team_id"]:
        raise HTTPException(status_code=403, detail="Manager or team leader access is required.")
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        member = connection.execute(text("""
            SELECT u.user_id, u.name, u.email, m.role,
                   COALESCE((SELECT SUM(active_seconds) FROM public.user_daily_activity d WHERE d.user_id = u.user_id AND d.activity_date >= DATE_TRUNC('week', CURRENT_DATE)::date), 0)::int AS active_seconds_today
            FROM public.team_memberships m JOIN public.app_users u ON u.user_id = m.user_id
            WHERE m.team_id = :team_id AND m.user_id = :member_id
        """), {"team_id": user["team_id"], "member_id": member_id}).mappings().first()
        if not member:
            raise HTTPException(status_code=404, detail="Team member not found.")
        summary = connection.execute(text("""
            SELECT COUNT(*)::int AS analyses_count, COALESCE(SUM(total_errors), 0)::int AS total_errors,
                   ROUND(AVG(compliance_score)::numeric, 1) AS average_compliance,
                   COUNT(*) FILTER (WHERE created_at::date = CURRENT_DATE)::int AS analyses_today
            FROM public.saved_analyses WHERE team_id = :team_id AND user_id = :member_id
        """), {"team_id": user["team_id"], "member_id": member_id}).mappings().one()
        recent = connection.execute(text("""
            SELECT analysis_id, filename, analysis_type, total_errors, compliance_score, created_at
            FROM public.saved_analyses WHERE team_id = :team_id AND user_id = :member_id
            ORDER BY created_at DESC LIMIT 5
        """), {"team_id": user["team_id"], "member_id": member_id}).mappings().all()
    active_seconds = int(member["active_seconds_today"] or 0)
    return {"member": {**dict(member), "user_id": str(member["user_id"]), "work_hours_today": round(active_seconds / 3600, 1), "work_percentage": min(round(active_seconds / 28800 * 100), 100)}, "summary": dict(summary), "recent_analyses": [{**dict(row), "analysis_id": str(row["analysis_id"]), "created_at": row["created_at"].isoformat()} for row in recent]}


@app.patch("/teams/{team_id}/members/{member_id}/role")
def update_team_role(team_id: str, member_id: str, body: TeamRoleUpdate, user: dict = Depends(current_user)):
    if user["role"] != "manager" or user["team_id"] != team_id:
        raise HTTPException(status_code=403, detail="Only this team's manager can change member roles.")
    if member_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="The team manager cannot change their own role.")
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        updated = connection.execute(text("UPDATE public.team_memberships SET role = :role WHERE team_id = :team_id AND user_id = :member_id AND role <> 'manager' RETURNING user_id"), {"role": body.role, "team_id": team_id, "member_id": member_id}).scalar()
    if not updated:
        raise HTTPException(status_code=404, detail="Team member not found.")
    return {"user_id": str(updated), "role": body.role}


def _strip_json_fence(value: str) -> str:
    value = value.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1]
        if value.endswith("```"):
            value = value[:-3]
    return value.strip()


def _interpret_new_user(instruction: str) -> dict:
    llm = get_llm()
    if llm is not None:
        prompt = """You interpret an Arabic or English team-management instruction. Do not execute anything. Return strict JSON only with: action (add, remove, create_team, delete_team, change_role, list_members, or team_summary), name (employee name or null), email (optional personal email or null), team_name (new team name or null), role (member or leader), suggested_username (lowercase ASCII only), missing_fields (array). Never choose manager. Adding requires a name; personal email is optional. Removing and changing role require an existing member name/email. Creating a team requires team_name. delete_team means delete the current team and never means remove one member. Examples: {\"action\":\"add\",\"name\":\"Sara\",\"email\":null,\"team_name\":null,\"role\":\"member\",\"suggested_username\":\"sara\",\"missing_fields\":[]}; {\"action\":\"delete_team\",\"team_name\":null,\"name\":null,\"email\":null,\"role\":\"member\",\"suggested_username\":null,\"missing_fields\":[]}. Instruction: """ + instruction
        try:
            parsed = json.loads(_strip_json_fence(str(llm.invoke(prompt).content)))
            name = str(parsed.get("name") or "").strip()
            personal_email = str(parsed.get("email") or "").strip() or None
            team_name = str(parsed.get("team_name") or "").strip() or None
            allowed = {"add", "remove", "create_team", "delete_team", "change_role", "list_members", "team_summary"}
            action = parsed.get("action") if parsed.get("action") in allowed else "add"
            missing = []
            if action == "add" and not name: missing.append("name")
            if action in ("remove", "change_role") and not (name or personal_email): missing.append("name")
            if action == "create_team" and not team_name: missing.append("team_name")
            return {"action": action, "name": name or None, "email": personal_email, "team_name": team_name, "role": "leader" if parsed.get("role") == "leader" else "member", "suggested_username": re.sub(r"[^a-z0-9.]", "", str(parsed.get("suggested_username") or "").lower()) or None, "missing_fields": missing}
        except Exception:
            pass
    email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", instruction, re.I)
    name_match = re.search(r"(?:اسم(?:ها|ه)?|named?|user)\s*[:：]?\s*([\u0600-\u06FFA-Za-z][\u0600-\u06FFA-Za-z ]{1,40})", instruction, re.I)
    name = name_match.group(1).strip() if name_match else ""
    name = re.split(r"\s+(?:بريد|email|دور|role|في|in)\b", name, maxsplit=1, flags=re.I)[0].strip()
    team_match = re.search(r"(?:team|فريق|تيم).*?(?:named?|اسم(?:ه)?)\s*[:：]?\s*([\u0600-\u06FFA-Za-z0-9 _-]{2,50})", instruction, re.I)
    if not team_match:
        team_match = re.search(r"(?:create|new|أنشئ|انشئ|سوي|سوّي)\s+(?:a\s+)?(?:new\s+)?(?:team|فريق|تيم)\s*[:：]?\s*([\u0600-\u06FFA-Za-z0-9 _-]{2,50})", instruction, re.I)
    team_name = team_match.group(1).strip() if team_match else None
    if re.search(r"\b(delete|remove)\s+(?:the\s+|this\s+|current\s+)?team\b|(?:احذف|حذف|شيل|أزل)\s+(?:هذا\s+|هذي\s+)?(?:الفريق|التيم)\b", instruction, re.I): action = "delete_team"
    elif re.search(r"\b(create|new)\b.*\bteam\b|(?:أنشئ|انشئ|سوي|سوّي|جديد).*?(?:فريق|تيم)", instruction, re.I): action = "create_team"
    elif re.search(r"\b(remove|delete)\b|احذف|حذف|شيل|أزل|ازالة|إزالة", instruction, re.I): action = "remove"
    elif re.search(r"promote|demote|change.*role|رقّي|رقي|غيّر.*دور|خليه.*ليدر|خليها.*ليدر", instruction, re.I): action = "change_role"
    elif re.search(r"list.*member|show.*member|اعرض.*(?:الأعضاء|الاعضاء)|مين.*الفريق", instruction, re.I): action = "list_members"
    elif re.search(r"summary|statistics|stats|ملخص|إحصائيات|احصائيات", instruction, re.I): action = "team_summary"
    else: action = "add"
    missing_fields = []
    if action == "add" and not name: missing_fields.append("name")
    if action in ("remove", "change_role") and not (name or email_match): missing_fields.append("name")
    if action == "create_team" and not team_name: missing_fields.append("team_name")
    return {"action": action, "name": name or None, "email": email_match.group(0).lower() if email_match else None, "team_name": team_name, "role": "leader" if re.search(r"team\s*leader|تيم\s*ليدر|قائد|leader|ليدر", instruction, re.I) else "member", "suggested_username": re.sub(r"[^a-z0-9.]", "", name.lower().replace(" ", ".")) or None, "missing_fields": missing_fields}


@app.post("/team/users/interpret")
async def interpret_new_team_user(body: NewUserInterpretRequest, user: dict = Depends(current_user)):
    if user["role"] != "manager":
        raise HTTPException(status_code=403, detail="Only the team manager can create users.")
    return await run_in_threadpool(_interpret_new_user, body.instruction)


@app.post("/team/users", status_code=201)
def create_team_user(body: NewUserCreateRequest, user: dict = Depends(current_user)):
    if user["role"] != "manager" or not user["team_id"]:
        raise HTTPException(status_code=403, detail="Only the team manager can create users.")
    personal_email = body.email.strip().lower() if body.email else None
    if personal_email:
        parsed_email = parseaddr(personal_email)[1]
        if parsed_email != personal_email or "@" not in personal_email or "." not in personal_email.rsplit("@", 1)[-1]:
            raise HTTPException(status_code=422, detail="Enter a valid personal email address.")
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        base = re.sub(r"[^a-z0-9._-]", "", (body.suggested_username or "").lower()) or "user"
        base = base[:36].strip("._-") or "user"
        username = base
        while connection.execute(text("SELECT 1 FROM public.app_users WHERE LOWER(username) = :username"), {"username": username}).scalar():
            username = f"{base[:32]}{secrets.randbelow(9000) + 1000}"
        account_email = f"{username}@meyaar.com"
        temporary_password = secrets.token_urlsafe(10) + "!A7"
        member_id = str(__import__("uuid").uuid4())
        connection.execute(text("""INSERT INTO public.app_users (user_id, name, email, personal_email, username, password_hash, active_team_id, must_change_password) VALUES (:user_id, :name, :email, :personal_email, :username, :password_hash, :team_id, TRUE)"""), {"user_id": member_id, "name": body.name.strip(), "email": account_email, "personal_email": personal_email, "username": username, "password_hash": hash_password(temporary_password), "team_id": user["team_id"]})
        connection.execute(text("INSERT INTO public.team_memberships (team_id, user_id, role) VALUES (:team_id, :user_id, :role)"), {"team_id": user["team_id"], "user_id": member_id, "role": body.role})
        connection.execute(text("""INSERT INTO public.audit_logs (actor_user_id, team_id, action, target_user_id, details) VALUES (:actor, :team, 'user_created', :target, CAST(:details AS JSONB))"""), {"actor": user["user_id"], "team": user["team_id"], "target": member_id, "details": json.dumps({"role": body.role, "username": username})})
        if personal_email:
            try:
                _send_new_user_welcome(personal_email, body.name.strip(), user["team_name"], account_email, username, temporary_password)
            except RuntimeError as error:
                raise HTTPException(status_code=503, detail=str(error)) from error
            except (OSError, smtplib.SMTPException) as error:
                raise HTTPException(status_code=502, detail=f"Welcome email could not be sent: {error}") from error
    return {"user_id": member_id, "name": body.name.strip(), "email": account_email, "personal_email": personal_email, "username": username, "role": body.role, "temporary_password": temporary_password, "must_change_password": True, "welcome_email_sent": bool(personal_email)}


@app.delete("/teams/{team_id}/members/{member_id}", status_code=204)
def remove_team_member(team_id: str, member_id: str, user: dict = Depends(current_user)):
    if user["role"] != "manager" or user["team_id"] != team_id:
        raise HTTPException(status_code=403, detail="Only this team's manager can remove members.")
    if member_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="The manager cannot remove themselves from their team.")
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        member = connection.execute(text("SELECT role FROM public.team_memberships WHERE team_id = :team_id AND user_id = :member_id"), {"team_id": team_id, "member_id": member_id}).mappings().first()
        if not member:
            raise HTTPException(status_code=404, detail="Team member not found.")
        if member["role"] == "manager":
            raise HTTPException(status_code=400, detail="A team manager cannot be removed.")
        connection.execute(text("DELETE FROM public.team_memberships WHERE team_id = :team_id AND user_id = :member_id"), {"team_id": team_id, "member_id": member_id})
        connection.execute(text("UPDATE public.app_users SET active_team_id = (SELECT team_id FROM public.team_memberships WHERE user_id = :member_id ORDER BY joined_at LIMIT 1) WHERE user_id = :member_id AND active_team_id = :team_id"), {"member_id": member_id, "team_id": team_id})
        connection.execute(text("""INSERT INTO public.audit_logs (actor_user_id, team_id, action, target_user_id, details) VALUES (:actor, :team, 'member_removed', :target, CAST(:details AS JSONB))"""), {"actor": user["user_id"], "team": team_id, "target": member_id, "details": json.dumps({"previous_role": member["role"]})})


def _send_new_user_welcome(recipient: str, employee_name: str, team_name: str, account_email: str, username: str, temporary_password: str) -> None:
    host = os.getenv("MEYAAR_SMTP_HOST")
    smtp_username = os.getenv("MEYAAR_SMTP_USER")
    smtp_password = os.getenv("MEYAAR_SMTP_PASSWORD")
    sender = os.getenv("MEYAAR_SMTP_FROM") or smtp_username
    if not host or not sender:
        raise RuntimeError("Email service is not configured. Add MEYAAR_SMTP_HOST and MEYAAR_SMTP_FROM to the backend environment.")
    port = int(os.getenv("MEYAAR_SMTP_PORT", "587"))
    message = EmailMessage()
    message["Subject"] = f"Welcome to {team_name} on MEYAAR"
    message["From"] = formataddr(("MEYAAR", sender))
    message["To"] = recipient
    message.set_content(
        f"Welcome {employee_name}!\n\nYour MEYAAR account for {team_name} is ready.\n"
        f"Account email: {account_email}\nUsername: {username}\nTemporary password: {temporary_password}\n\n"
        "You must change this temporary password when you sign in for the first time.\n\n"
        f"مرحبًا {employee_name}! تم إنشاء حسابك في فريق {team_name}.\n"
        f"بريد الدخول: {account_email}\nاسم المستخدم: {username}\nكلمة المرور المؤقتة: {temporary_password}\n"
        "سيُطلب منك تغيير كلمة المرور عند أول تسجيل دخول."
    )
    server = smtplib.SMTP_SSL(host, port, timeout=20) if port == 465 else smtplib.SMTP(host, port, timeout=20)
    try:
        if port != 465 and os.getenv("MEYAAR_SMTP_TLS", "true").lower() == "true":
            server.starttls()
        if smtp_username and smtp_password:
            server.login(smtp_username, smtp_password)
        server.send_message(message)
    finally:
        server.quit()


def _send_team_invitation(recipient: str, team_name: str, manager_name: str, manager_email: str, invite_code: str) -> None:
    host = os.getenv("MEYAAR_SMTP_HOST")
    username = os.getenv("MEYAAR_SMTP_USER")
    password = os.getenv("MEYAAR_SMTP_PASSWORD")
    sender = os.getenv("MEYAAR_SMTP_FROM") or username
    if not host or not sender:
        raise RuntimeError("Email service is not configured. Add MEYAAR_SMTP_HOST and MEYAAR_SMTP_FROM to the backend environment.")
    port = int(os.getenv("MEYAAR_SMTP_PORT", "587"))
    message = EmailMessage()
    message["Subject"] = f"Invitation to join {team_name} on MEYAAR"
    message["From"] = formataddr((f"{manager_name} via MEYAAR", sender))
    message["To"] = recipient
    message["Reply-To"] = formataddr((manager_name, manager_email))
    message.set_content(
        f"{manager_name} invited you to join {team_name} on MEYAAR.\n\n"
        f"Create an Employee account and enter this invitation code:\n{invite_code}\n\n"
        "تمت دعوتك للانضمام إلى فريق معيار. أنشئ حساب موظف وأدخل رمز الدعوة الموضح أعلاه."
    )
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        server = smtplib.SMTP(host, port, timeout=20)
        if os.getenv("MEYAAR_SMTP_TLS", "true").lower() == "true":
            server.starttls()
    try:
        if username and password:
            server.login(username, password)
        server.send_message(message)
    finally:
        server.quit()


@app.post("/team/invitations", status_code=202)
async def invite_team_member(body: TeamInviteRequest, user: dict = Depends(current_user)):
    if user["role"] not in ("manager", "leader"):
        raise HTTPException(status_code=403, detail="Manager or team leader access is required.")
    recipient = body.email.strip().lower()
    parsed = parseaddr(recipient)[1]
    if parsed != recipient or "@" not in parsed or "." not in parsed.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    engine = database_engine()
    with engine.begin() as connection:
        ensure_app_tables(connection)
        existing = connection.execute(text("SELECT 1 FROM public.app_users WHERE email = :email"), {"email": recipient}).scalar()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    try:
        await run_in_threadpool(_send_team_invitation, recipient, user["team_name"], user["name"], user["email"], user["invite_code"])
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (OSError, smtplib.SMTPException) as error:
        raise HTTPException(status_code=502, detail=f"Invitation email could not be sent: {error}") from error
    return {"status": "sent", "email": recipient}


def _ensure_review_table(connection) -> None:
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS public.validation_reviews (
            result_id BIGINT PRIMARY KEY REFERENCES public.validation_results(result_id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'confirmed', 'resolved', 'false_positive')),
            comment TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))

MAX_IMAGE_SIZE = 25 * 1024 * 1024

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
}


@app.get("/", include_in_schema=False)
def api_home():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/voice/synthesize")
async def synthesize_agent_voice(body: VoiceSynthesisRequest, user: dict = Depends(current_user)):
    from src.voice.voice_summary import synthesize_speech_bytes

    try:
        audio = await run_in_threadpool(synthesize_speech_bytes, body.text, body.voice)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Audio generation failed: {error}") from error

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Content-Disposition": 'attachment; filename="meyaar-agent-explanation.wav"'},
    )


@app.get("/reviews/{result_id}", response_model=ErrorReviewResponse)
def get_error_review(result_id: int, user: dict = Depends(current_user)):
    engine = _database_engine()
    with engine.begin() as connection:
        _ensure_review_table(connection)
        run_id = connection.execute(text("SELECT run_id FROM public.validation_results WHERE result_id = :result_id"), {"result_id": result_id}).scalar()
        if not run_id:
            raise HTTPException(status_code=404, detail="Validation result not found.")
        require_run_access(connection, user, str(run_id))
        row = connection.execute(text("SELECT result_id, status, comment, updated_at FROM public.validation_reviews WHERE result_id = :result_id"), {"result_id": result_id}).mappings().first()
    if not row:
        return ErrorReviewResponse(result_id=result_id, status="new", comment="", updated_at=None)
    review = dict(row)
    review["updated_at"] = row["updated_at"].isoformat()
    return ErrorReviewResponse(**review)


@app.put("/reviews/{result_id}", response_model=ErrorReviewResponse)
def save_error_review(result_id: int, body: ErrorReviewUpdate, user: dict = Depends(current_user)):
    engine = _database_engine()
    with engine.begin() as connection:
        _ensure_review_table(connection)
        run_id = connection.execute(text("SELECT run_id FROM public.validation_results WHERE result_id = :result_id"), {"result_id": result_id}).scalar()
        if not run_id:
            raise HTTPException(status_code=404, detail="Validation result not found.")
        require_run_access(connection, user, str(run_id))
        row = connection.execute(text("""
            INSERT INTO public.validation_reviews (result_id, status, comment)
            VALUES (:result_id, :status, :comment)
            ON CONFLICT (result_id) DO UPDATE SET status = EXCLUDED.status, comment = EXCLUDED.comment, updated_at = CURRENT_TIMESTAMP
            RETURNING result_id, status, comment, updated_at
        """), {"result_id": result_id, "status": body.status, "comment": body.comment}).mappings().one()
    review = dict(row)
    review["updated_at"] = row["updated_at"].isoformat()
    return ErrorReviewResponse(**review)


@app.post("/reports/pdf")
async def create_report_pdf(payload: dict, user: dict = Depends(current_user)):
    from src.reporting.simple_pdf import build_report_pdf
    pdf = await run_in_threadpool(build_report_pdf, payload)
    filename = Path(str(payload.get("filename", "meyaar"))).stem
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}-meyaar-report.pdf"'})


@app.post("/images/inspect", response_model=ImageInspectionResponse)
async def inspect_uploaded_image(file: UploadFile = File(...)):
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Supported formats: JPG, JPEG, PNG, TIF, and TIFF.",
        )

    content = await file.read(MAX_IMAGE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The image exceeds the 25 MB limit.",
        )

    try:
        metadata = inspect_image(content)
    except InvalidImageError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return ImageInspectionResponse(
        filename=filename,
        size_bytes=len(content),
        **metadata,
    )



@app.post("/images/analyze", response_model=VisionAnalysisResponse)
async def analyze_uploaded_image(
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
):
    if not user["team_id"]:
        raise HTTPException(status_code=403, detail="Create or join a team before starting an analysis.")
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Supported formats: JPG, JPEG, PNG, TIF, and TIFF.",
        )

    content = await file.read(MAX_IMAGE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The image exceeds the 25 MB limit.",
        )

    try:
        inspect_image(content)
        result = await run_in_threadpool(
            run_vision_pipeline,
            filename,
            content,
        )
        analysis_id = await run_in_threadpool(
            save_analysis,
            user["user_id"], user["team_id"],
            filename,
            "image",
            result.model_dump(mode="json"),
        )
        result.analysis_id = analysis_id
        return result

    except InvalidImageError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except VisionModelNotConfiguredError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    except VisionModelServiceError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error



MAX_VECTOR_SIZE = 100 * 1024 * 1024


@app.post(
    "/vectors/process",
    response_model=VectorProcessingResponse,
)
async def process_uploaded_vector(
    file: UploadFile = File(...),
    layer_type: str | None = Form(None),
    user: dict = Depends(current_user),
):
    if not user["team_id"]:
        raise HTTPException(status_code=403, detail="Create or join a team before starting an analysis.")
    filename = file.filename or ""

    content = await file.read(
        MAX_VECTOR_SIZE + 1
    )

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_VECTOR_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                "The vector file exceeds "
                "the 100 MB limit."
            ),
        )

    try:
        result = await run_in_threadpool(
            process_vector_upload,
            filename,
            content,
            layer_type,
        )
        analysis_id = await run_in_threadpool(save_analysis, user["user_id"], user["team_id"], filename, "vector", result)
        result["analysis_id"] = analysis_id
        return result

    except InvalidVectorFileError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except VectorProcessingError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Vector processing failed: "
                f"{error}"
            ),
        ) from error
