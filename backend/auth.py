import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends
from .database import get_connection

INVITE_CODE = os.getenv("INVITE_CODE", "vagas2025")

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, key_hex = stored_hash.split("$", 1)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False

def create_session(profile_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            token TEXT PRIMARY KEY,
            profile_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    cursor.execute("INSERT INTO user_sessions (token, profile_id) VALUES (?, ?)", (token, profile_id))
    conn.commit()
    conn.close()
    return token

def delete_session(token: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def get_current_profile(request: Request) -> Dict[str, Any]:
    # 1. Verifica token nos cookies ou headers
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "").strip()

    conn = get_connection()
    cursor = conn.cursor()

    # Cria tabela de sessões caso não exista
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            token TEXT PRIMARY KEY,
            profile_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.commit()

    # Se houver token válido, resgata o perfil correspondente
    if token:
        cursor.execute("""
            SELECT p.* FROM profiles p
            JOIN user_sessions s ON s.profile_id = p.id
            WHERE s.token = ?
        """, (token,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)

    # Se estiver rodando sem autenticação obrigatória (modo local sem senhas criadas ainda)
    cursor.execute("SELECT COUNT(*) as count FROM profiles WHERE password_hash IS NOT NULL AND password_hash != ''")
    has_passwords = cursor.fetchone()["count"] > 0

    if not has_passwords:
        # Modo local inicial sem senha: usa o primeiro perfil existente
        cursor.execute("SELECT * FROM profiles ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)

    conn.close()
    raise HTTPException(status_code=401, detail="Não autenticado. Faça login para continuar.")
