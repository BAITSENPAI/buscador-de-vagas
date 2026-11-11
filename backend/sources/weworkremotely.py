import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from .base import strip_html, canonical_url, generate_job_hash

WWR_FEEDS = [
    "https://weworkremotely.com/categories/remote-design-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-product-management-jobs.rss",
]

async def fetch_weworkremotely_jobs(search_terms: List[str]) -> List[Dict[str, Any]]:
    """
    Coleta vagas remotas públicas do WeWorkRemotely via RSS XML.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    normalized_terms = [t.strip().lower() for t in search_terms if t.strip()]
    if not normalized_terms:
        return []

    jobs = []
    seen_urls = set()

    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
            for feed_url in WWR_FEEDS:
                try:
                    resp = await client.get(feed_url)
                    if resp.status_code != 200:
                        continue

                    root = ET.fromstring(resp.text)
                    items = root.findall(".//item")

                    for item in items:
                        title_el = item.find("title")
                        link_el = item.find("link")
                        desc_el = item.find("description")
                        pub_date_el = item.find("pubDate")

                        title_text = title_el.text if title_el is not None and title_el.text else ""
                        link_text = link_el.text if link_el is not None and link_el.text else ""
                        desc_text = desc_el.text if desc_el is not None and desc_el.text else ""
                        pub_date = pub_date_el.text if pub_date_el is not None else None

                        if not link_text or link_text in seen_urls:
                            continue

                        # O título costuma vir no formato: "Empresa: Cargo"
                        company_name = "Empresa"
                        clean_title = title_text
                        if ":" in title_text:
                            parts = title_text.split(":", 1)
                            company_name = parts[0].strip()
                            clean_title = parts[1].strip()

                        combined_text = f"{clean_title} {desc_text}".lower()
                        if not any(term in combined_text for term in normalized_terms):
                            continue

                        app_url = canonical_url(link_text)
                        if not app_url:
                            continue

                        seen_urls.add(link_text)
                        clean_desc = strip_html(desc_text)

                        job = {
                            "source": "weworkremotely",
                            "external_id": link_text.split("/")[-1] if "/" in link_text else link_text,
                            "company_name": company_name,
                            "company_country": "US",
                            "title": clean_title,
                            "location": "Remote (Worldwide)",
                            "remote_type": "remote",
                            "description": clean_desc[:6000],
                            "application_url": app_url,
                            "employment_type": "Full-Time",
                            "salary_min": None,
                            "salary_max": None,
                            "salary_currency": None,
                            "salary_period": None,
                            "salary_disclosed": 0,
                            "published_at": pub_date,
                            "content_hash": generate_job_hash(company_name, clean_title, clean_desc)
                        }
                        jobs.append(job)
                except Exception:
                    continue
    except Exception as e:
        print(f"Erro ao buscar WeWorkRemotely: {e}")

    return jobs
