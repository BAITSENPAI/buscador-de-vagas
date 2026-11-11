import httpx
from typing import List, Dict, Any
from .base import strip_html, canonical_url, generate_job_hash

async def fetch_remoteok_jobs(search_terms: List[str]) -> List[Dict[str, Any]]:
    """
    Coleta vagas remotas públicas do RemoteOK.
    """
    url = "https://remoteok.com/api"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    normalized_terms = [t.strip().lower() for t in search_terms if t.strip()]
    if not normalized_terms:
        return []

    jobs = []
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            
            raw_data = resp.json()
            # O primeiro elemento costuma ser um aviso legal / metadata
            if isinstance(raw_data, list):
                postings = [p for p in raw_data if isinstance(p, dict) and p.get("id")]
            else:
                postings = []

            for p in postings:
                position = p.get("position", "")
                tags = p.get("tags", [])
                tags_str = " ".join(tags).lower() if isinstance(tags, list) else ""
                combined_text = f"{position} {tags_str}".lower()

                # Verifica se atende a algum dos termos de busca
                if not any(term in combined_text for term in normalized_terms):
                    continue

                app_url = canonical_url(p.get("url", ""))
                if not app_url:
                    continue

                desc = strip_html(p.get("description", ""))
                salary_min = p.get("salary_min")
                salary_max = p.get("salary_max")
                location = p.get("location") or "Remote (Worldwide)"

                job = {
                    "source": "remoteok",
                    "external_id": str(p.get("id")),
                    "company_name": p.get("company", "Empresa Confidencial"),
                    "company_country": "US",
                    "title": position,
                    "location": location,
                    "remote_type": "remote",
                    "description": desc[:6000],
                    "application_url": app_url,
                    "employment_type": "Full-Time",
                    "salary_min": float(salary_min) if salary_min else None,
                    "salary_max": float(salary_max) if salary_max else None,
                    "salary_currency": "USD" if (salary_min or salary_max) else None,
                    "salary_period": "year" if (salary_min or salary_max) else None,
                    "salary_disclosed": 1 if (salary_min or salary_max) else 0,
                    "published_at": p.get("date"),
                    "content_hash": generate_job_hash(p.get("company", ""), position, desc)
                }
                jobs.append(job)

    except Exception as e:
        print(f"Erro ao buscar RemoteOK: {e}")

    return jobs
