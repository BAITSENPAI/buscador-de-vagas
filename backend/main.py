import os
import json
import webbrowser
import sys
import httpx
from typing import Dict, Any, Optional, List
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Request, Response, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import get_connection, init_db
from .services.ai_service import AIService
from .services.resume_parser import extract_text_from_pdf
from .services.job_search_service import JobSearchService
from .auth import hash_password, verify_password, create_session, delete_session, get_current_profile, INVITE_CODE

init_db()

app = FastAPI(title="Buscador de Vagas com IA", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_DIR = BASE_DIR / "frontend"

# Modelos Pydantic para validação
class ProfileUpdate(BaseModel):
    name: str
    email: Optional[str] = None
    resume_text: Optional[str] = ""
    target_roles: List[str] = []
    negative_keywords: List[str] = []
    min_salary: float = 0
    employment_types: List[str] = ["CLT", "PJ"]
    work_modes: List[str] = ["remote"]
    preferred_location: Optional[str] = ""
    company_country: str = "BR"
    ai_provider: str = "gemini"
    ai_api_key: Optional[str] = ""
    ai_model: Optional[str] = "gemini-3.8-flash"
    adzuna_app_id: Optional[str] = ""
    adzuna_app_key: Optional[str] = ""

class TestAIRequest(BaseModel):
    provider: str
    api_key: str
    model: Optional[str] = None

class JobStatusUpdate(BaseModel):
    status: str # 'nova', 'favorita', 'candidatado', 'descartada'

class CompanyCreate(BaseModel):
    name: str
    country_code: str = "BR"
    greenhouse_board_token: Optional[str] = None
    lever_site: Optional[str] = None
    website: Optional[str] = None

class RegisterRequest(BaseModel):
    name: str
    username: str
    password: str
    invite_code: str
    email: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# Rotas de Autenticação
@app.post("/api/auth/register")
def register_user(req: RegisterRequest, response: Response):
    expected_code = os.getenv("INVITE_CODE", "vagas2025").strip()
    if req.invite_code.strip() != expected_code:
        raise HTTPException(status_code=400, detail="Código de convite inválido.")

    username = req.username.strip().lower()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="O nome de usuário deve ter pelo menos 3 caracteres.")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 4 caracteres.")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM profiles WHERE LOWER(username) = ?", (username,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Este nome de usuário já está em uso.")

    pwd_hash = hash_password(req.password)
    cursor.execute("""
        INSERT INTO profiles (
            name, username, email, password_hash, target_roles, employment_types, work_modes, min_salary, ai_provider, ai_model
        ) VALUES (?, ?, ?, ?, '["Designer", "Desenvolvedor"]', '["CLT", "PJ"]', '["remote"]', 0, 'gemini', 'gemini-3.8-flash')
    """, (req.name.strip(), username, req.email, pwd_hash))
    profile_id = cursor.lastrowid
    conn.commit()
    conn.close()

    token = create_session(profile_id)
    response.set_cookie(key="session_token", value=token, max_age=30*86400, httponly=True, samesite="lax")
    return {"success": True, "token": token, "name": req.name.strip(), "username": username}

@app.post("/api/auth/login")
def login_user(req: LoginRequest, response: Response):
    username = req.username.strip().lower()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profiles WHERE LOWER(username) = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row["password_hash"] or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos.")

    profile_id = row["id"]
    token = create_session(profile_id)
    response.set_cookie(key="session_token", value=token, max_age=30*86400, httponly=True, samesite="lax")
    return {"success": True, "token": token, "name": row["name"], "username": row["username"]}

@app.get("/api/auth/me")
def get_auth_me(current_profile: Dict[str, Any] = Depends(get_current_profile)):
    p = dict(current_profile)
    p["target_roles"] = json.loads(p.get("target_roles") or "[]")
    p["negative_keywords"] = json.loads(p.get("negative_keywords") or "[]")
    p["employment_types"] = json.loads(p.get("employment_types") or "[]")
    p["work_modes"] = json.loads(p.get("work_modes") or "[]")
    p.pop("password_hash", None)
    return p

@app.post("/api/auth/logout")
def logout_user(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        delete_session(token)
    response.delete_cookie("session_token")
    return {"success": True}

# Rotas de Perfil
@app.get("/api/profile")
def get_profile(current_profile: Dict[str, Any] = Depends(get_current_profile)):
    p = dict(current_profile)
    p["target_roles"] = json.loads(p.get("target_roles") or "[]")
    p["negative_keywords"] = json.loads(p.get("negative_keywords") or "[]")
    p["employment_types"] = json.loads(p.get("employment_types") or "[]")
    p["work_modes"] = json.loads(p.get("work_modes") or "[]")
    p.pop("password_hash", None)
    return p

@app.post("/api/profile")
def update_profile(data: ProfileUpdate, current_profile: Dict[str, Any] = Depends(get_current_profile)):
    conn = get_connection()
    cursor = conn.cursor()
    profile_id = current_profile["id"]

    target_roles_json = json.dumps(data.target_roles, ensure_ascii=False)
    negative_keywords_json = json.dumps(data.negative_keywords, ensure_ascii=False)
    employment_types_json = json.dumps(data.employment_types, ensure_ascii=False)
    work_modes_json = json.dumps(data.work_modes, ensure_ascii=False)

    cursor.execute("""
        UPDATE profiles SET
            name = ?, email = ?, resume_text = ?, target_roles = ?,
            negative_keywords = ?, min_salary = ?, employment_types = ?,
            work_modes = ?, preferred_location = ?, company_country = ?,
            ai_provider = ?, ai_api_key = ?, ai_model = ?,
            adzuna_app_id = ?, adzuna_app_key = ?,
            updated_at = datetime('now', 'localtime')
        WHERE id = ?
    """, (
        data.name, data.email, data.resume_text, target_roles_json,
        negative_keywords_json, data.min_salary, employment_types_json,
        work_modes_json, data.preferred_location, data.company_country,
        data.ai_provider, data.ai_api_key, data.ai_model,
        data.adzuna_app_id, data.adzuna_app_key, profile_id
    ))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Perfil salvo com sucesso!"}

@app.post("/api/profile/upload-resume")
async def upload_resume(file: UploadFile = File(...), current_profile: Dict[str, Any] = Depends(get_current_profile)):
    content = await file.read()
    filename = file.filename.lower()
    
    if filename.endswith(".pdf"):
        try:
            text = extract_text_from_pdf(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif filename.endswith(".txt"):
        try:
            text = content.decode("utf-8", errors="ignore")
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Formato não suportado. Envie um arquivo PDF ou TXT.")

    return {"text": text}

@app.post("/api/profile/autocomplete-with-ai")
async def autocomplete_with_ai(data: Dict[str, Any], current_profile: Dict[str, Any] = Depends(get_current_profile)):
    resume_text = data.get("resume_text", "")
    provider = data.get("provider", "gemini")
    api_key = data.get("api_key", "")
    model = data.get("model")

    if not resume_text:
        raise HTTPException(status_code=400, detail="Envie o texto do currículo.")
    if not api_key:
        raise HTTPException(status_code=400, detail="Informe a chave de IA para extrair dados do currículo.")

    try:
        extracted = await AIService.extract_profile_from_resume(resume_text, provider, api_key, model)
        return extracted
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao analisar currículo com IA: {str(e)}")

# Teste de Conexão com IA
@app.post("/api/ai/test")
async def test_ai_connection(req: TestAIRequest):
    res = await AIService.test_connection(req.provider, req.api_key, req.model)
    return res

@app.post("/api/ai/diagnose")
async def diagnose_ai(req: TestAIRequest):
    key = AIService.clean_api_key(req.api_key)
    if not key:
        return {"error": "Chave não informada."}

    results = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. ListModels
        try:
            r1 = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                headers={"x-goog-api-key": key}
            )
            if r1.status_code == 200:
                all_models = [m.get("name", "").replace("models/", "") for m in r1.json().get("models", [])]
                flash_models = [m for m in all_models if "flash" in m]
                results["list_models"] = {
                    "status": 200,
                    "success": True,
                    "message": "Chave reconhecida com sucesso!",
                    "available_flash_models": flash_models[:8]
                }
            else:
                results["list_models"] = {
                    "status": r1.status_code,
                    "success": False,
                    "message": r1.text[:300]
                }
        except Exception as e:
            results["list_models"] = {"status": 0, "success": False, "message": str(e)}

        # 2. Interactions API (gemini-3.8-flash)
        try:
            r2 = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": key,
                    "Api-Revision": "2026-05-20"
                },
                json={"model": "gemini-3.8-flash", "input": "OK"}
            )
            results["interactions"] = {
                "status": r2.status_code,
                "success": r2.status_code == 200,
                "message": r2.text[:300]
            }
        except Exception as e:
            results["interactions"] = {"status": 0, "success": False, "message": str(e)}

        # 3. generateContent clássico com modelos liberados na conta
        classic_results = []
        for m in ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview"]:
            try:
                r3 = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                    headers={"Content-Type": "application/json", "x-goog-api-key": key},
                    json={"contents": [{"parts": [{"text": "OK"}]}]}
                )
                classic_results.append({
                    "model": m,
                    "status": r3.status_code,
                    "success": r3.status_code == 200,
                    "message": r3.text[:150]
                })
            except Exception as e:
                classic_results.append({"model": m, "status": 0, "success": False, "message": str(e)})

        results["generate_content"] = classic_results

    return results

# Execução de Busca de Vagas
@app.post("/api/search/run")
async def trigger_search(current_profile: Dict[str, Any] = Depends(get_current_profile)):
    profile_id = current_profile["id"]
    try:
        report = await JobSearchService.run_search(profile_id)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar vagas: {str(e)}")

# Feed de Vagas
@app.get("/api/jobs")
def list_jobs(
    status: Optional[str] = None,
    min_score: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 150,
    current_profile: Dict[str, Any] = Depends(get_current_profile)
):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT 
        e.id as evaluation_id,
        e.score,
        e.seniority,
        e.technical_score,
        e.experience_score,
        e.compensation_score,
        e.remote_score,
        e.qualified,
        e.status as user_status,
        e.positives,
        e.concerns,
        e.reasoning,
        e.hard_gate_reason,
        e.evaluated_at,
        j.id as job_id,
        j.title,
        j.company_name,
        j.location,
        j.remote_type,
        j.employment_type,
        j.salary_min,
        j.salary_max,
        j.salary_currency,
        j.salary_period,
        j.salary_disclosed,
        j.application_url,
        j.source,
        j.published_at,
        j.description
    FROM job_evaluations e
    JOIN jobs j ON j.id = e.job_id
    WHERE e.profile_id = ?
    """
    params = [current_profile["id"]]

    if status and status != 'todas':
        query += " AND e.status = ?"
        params.append(status)

    if min_score is not None:
        query += " AND e.score >= ?"
        params.append(min_score)

    if search:
        query += " AND (j.title LIKE ? OR j.company_name LIKE ? OR j.description LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])

    query += """
    ORDER BY 
        CASE WHEN e.reasoning LIKE '%Aguardando%' OR e.reasoning LIKE '%Clique para analisar%' THEN 1 ELSE 0 END ASC,
        e.score DESC, 
        e.evaluated_at DESC 
    LIMIT ?
    """
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        item = dict(r)
        item["positives"] = json.loads(item.get("positives") or "[]")
        item["concerns"] = json.loads(item.get("concerns") or "[]")
        results.append(item)

    return results

@app.patch("/api/jobs/{evaluation_id}/status")
def update_job_status(evaluation_id: int, data: JobStatusUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE job_evaluations SET status = ? WHERE id = ?", (data.status, evaluation_id))
    conn.commit()
    conn.close()
    return {"success": True, "status": data.status}

@app.post("/api/jobs/{evaluation_id}/evaluate")
async def evaluate_single_job(evaluation_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id as eval_id, e.profile_id, j.* 
        FROM job_evaluations e
        JOIN jobs j ON j.id = e.job_id
        WHERE e.id = ?
    """, (evaluation_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Avaliação não encontrada.")
    
    data = dict(row)
    profile_id = data["profile_id"]
    cursor.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,))
    prof_row = cursor.fetchone()
    if not prof_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    
    profile = dict(prof_row)
    try:
        evaluation = await AIService.evaluate_job(profile, data)
        qualified = 1 if evaluation.get("qualified") else 0
        cursor.execute("""
            UPDATE job_evaluations SET
                score = ?, seniority = ?, technical_score = ?, experience_score = ?,
                compensation_score = ?, remote_score = ?, qualified = ?,
                positives = ?, concerns = ?, reasoning = ?, hard_gate_reason = ?,
                evaluated_at = datetime('now', 'localtime')
            WHERE id = ?
        """, (
            evaluation.get("score", 0), evaluation.get("seniority", "N/A"),
            evaluation.get("technical_score", 0), evaluation.get("experience_score", 0),
            evaluation.get("compensation_score", 0), evaluation.get("remote_score", 0),
            qualified, json.dumps(evaluation.get("positives", []), ensure_ascii=False),
            json.dumps(evaluation.get("concerns", []), ensure_ascii=False),
            evaluation.get("reasoning", ""), evaluation.get("hard_gate_reason"),
            evaluation_id
        ))
        
        cursor.execute("""
            SELECT 
                e.id as evaluation_id, e.score, e.seniority, e.technical_score,
                e.experience_score, e.compensation_score, e.remote_score, e.qualified,
                e.status as user_status, e.positives, e.concerns, e.reasoning,
                e.hard_gate_reason, e.evaluated_at, j.id as job_id, j.title,
                j.company_name, j.location, j.remote_type, j.employment_type,
                j.salary_min, j.salary_max, j.salary_currency, j.salary_period,
                j.salary_disclosed, j.application_url, j.source, j.published_at, j.description
            FROM job_evaluations e
            JOIN jobs j ON j.id = e.job_id
            WHERE e.id = ?
        """, (evaluation_id,))
        updated_row = cursor.fetchone()
        conn.commit()
        conn.close()

        updated_job = dict(updated_row)
        updated_job["positives"] = json.loads(updated_job.get("positives") or "[]")
        updated_job["concerns"] = json.loads(updated_job.get("concerns") or "[]")
        return {"success": True, "job": updated_job}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Erro na avaliação com IA: {str(e)}")

# Estatísticas do Topo
@app.get("/api/stats")
def get_stats(current_profile: Dict[str, Any] = Depends(get_current_profile)):
    conn = get_connection()
    cursor = conn.cursor()
    profile_id = current_profile["id"]

    cursor.execute("SELECT COUNT(*) as total FROM jobs")
    total_jobs = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as count FROM job_evaluations WHERE profile_id = ? AND score >= 70 AND qualified = 1", (profile_id,))
    high_match = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM job_evaluations WHERE profile_id = ? AND status = 'favorita'", (profile_id,))
    favorites = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM job_evaluations WHERE profile_id = ? AND status = 'candidatado'", (profile_id,))
    applied = cursor.fetchone()["count"]

    conn.close()
    return {
        "total_jobs": total_jobs,
        "high_match": high_match,
        "favorites": favorites,
        "applied": applied
    }

# Empresas
@app.get("/api/companies")
def get_companies():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM companies ORDER BY name ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/companies")
def add_company(comp: CompanyCreate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO companies (name, country_code, greenhouse_board_token, lever_site, website)
        VALUES (?, ?, ?, ?, ?)
    """, (comp.name, comp.country_code, comp.greenhouse_board_token, comp.lever_site, comp.website))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Empresa adicionada com sucesso!"}

# Servir Frontend
@app.get("/")
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse({"status": "Frontend em construção"})
    return FileResponse(index_file)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
