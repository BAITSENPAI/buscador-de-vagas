import httpx
from typing import List, Dict, Any
from .base import strip_html, canonical_url, generate_job_hash

async def fetch_remotive_jobs(search_terms: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    seen_urls = set()
    
    headers = {
        "User-Agent": "JobSearchAgent/1.0 (Local Desktop App)"
    }

    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        for term in search_terms:
            if not term.strip():
                continue
            try:
                url = f"https://remotive.com/api/remote-jobs?search={term.strip()}"
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                raw_jobs = data.get("jobs", [])
                
                for r in raw_jobs:
                    title = r.get("title", "")
                    company = r.get("company_name", "Empresa não identificada")
                    app_url = canonical_url(r.get("url", ""))
                    if not title or not app_url or app_url in seen_urls:
                        continue
                    seen_urls.add(app_url)

                    description = strip_html(r.get("description", ""))
                    location = r.get("candidate_required_location") or "Mundo / Remoto"

                    job = {
                        "source": "remotive",
                        "external_id": str(r.get("id")),
                        "company_name": company,
                        "company_country": None,
                        "title": title,
                        "location": location,
                        "remote_type": "remote",
                        "description": description,
                        "application_url": app_url,
                        "employment_type": r.get("job_type"),
                        "salary_min": None,
                        "salary_max": None,
                        "salary_currency": None,
                        "salary_period": None,
                        "salary_disclosed": 0,
                        "published_at": r.get("publication_date"),
                        "content_hash": generate_job_hash(company, title, description)
                    }
                    jobs.append(job)
            except Exception as e:
                print(f"[Remotive] Erro ao buscar '{term}': {e}")
                continue

    return jobs
