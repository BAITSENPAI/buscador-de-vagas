import re
import hashlib
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def strip_html(text: str) -> str:
    if not text:
        return ""
    # Remove scripts e styles
    clean = re.sub(r'<script[\s\S]*?</script>', ' ', text, flags=re.IGNORECASE)
    clean = re.sub(r'<style[\s\S]*?</style>', ' ', clean, flags=re.IGNORECASE)
    # Remove tags HTML
    clean = re.sub(r'<[^>]+>', ' ', clean)
    # Entidades HTML comuns
    clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&#39;', "'").replace('&quot;', '"')
    # Normaliza múltiplos espaços
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def canonical_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        # Remove parâmetros de rastreamento (tracking)
        params = parse_qs(parsed.query)
        tracking_keys = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gh_src', 'ref'}
        filtered = {k: v for k, v in params.items() if k.lower() not in tracking_keys}
        new_query = urlencode(filtered, doseq=True)
        cleaned = urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), parsed.params, new_query, ''))
        return cleaned
    except Exception:
        return str(url).strip()

def generate_job_hash(company: str, title: str, description: str) -> str:
    content = f"{company.strip().lower()}|{title.strip().lower()}|{description[:1500].strip().lower()}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
