import httpx
from typing import List, Dict, Any
from .base import strip_html, canonical_url, generate_job_hash

async def fetch_lever_jobs(companies: List[Dict[str, Any]], search_terms: List[str]) -> List[Dict[str, Any]]:
    jobs = []
    headers = {"User-Agent": "JobSearchAgent/1.0"}

    normalized_terms = [t.strip().lower() for t in search_terms if t.strip()]
    if not normalized_terms:
        return []

    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        for comp in companies:
            site = comp.get("lever_site")
            if not site:
                continue
            try:
                url = f"https://api.lever.co/v0/postings/{site}?mode=json"
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                raw_postings = resp.json()

                for r in raw_postings:
                    title = r.get("text", "")
                    title_lower = title.lower()

                    matches_term = any(term in title_lower for term in normalized_terms)
                    if not matches_term:
                        continue

                    app_url = canonical_url(r.get("hostedUrl", ""))
                    if not app_url:
                        continue

                    categories = r.get("categories", {})
                    location_name = categories.get("location", "Brasil") if isinstance(categories, dict) else "Brasil"
                    work_place = categories.get("workplaceType", "") if isinstance(categories, dict) else ""
                    commitment = categories.get("commitment", "") if isinstance(categories, dict) else ""

                    description = strip_html(r.get("descriptionPlain", "") or r.get("description", ""))
                    company_name = comp.get("name") or site

                    remote_type = None
                    if "remote" in work_place.lower() or "remote" in location_name.lower() or "remoto" in location_name.lower():
                        remote_type = "remote"

                    job = {
                        "source": "lever",
                        "external_id": str(r.get("id")),
                        "company_name": company_name,
                        "company_country": comp.get("country_code", "BR"),
                        "title": title,
                        "location": location_name,
                        "remote_type": remote_type,
                        "description": description,
                        "application_url": app_url,
                        "employment_type": commitment,
                        "salary_min": None,
                        "salary_max": None,
                        "salary_currency": None,
                        "salary_period": None,
                        "salary_disclosed": 0,
                        "published_at": None,
                        "content_hash": generate_job_hash(company_name, title, description)
                    }
                    jobs.append(job)
            except Exception as e:
                print(f"[Lever] Erro ao buscar empresa '{site}': {e}")
                continue

    return jobs
