import httpx
from typing import List, Dict, Any
from .base import strip_html, canonical_url, generate_job_hash

async def fetch_adzuna_jobs(search_terms: List[str], app_id: str, app_key: str) -> List[Dict[str, Any]]:
    if not app_id or not app_key:
        return []
        
    jobs = []
    seen_urls = set()

    async with httpx.AsyncClient(timeout=15.0) as client:
        for term in search_terms:
            if not term.strip():
                continue
            try:
                url = "https://api.adzuna.com/v1/api/jobs/br/search/1"
                params = {
                    "app_id": app_id.strip(),
                    "app_key": app_key.strip(),
                    "what": term.strip(),
                    "where": "Brasil",
                    "results_per_page": 30,
                    "content-type": "application/json"
                }
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                results = data.get("results", [])

                for r in results:
                    title = r.get("title", "")
                    company_data = r.get("company", {})
                    company = company_data.get("display_name", "Empresa não identificada") if isinstance(company_data, dict) else "Empresa não identificada"
                    app_url = canonical_url(r.get("redirect_url", ""))
                    if not title or not app_url or app_url in seen_urls:
                        continue
                    seen_urls.add(app_url)

                    description = strip_html(r.get("description", ""))
                    location_data = r.get("location", {})
                    location = location_data.get("display_name", "Brasil") if isinstance(location_data, dict) else "Brasil"

                    sal_min = r.get("salary_min")
                    sal_max = r.get("salary_max")
                    has_salary = 1 if (sal_min is not None or sal_max is not None) else 0

                    job = {
                        "source": "adzuna",
                        "external_id": str(r.get("id")),
                        "company_name": company,
                        "company_country": "BR",
                        "title": title,
                        "location": location,
                        "remote_type": None, # Será inferido ou avaliado pela IA
                        "description": description,
                        "application_url": app_url,
                        "employment_type": r.get("contract_type"),
                        "salary_min": sal_min,
                        "salary_max": sal_max,
                        "salary_currency": "BRL",
                        "salary_period": "year", # Adzuna costuma retornar anual no BR
                        "salary_disclosed": has_salary,
                        "published_at": r.get("created"),
                        "content_hash": generate_job_hash(company, title, description)
                    }
                    jobs.append(job)
            except Exception as e:
                print(f"[Adzuna] Erro ao buscar '{term}': {e}")
                continue

    return jobs
