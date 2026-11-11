import httpx
from typing import List, Dict, Any
from .base import strip_html, canonical_url, generate_job_hash

async def fetch_greenhouse_jobs(companies: List[Dict[str, Any]], search_terms: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    headers = {"User-Agent": "JobSearchAgent/1.0"}

    # Cria regex ou lista de termos em minúsculo
    normalized_terms = [t.strip().lower() for t in search_terms if t.strip()]
    if not normalized_terms:
        return []

    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        for comp in companies:
            token = comp.get("greenhouse_board_token")
            if not token:
                continue
            try:
                url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                raw_jobs = data.get("jobs", [])

                for r in raw_jobs:
                    title = r.get("title", "")
                    title_lower = title.lower()
                    
                    # Verifica se o título da vaga bate com algum dos termos de busca
                    matches_term = any(term in title_lower for term in normalized_terms)
                    if not matches_term:
                        continue

                    app_url = canonical_url(r.get("absolute_url", ""))
                    if not app_url:
                        continue

                    description = strip_html(r.get("content", ""))
                    location_info = r.get("location", {})
                    location_name = location_info.get("name", "Brasil") if isinstance(location_info, dict) else "Brasil"
                    company_name = comp.get("name") or token

                    job = {
                        "source": "greenhouse",
                        "external_id": str(r.get("id")),
                        "company_name": company_name,
                        "company_country": comp.get("country_code", "BR"),
                        "title": title,
                        "location": location_name,
                        "remote_type": "remote" if "remote" in location_name.lower() or "remoto" in location_name.lower() else None,
                        "description": description,
                        "application_url": app_url,
                        "employment_type": None,
                        "salary_min": None,
                        "salary_max": None,
                        "salary_currency": None,
                        "salary_period": None,
                        "salary_disclosed": 0,
                        "published_at": r.get("updated_at"),
                        "content_hash": generate_job_hash(company_name, title, description)
                    }
                    jobs.append(job)
            except Exception as e:
                print(f"[Greenhouse] Erro ao buscar empresa '{token}': {e}")
                continue

    return jobs
