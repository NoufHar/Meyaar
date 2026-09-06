from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy import create_engine, text


SESSION_DAYS = 14


def database_engine():
    database_url = os.getenv("MEYAAR_DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=503, detail="MEYAAR_DATABASE_URL is not configured.")
    return create_engine(database_url, pool_pre_ping=True)


def ensure_app_tables(connection) -> None:
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS public.app_users (
            user_id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS public.teams (
            team_id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            invite_code TEXT NOT NULL UNIQUE,
            owner_user_id UUID NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))
    connection.execute(text("ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user'"))
    connection.execute(text("ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS team_id UUID"))
    connection.execute(text("ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS active_team_id UUID"))
    connection.execute(text("ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS username TEXT"))
    connection.execute(text("ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS personal_email TEXT"))
    connection.execute(text("ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ"))
    connection.execute(text("ALTER TABLE public.app_users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE"))
    connection.execute(text("ALTER TABLE public.app_users ALTER COLUMN email DROP NOT NULL"))
    connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_app_users_username_unique ON public.app_users(LOWER(username)) WHERE username IS NOT NULL"))
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS public.user_daily_activity (
            user_id UUID NOT NULL REFERENCES public.app_users(user_id) ON DELETE CASCADE,
            activity_date DATE NOT NULL DEFAULT CURRENT_DATE,
            active_seconds INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, activity_date)
        )
    """))
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS public.audit_logs (
            audit_id BIGSERIAL PRIMARY KEY,
            actor_user_id UUID REFERENCES public.app_users(user_id) ON DELETE SET NULL,
            team_id UUID,
            action TEXT NOT NULL,
            target_user_id UUID,
            details JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS public.team_memberships (
            team_id UUID NOT NULL REFERENCES public.teams(team_id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES public.app_users(user_id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('manager', 'leader', 'member')),
            joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (team_id, user_id)
        )
    """))
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS public.auth_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES public.app_users(user_id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS public.saved_analyses (
            analysis_id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES public.app_users(user_id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            analysis_type TEXT NOT NULL CHECK (analysis_type IN ('vector', 'image')),
            status TEXT NOT NULL,
            compliance_score DOUBLE PRECISION,
            total_errors INTEGER NOT NULL DEFAULT 0,
            result_payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))
    connection.execute(text("ALTER TABLE public.saved_analyses ADD COLUMN IF NOT EXISTS team_id UUID"))
    connection.execute(text("CREATE TABLE IF NOT EXISTS public.app_migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
    migrated = connection.execute(text("SELECT 1 FROM public.app_migrations WHERE name = 'team_memberships_v1'")).scalar()
    if not migrated:
        legacy_users = connection.execute(text("SELECT user_id, name FROM public.app_users WHERE team_id IS NULL")).mappings().all()
        for legacy_user in legacy_users:
            team_id = str(uuid.uuid4())
            invite_code = new_invite_code(connection)
            connection.execute(text("INSERT INTO public.teams (team_id, name, invite_code, owner_user_id) VALUES (:team_id, :name, :code, :owner)"), {"team_id": team_id, "name": f"{legacy_user['name']}'s Team", "code": invite_code, "owner": str(legacy_user["user_id"])})
            connection.execute(text("UPDATE public.app_users SET team_id = :team_id, role = 'manager' WHERE user_id = :user_id"), {"team_id": team_id, "user_id": str(legacy_user["user_id"])})
            connection.execute(text("UPDATE public.saved_analyses SET team_id = :team_id WHERE user_id = :user_id AND team_id IS NULL"), {"team_id": team_id, "user_id": str(legacy_user["user_id"])})
        connection.execute(text("INSERT INTO public.app_migrations (name) VALUES ('team_memberships_v1')"))
    connection.execute(text("""
        INSERT INTO public.team_memberships (team_id, user_id, role)
        SELECT u.team_id, u.user_id, CASE WHEN u.role = 'manager' THEN 'manager' ELSE 'member' END
        FROM public.app_users u JOIN public.teams t ON t.team_id = u.team_id
        ON CONFLICT (team_id, user_id) DO NOTHING
    """))
    connection.execute(text("UPDATE public.app_users SET active_team_id = team_id WHERE active_team_id IS NULL AND team_id IS NOT NULL"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS idx_saved_analyses_user_created ON public.saved_analyses(user_id, created_at DESC)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS idx_saved_analyses_team_created ON public.saved_analyses(team_id, created_at DESC)"))


def new_invite_code(connection) -> str:
    for _ in range(10):
        code = secrets.token_hex(4).upper()
        if not connection.execute(text("SELECT 1 FROM public.teams WHERE invite_code = :code"), {"code": code}).scalar():
            return code
    raise HTTPException(status_code=500, detail="Could not create a unique team code.")


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256$210000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(connection, user_id: str) -> str:
    token = secrets.token_urlsafe(40)
    connection.execute(text("DELETE FROM public.auth_sessions WHERE expires_at <= CURRENT_TIMESTAMP"))
    connection.execute(text("""
        INSERT INTO public.auth_sessions (token_hash, user_id, expires_at)
        VALUES (:token_hash, :user_id, :expires_at)
    """), {
        "token_hash": token_hash(token),
        "user_id": user_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
    })
    return token


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in is required.")
    token = authorization.split(" ", 1)[1].strip()
    engine = database_engine()
    with engine.begin() as connection:
        ensure_app_tables(connection)
        row = connection.execute(text("""
            SELECT u.user_id, u.name, u.email, u.username, u.must_change_password, m.role, u.active_team_id AS team_id, u.created_at,
                   t.name AS team_name, t.invite_code
            FROM public.auth_sessions s
            JOIN public.app_users u ON u.user_id = s.user_id
            LEFT JOIN public.team_memberships m ON m.user_id = u.user_id AND m.team_id = u.active_team_id
            LEFT JOIN public.teams t ON t.team_id = u.active_team_id
            WHERE s.token_hash = :token_hash AND s.expires_at > CURRENT_TIMESTAMP
        """), {"token_hash": token_hash(token)}).mappings().first()
        if row:
            connection.execute(text("UPDATE public.app_users SET last_seen = CURRENT_TIMESTAMP WHERE user_id = :user_id"), {"user_id": str(row["user_id"])})
    if not row:
        raise HTTPException(status_code=401, detail="Your session is invalid or expired.")
    result = dict(row)
    result["user_id"] = str(row["user_id"])
    result["team_id"] = str(row["team_id"]) if row["team_id"] else None
    if result["role"] not in ("manager", "leader"):
        result["invite_code"] = None
    return result


def require_run_access(connection, user: dict, run_id: str) -> None:
    allowed = connection.execute(text("""
        SELECT 1 FROM public.saved_analyses
        WHERE result_payload->>'run_id' = :run_id
          AND ((user_id = :user_id) OR (:is_manager AND team_id = :team_id))
    """), {"run_id": run_id, "user_id": user["user_id"], "team_id": user["team_id"], "is_manager": user["role"] in ("manager", "leader")}).scalar()
    if not allowed:
        raise HTTPException(status_code=404, detail="Validation run not found.")


def save_analysis(user_id: str, team_id: str, filename: str, analysis_type: str, result: dict) -> str:
    analysis_id = str(uuid.uuid4())
    if analysis_type == "vector":
        total_errors = int(result.get("validation", {}).get("total_errors", 0))
    else:
        total_errors = len(result.get("issues", []))
    engine = database_engine()
    with engine.begin() as connection:
        ensure_app_tables(connection)
        connection.execute(text("""
            INSERT INTO public.saved_analyses (
                analysis_id, user_id, team_id, filename, analysis_type, status,
                compliance_score, total_errors, result_payload
            ) VALUES (
                :analysis_id, :user_id, :team_id, :filename, :analysis_type, :status,
                :compliance_score, :total_errors, CAST(:result_payload AS JSONB)
            )
        """), {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "team_id": team_id,
            "filename": filename,
            "analysis_type": analysis_type,
            "status": result.get("status", "completed"),
            "compliance_score": result.get("compliance_score"),
            "total_errors": total_errors,
            "result_payload": __import__("json").dumps(result, ensure_ascii=False, default=str),
        })
    return analysis_id
