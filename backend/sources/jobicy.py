import httpx
from typing import List, Dict, Any
from .base import strip_html, canonical_url, generate_job_hash

async def fetch_jobicy_jobs(search_terms: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    seen_urls = set()
    normalized_terms = [t.strip().lower() for t in search_terms if t.strip()]
    if not normalized_terms:
        return []

    headers = {"User-Agent": "JobSearchAgent/1.0"}

    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        try:
            url = "https://jobicy.com/api/v2/remote-jobs?count=50"
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            raw_jobs = resp.json().get("jobs", [])

            for r in raw_jobs:
                title = r.get("jobTitle", "")
                title_lower = title.lower()

                # Verifica se o título da vaga bate com algum dos termos de busca
                matches_term = any(term in title_lower for term in normalized_terms)
                if not matches_term:
                    continue

                app_url = canonical_url(r.get("url", ""))
                if not app_url or app_url in seen_urls:
                    continue
                seen_urls.add(app_url)

                company = r.get("companyName", "Empresa não identificada")
                description = strip_html(r.get("jobDescription", ""))
                location = r.get("jobGeo", "Global / Remoto")

                sal_min = None
                sal_max = None
                try:
                    if r.get("annualSalaryMin"):
                        sal_min = float(r.get("annualSalaryMin"))
                    if r.get("annualSalaryMax"):
                        sal_max = float(r.get("annualSalaryMax"))
                except Exception:
                    pass

                job = {
                    "source": "jobicy",
                    "external_id": str(r.get("id")),
                    "company_name": company,
                    "company_country": None,
                    "title": title,
                    "location": location,
                    "remote_type": "remote",
                    "description": description,
                    "application_url": app_url,
                    "employment_type": r.get("jobType"),
                    "salary_min": sal_min,
                    "salary_max": sal_max,
                    "salary_currency": r.get("salaryCurrency"),
                    "salary_period": "year",
                    "salary_disclosed": 1 if sal_min or sal_max else 0,
                    "published_at": r.get("pubDate"),
                    "content_hash": generate_job_hash(company, title, description)
                }
                jobs.append(job)
        except Exception as e:
            print(f"[Jobicy] Erro: {e}")

    return jobs
