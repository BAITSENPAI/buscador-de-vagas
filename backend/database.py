import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

import sys

DB_PATH = os.environ.get("VAGAS_DB_PATH")
if not DB_PATH:
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parent.parent
    data_dir = app_dir / "data"
    data_dir.mkdir(exist_ok=True)
    DB_PATH = str(data_dir / "vagas.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Perfil do candidato / configurações
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL DEFAULT '',
        email TEXT,
        resume_text TEXT DEFAULT '',
        target_roles TEXT DEFAULT '[]',
        negative_keywords TEXT DEFAULT '[]',
        min_salary REAL DEFAULT 0,
        employment_types TEXT DEFAULT '["CLT", "PJ"]',
        work_modes TEXT DEFAULT '["remote"]',
        preferred_location TEXT DEFAULT '',
        company_country TEXT DEFAULT 'BR',
        ai_provider TEXT DEFAULT 'gemini',
        ai_api_key TEXT DEFAULT '',
        ai_model TEXT DEFAULT 'gemini-3.8-flash',
        adzuna_app_id TEXT DEFAULT '',
        adzuna_app_key TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """)

    # Empresas catalogadas com boards públicos conhecidos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        country_code TEXT DEFAULT 'BR',
        greenhouse_board_token TEXT,
        lever_site TEXT,
        website TEXT,
        is_active INTEGER DEFAULT 1,
        last_checked_at TEXT,
        created_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """)

    # Vagas globais (catálogo desduplicado)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        external_id TEXT,
        company_name TEXT NOT NULL,
        company_country TEXT,
        title TEXT NOT NULL,
        location TEXT,
        remote_type TEXT,
        description TEXT,
        application_url TEXT NOT NULL,
        employment_type TEXT,
        salary_min REAL,
        salary_max REAL,
        salary_currency TEXT,
        salary_period TEXT,
        salary_disclosed INTEGER DEFAULT 0,
        published_at TEXT,
        content_hash TEXT UNIQUE,
        created_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
    """)

    # Avaliação da vaga contra o perfil
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
        score INTEGER NOT NULL,
        seniority TEXT,
        technical_score INTEGER DEFAULT 0,
        experience_score INTEGER DEFAULT 0,
        compensation_score INTEGER DEFAULT 0,
        remote_score INTEGER DEFAULT 0,
        qualified INTEGER DEFAULT 0,
        status TEXT DEFAULT 'nova', -- 'nova', 'favorita', 'candidatado', 'descartada'
        positives TEXT DEFAULT '[]',
        concerns TEXT DEFAULT '[]',
        reasoning TEXT,
        hard_gate_reason TEXT,
        evaluated_at TEXT DEFAULT (datetime('now', 'localtime')),
        UNIQUE(job_id, profile_id)
    )
    """)

    # Histórico de buscas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER,
        started_at TEXT DEFAULT (datetime('now', 'localtime')),
        finished_at TEXT,
        jobs_found INTEGER DEFAULT 0,
        jobs_new INTEGER DEFAULT 0,
        jobs_qualified INTEGER DEFAULT 0,
        errors TEXT DEFAULT '[]',
        status TEXT DEFAULT 'running'
    )
    """)

    # Migrações seguras de colunas em profiles
    cursor.execute("PRAGMA table_info(profiles)")
    existing_cols = [r[1] for r in cursor.fetchall()]
    if "username" not in existing_cols:
        cursor.execute("ALTER TABLE profiles ADD COLUMN username TEXT")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_username ON profiles(username)")
    if "password_hash" not in existing_cols:
        cursor.execute("ALTER TABLE profiles ADD COLUMN password_hash TEXT")

    # Inserir perfil inicial padrão se não existir nenhum
    cursor.execute("SELECT COUNT(*) as count FROM profiles")
    if cursor.fetchone()["count"] == 0:
        cursor.execute("""
        INSERT INTO profiles (name, target_roles, employment_types, work_modes, min_salary, ai_provider, ai_model)
        VALUES ('Meu Perfil', '["Desenvolvedor", "Designer"]', '["CLT", "PJ"]', '["remote"]', 0, 'gemini', 'gemini-3.8-flash')
        """)
    else:
        # Migração automática de modelos descontinuados
        cursor.execute("""
        UPDATE profiles
        SET ai_model = 'gemini-3.8-flash'
        WHERE ai_model IN ('gemini-2.5-flash', 'gemini-1.5-flash') OR ai_model IS NULL
        """)
        cursor.execute("""
        UPDATE profiles
        SET ai_model = 'gemini-3.8-pro'
        WHERE ai_model IN ('gemini-2.5-pro', 'gemini-1.5-pro')
        """)

    # Inserir ou atualizar catálogo de empresas com board público ativo
    initial_companies = [
        ("Stone", "BR", "stone", None, "https://stone.co"),
        ("QuintoAndar", "BR", "quintoandar", None, "https://quintoandar.com.br"),
        ("Wellhub (Gympass)", "BR", "gympass", None, "https://wellhub.com"),
        ("VTEX", "BR", "vtex", None, "https://vtex.com"),
        ("RD Station", "BR", "rdstation", None, "https://rdstation.com"),
        ("Nubank", "BR", "nubank", None, "https://nubank.com.br"),
        ("Creditas", "BR", "creditas", None, "https://creditas.com"),
        ("Pipefy", "BR", "pipefy", None, "https://pipefy.com"),
        ("Loft", "BR", "loft", None, "https://loft.com.br"),
        ("PicPay", "BR", "picpay", None, "https://picpay.com"),
        ("EBANX", "BR", "ebanx", None, "https://ebanx.com"),
        ("Brex", "US", "brex", None, "https://brex.com"),
        ("Wildlife Studios", "BR", "wildlifestudios", None, "https://wildlifestudios.com")
    ]
    for comp in initial_companies:
        cursor.execute("SELECT id FROM companies WHERE name = ?", (comp[0],))
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO companies (name, country_code, greenhouse_board_token, lever_site, website)
            VALUES (?, ?, ?, ?, ?)
            """, comp)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Banco de dados SQLite inicializado com sucesso!")
