import json
import sqlite3
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from ..database import get_connection
from ..sources.remotive import fetch_remotive_jobs
from ..sources.jobicy import fetch_jobicy_jobs
from ..sources.remoteok import fetch_remoteok_jobs
from ..sources.weworkremotely import fetch_weworkremotely_jobs
from ..sources.adzuna import fetch_adzuna_jobs
from ..sources.greenhouse import fetch_greenhouse_jobs
from ..sources.lever import fetch_lever_jobs
from .ai_service import AIService

SYNONYMS_MAP = {
    "desenvolvedor": ["developer", "software engineer", "frontend", "backend", "fullstack", "engenheiro de software", "programador", "engenheiro"],
    "dev": ["developer", "software engineer", "frontend", "backend", "fullstack"],
    "designer": ["product designer", "ux designer", "ui designer", "ui/ux", "web designer", "ux", "design"],
    "dados": ["data analyst", "data engineer", "data scientist", "analista de dados", "cientista de dados", "analytics"],
    "produto": ["product manager", "product owner", "gerente de produto", "pm", "po"],
    "marketing": ["growth", "social media", "content", "copywriter", "marketing digital", "analista de marketing"],
    "vendas": ["sales", "sdr", "bdr", "account executive", "comercial", "executivo de contas"],
    "rh": ["recrutador", "tech recruiter", "recursos humanos", "people"],
    "financeiro": ["analista financeiro", "financial analyst", "finanças", "controladoria"]
}

class JobSearchService:
    @staticmethod
    def expand_search_terms(terms: List[str]) -> List[str]:
        expanded = set()
        for t in terms:
            t_clean = t.strip()
            if not t_clean:
                continue
            expanded.add(t_clean)
            t_lower = t_clean.lower()
            
            # Adiciona sinônimos conhecidos
            for key, syns in SYNONYMS_MAP.items():
                if key in t_lower:
                    for s in syns:
                        expanded.add(s)
        return list(expanded)

    @staticmethod
    def prefilter_job(job: Dict[str, Any], negative_keywords: List[str], work_modes: List[str]) -> bool:
        title_lower = (job.get("title") or "").lower()
        desc_lower = (job.get("description") or "").lower()
        full_text = f"{title_lower} {desc_lower}"

        # Palavras-chave negativas
        for neg in negative_keywords:
            if neg.strip() and neg.strip().lower() in title_lower:
                return False

        # Se o usuário marcou APENAS remoto
        if "remote" in work_modes and len(work_modes) == 1:
            if "presencial obrigatório" in full_text or "must be on-site" in full_text or "100% presencial" in full_text:
                return False

        return True

    @classmethod
    async def run_search(cls, profile_id: int) -> Dict[str, Any]:
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Carrega o perfil
        cursor.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,))
        profile_row = cursor.fetchone()
        if not profile_row:
            conn.close()
            raise ValueError(f"Perfil com id {profile_id} não encontrado.")

        profile = dict(profile_row)
        try:
            target_roles = json.loads(profile.get("target_roles") or "[]")
        except Exception:
            target_roles = ["Desenvolvedor"]

        try:
            negative_keywords = json.loads(profile.get("negative_keywords") or "[]")
        except Exception:
            negative_keywords = []

        try:
            work_modes = json.loads(profile.get("work_modes") or "[]")
        except Exception:
            work_modes = ["remote"]

        expanded_terms = cls.expand_search_terms(target_roles)

        # Carrega catálogo de empresas para Greenhouse/Lever
        cursor.execute("SELECT * FROM companies WHERE is_active = 1")
        companies = [dict(r) for r in cursor.fetchall()]

        # Registra o início do run
        cursor.execute("""
            INSERT INTO search_runs (profile_id, started_at, status)
            VALUES (?, datetime('now', 'localtime'), 'running')
        """, (profile_id,))
        run_id = cursor.lastrowid
        conn.commit()

        # 2. Executa coletas assíncronas em paralelo
        tasks = [
            fetch_remotive_jobs(expanded_terms),
            fetch_jobicy_jobs(expanded_terms),
            fetch_remoteok_jobs(expanded_terms),
            fetch_weworkremotely_jobs(expanded_terms),
            fetch_greenhouse_jobs(companies, expanded_terms),
            fetch_lever_jobs(companies, expanded_terms),
        ]
        if profile.get("adzuna_app_id") and profile.get("adzuna_app_key"):
            tasks.append(fetch_adzuna_jobs(expanded_terms, profile["adzuna_app_id"], profile["adzuna_app_key"]))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_collected_jobs: List[Dict[str, Any]] = []
        errors = []
        for res in results:
            if isinstance(res, Exception):
                errors.append(str(res))
            elif isinstance(res, list):
                all_collected_jobs.extend(res)

        jobs_found_count = len(all_collected_jobs)
        jobs_new_count = 0
        jobs_qualified_count = 0

        # 3. Pré-filtragem e persistência no banco global
        candidate_jobs_to_evaluate = []

        for j in all_collected_jobs:
            if not cls.prefilter_job(j, negative_keywords, work_modes):
                continue

            content_hash = j.get("content_hash")
            cursor.execute("SELECT id FROM jobs WHERE content_hash = ?", (content_hash,))
            existing_job = cursor.fetchone()

            job_id = None
            # Garante que campos que podem vir como lista da API sejam convertidos em string
            emp_type = j.get("employment_type")
            if isinstance(emp_type, list):
                emp_type = ", ".join(str(x) for x in emp_type)
            elif emp_type is not None:
                emp_type = str(emp_type)

            loc = j.get("location")
            if isinstance(loc, list):
                loc = ", ".join(str(x) for x in loc)
            elif loc is not None:
                loc = str(loc)

            if existing_job:
                job_id = existing_job["id"]
                cursor.execute("UPDATE jobs SET updated_at = datetime('now', 'localtime') WHERE id = ?", (job_id,))
            else:
                cursor.execute("""
                    INSERT INTO jobs (
                        source, external_id, company_name, company_country,
                        title, location, remote_type, description, application_url,
                        employment_type, salary_min, salary_max, salary_currency,
                        salary_period, salary_disclosed, published_at, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    j["source"], j["external_id"], j["company_name"], j["company_country"],
                    j["title"], loc, j["remote_type"], j["description"], j["application_url"],
                    emp_type, j["salary_min"], j["salary_max"], j["salary_currency"],
                    j["salary_period"], j["salary_disclosed"], j["published_at"], j["content_hash"]
                ))
                job_id = cursor.lastrowid
                jobs_new_count += 1

            # Garante que a vaga SEMPRE tenha uma entrada na tabela de avaliações para aparecer no feed
            cursor.execute("""
                SELECT id, score, reasoning FROM job_evaluations 
                WHERE job_id = ? AND profile_id = ?
            """, (job_id, profile_id))
            existing_eval = cursor.fetchone()

            needs_eval = False
            if not existing_eval:
                needs_eval = True
                cursor.execute("""
                    INSERT INTO job_evaluations (
                        job_id, profile_id, score, seniority, technical_score,
                        experience_score, compensation_score, remote_score,
                        qualified, status, positives, concerns, reasoning, hard_gate_reason
                    ) VALUES (?, ?, 50, 'Aguardando', 50, 50, 50, 50, 1, 'nova', '[]', '[]',
                              'Vaga capturada por título compatível. Clique para analisar com IA.', NULL)
                """, (job_id, profile_id))
            elif "aguardando" in (existing_eval["reasoning"] or "").lower() or "clique para analisar" in (existing_eval["reasoning"] or "").lower() or existing_eval["score"] == 50:
                needs_eval = True

            if needs_eval:
                j_eval = dict(j)
                j_eval["id"] = job_id
                candidate_jobs_to_evaluate.append(j_eval)

        conn.commit()

        # Resgata também até 10 vagas pendentes já existentes no banco
        cursor.execute("""
            SELECT j.id, j.title, j.company_name, j.location, j.remote_type, j.description,
                   j.application_url, j.salary_min, j.salary_max, j.salary_currency, j.salary_period
            FROM jobs j
            JOIN job_evaluations e ON e.job_id = j.id AND e.profile_id = ?
            WHERE e.reasoning LIKE '%aguardando%' OR e.reasoning LIKE '%clique para analisar%' OR e.score = 50
            LIMIT 15
        """, (profile_id,))
        pending_reval = [dict(r) for r in cursor.fetchall()]
        for pj in pending_reval:
            if not any(c["id"] == pj["id"] for c in candidate_jobs_to_evaluate):
                candidate_jobs_to_evaluate.append(pj)

        # 4. Avaliação com IA em paralelo rápido (semáforo de 3 requisições simultâneas)
        jobs_to_eval = candidate_jobs_to_evaluate[:12]
        sem = asyncio.Semaphore(3)

        async def evaluate_single(j_item):
            async with sem:
                try:
                    ev = await AIService.evaluate_job(profile, j_item)
                    return (j_item, ev, None)
                except Exception as ex:
                    return (j_item, None, str(ex))

        if jobs_to_eval:
            eval_results = await asyncio.gather(*(evaluate_single(item) for item in jobs_to_eval))
            for j_item, evaluation, err in eval_results:
                if err:
                    errors.append(f"Erro ao avaliar vaga '{j_item.get('title')}': {err}")
                    continue
                if not evaluation:
                    continue

                qualified = 1 if evaluation.get("qualified") else 0
                if qualified:
                    jobs_qualified_count += 1

                cursor.execute("""
                    INSERT INTO job_evaluations (
                        job_id, profile_id, score, seniority, technical_score,
                        experience_score, compensation_score, remote_score,
                        qualified, status, positives, concerns, reasoning, hard_gate_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'nova', ?, ?, ?, ?)
                    ON CONFLICT(job_id, profile_id) DO UPDATE SET
                        score = excluded.score,
                        seniority = excluded.seniority,
                        technical_score = excluded.technical_score,
                        experience_score = excluded.experience_score,
                        compensation_score = excluded.compensation_score,
                        remote_score = excluded.remote_score,
                        qualified = excluded.qualified,
                        positives = excluded.positives,
                        concerns = excluded.concerns,
                        reasoning = excluded.reasoning,
                        hard_gate_reason = excluded.hard_gate_reason,
                        evaluated_at = datetime('now', 'localtime')
                """, (
                    j_item["id"], profile_id, evaluation.get("score", 0), evaluation.get("seniority", "N/A"),
                    evaluation.get("technical_score", 0), evaluation.get("experience_score", 0),
                    evaluation.get("compensation_score", 0), evaluation.get("remote_score", 0),
                    qualified, json.dumps(evaluation.get("positives", []), ensure_ascii=False),
                    json.dumps(evaluation.get("concerns", []), ensure_ascii=False),
                    evaluation.get("reasoning", ""), evaluation.get("hard_gate_reason")
                ))
            conn.commit()

        # 5. Finaliza o registro do run
        cursor.execute("""
            UPDATE search_runs
            SET finished_at = datetime('now', 'localtime'),
                jobs_found = ?,
                jobs_new = ?,
                jobs_qualified = ?,
                errors = ?,
                status = 'completed'
            WHERE id = ?
        """, (jobs_found_count, jobs_new_count, jobs_qualified_count, json.dumps(errors), run_id))
        conn.commit()
        conn.close()
        conn.close()

        return {
            "run_id": run_id,
            "jobs_found": jobs_found_count,
            "jobs_new": jobs_new_count,
            "jobs_qualified": jobs_qualified_count,
            "evaluated_count": len(jobs_to_eval),
            "errors": errors
        }
