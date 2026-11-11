import httpx
import json
import re
from typing import Dict, Any, Optional

def clean_json_response(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text.strip())
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                pass
        raise ValueError(f"Não foi possível parsear a resposta da IA como JSON: {text[:200]}")

def extract_text_from_interaction(data: Dict[str, Any]) -> str:
    # 1. output_text direto se presente
    if "output_text" in data and data["output_text"]:
        return str(data["output_text"])

    # 2. Percorre steps procurando model_output (Padrão Interactions API)
    steps = data.get("steps", [])
    texts = []
    for step in steps:
        if step.get("type") == "model_output":
            for c in step.get("content", []):
                if c.get("type") == "text" and "text" in c:
                    texts.append(c["text"])
    if texts:
        return "\n".join(texts)

    # 3. Fallback candidates clássico
    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        return "\n".join(p.get("text", "") for p in parts if "text" in p)

    return str(data)

class AIService:
    @staticmethod
    def clean_api_key(key: str) -> str:
        if not key:
            return ""
        return key.strip().strip("'\"").strip()

    @staticmethod
    def normalize_model(provider: str, model: Optional[str]) -> str:
        if provider == "gemini":
            if model in ["gemini-3-flash-preview", "gemini-3.1-flash-lite-preview"]:
                return model
            return "gemini-3-flash-preview"
        elif provider == "openai":
            return model or "gpt-4o-mini"
        return model or "gemini-3-flash-preview"

    @classmethod
    async def test_connection(cls, provider: str, api_key: str, model: str = None) -> Dict[str, Any]:
        cleaned_key = cls.clean_api_key(api_key)
        if not cleaned_key:
            return {"success": False, "message": "Chave de API não informada."}

        model_name = cls.normalize_model(provider, model)

        try:
            if provider == "gemini":
                candidate_models = [model_name, "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview"]
                candidate_models = list(dict.fromkeys(candidate_models))

                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": cleaned_key
                }
                payload = {
                    "contents": [{"parts": [{"text": "Responda apenas com a palavra: OK"}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 10}
                }

                last_error = ""
                async with httpx.AsyncClient(timeout=15.0) as client:
                    for m in candidate_models:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
                        resp = await client.post(url, headers=headers, json=payload)
                        if resp.status_code == 200:
                            return {"success": True, "message": f"Conexão com Google Gemini ({m}) bem-sucedida!"}
                        
                        try:
                            last_error = resp.json().get("error", {}).get("message", resp.text)
                        except Exception:
                            last_error = resp.text

                return {"success": False, "message": f"Erro Gemini: {last_error}"}

            elif provider == "openai":
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {cleaned_key}"}
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Responda apenas: OK"}],
                    "max_tokens": 5
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        return {"success": True, "message": f"Conexão com OpenAI ({model_name}) bem-sucedida!"}
                    else:
                        try:
                            error_detail = resp.json().get("error", {}).get("message", resp.text)
                            return {"success": False, "message": f"Erro OpenAI ({resp.status_code}): {error_detail}"}
                        except Exception:
                            return {"success": False, "message": f"Erro OpenAI ({resp.status_code}): {resp.text}"}

            return {"success": False, "message": f"Provedor '{provider}' não suportado."}
        except Exception as e:
            return {"success": False, "message": f"Falha ao conectar: {str(e)}"}

    @classmethod
    async def evaluate_job(
        cls,
        profile: Dict[str, Any],
        job: Dict[str, Any]
    ) -> Dict[str, Any]:
        provider = profile.get("ai_provider", "gemini")
        api_key = cls.clean_api_key(profile.get("ai_api_key", ""))
        model = cls.normalize_model(provider, profile.get("ai_model"))

        if not api_key:
            return {
                "score": 50,
                "seniority": "Não analisado",
                "technical_score": 50,
                "experience_score": 50,
                "compensation_score": 50,
                "remote_score": 50,
                "qualified": True,
                "positives": ["Chave de IA não configurada - exibindo vaga pelo filtro de palavras-chave"],
                "concerns": ["Configure sua chave de IA nas opções para ter a análise profunda"],
                "reasoning": "Vaga capturada por título compatível, aguardando configuração de chave de IA.",
                "hard_gate_reason": None
            }

        prompt = f"""Você é um especialista sênior em recrutamento e seleção de pessoas.
Sua missão é avaliar minuciosamente a compatibilidade entre uma VAGA DE EMPREGO e o PERFIL DO CANDIDATO.

PERFIL DO CANDIDATO:
- Nome: {profile.get('name', 'Candidato')}
- Cargos Alvos de Interesse: {profile.get('target_roles', '[]')}
- Termos a Evitar: {profile.get('negative_keywords', '[]')}
- Modelos de Trabalho Aceitos: {profile.get('work_modes', '["remote"]')}
- Localização Preferencial do Candidato: {profile.get('preferred_location', 'Brasil')}
- Pretensão Salarial Mínima: R$ {profile.get('min_salary', 0)}
- Tipos de Contrato Aceitos: {profile.get('employment_types', '["CLT", "PJ"]')}
- País da Empresa Preferencial: {profile.get('company_country', 'BR')}
- Histórico / Resumo / Currículo:
\"\"\"{profile.get('resume_text', 'Não informado')}\"\"\"

VAGA A SER AVALIADA:
- Título da Vaga: {job.get('title')}
- Empresa: {job.get('company_name')}
- Localização da Vaga: {job.get('location')}
- Modalidade Declarada: {job.get('remote_type')}
- Salário Divulgado: {job.get('salary_min')} a {job.get('salary_max')} {job.get('salary_currency')} ({job.get('salary_period')})
- Descrição da Vaga:
\"\"\"{job.get('description', '')[:3500]}\"\"\"

REGRAS DE AVALIAÇÃO:
1. GATES ELIMINATÓRIOS (Se falhar em algum, a vaga NÃO é qualificada):
   - Se o candidato quer APENAS REMOTO ("remote") e a vaga exige trabalho presencial obrigatório em outra cidade -> remote_gate = false.
   - Se o candidato definiu pretensão salarial mínima (>0) e o salário divulgado na vaga for EXPLICITAMENTE menor que o piso -> salary_gate = false. (Atenção: se a vaga NÃO divulgar salário, NÃO elimine por isso).
   - Se a vaga for de uma área completamente não relacionada aos cargos do candidato -> role_gate = false.
2. PONTUAÇÃO (0 a 100):
   - technical_score (peso 25%): Aderência de ferramentas, linguagens e tecnologias.
   - experience_score (peso 25%): Experiência prática prévia nas responsabilidades da vaga.
   - seniority_score (peso 20%): Nível de maturidade exigido vs maturidade do candidato.
   - compensation_score (peso 15%): Adequação de remuneração.
   - remote_score (peso 15%): Modalidade de trabalho.
   - score: Média ponderada final de 0 a 100.
3. PARECER:
   - positives: 2 a 3 pontos fortes reais de aderência.
   - concerns: 1 a 2 pontos de alerta ou gaps de competência.
   - reasoning: Síntese de 2 a 3 frases explicando o resultado.
   - qualified: true apenas se passar em todos os gates e o score final for >= 65.

Responda EXCLUSIVAMENTE em formato JSON com a seguinte estrutura:
{{
  "score": 85,
  "seniority": "Sênior",
  "technical_score": 85,
  "experience_score": 80,
  "compensation_score": 90,
  "remote_score": 100,
  "qualified": true,
  "positives": ["...", "..."],
  "concerns": ["..."],
  "reasoning": "...",
  "hard_gate_reason": null
}}
"""

        raw_response = ""
        if provider == "gemini":
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            }
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json"
                }
            }
            candidate_models = [model, "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview"]
            candidate_models = list(dict.fromkeys(candidate_models))

            last_err = ""
            async with httpx.AsyncClient(timeout=45.0) as client:
                for m in candidate_models:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        raw_response = extract_text_from_interaction(resp.json())
                        break
                    else:
                        last_err = resp.text

            if not raw_response:
                raise Exception(f"Erro Gemini: {last_err}")

        elif provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.2
            }
            async with httpx.AsyncClient(timeout=40.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise Exception(f"Erro OpenAI: {resp.text}")
                data = resp.json()
                raw_response = data["choices"][0]["message"]["content"]

        parsed = clean_json_response(raw_response)
        return parsed

    @classmethod
    async def extract_profile_from_resume(cls, resume_text: str, provider: str, api_key: str, model: str = None) -> Dict[str, Any]:
        cleaned_key = cls.clean_api_key(api_key)
        if not cleaned_key:
            return {"error": "Chave de IA necessária para autocompletar perfil."}

        model_name = cls.normalize_model(provider, model)
        prompt = f"""Analise o seguinte currículo profissional e extraia as principais informações para configurar um agente de busca de vagas.

CURRÍCULO:
\"\"\"{resume_text[:4000]}\"\"\"

Extraia e retorne EXCLUSIVAMENTE em formato JSON com o seguinte formato:
{{
  "name": "Nome Completo do Candidato",
  "summary": "Resumo profissional de 2 frases destacando os pontos fortes",
  "suggested_roles": ["Cargo Alvo 1", "Cargo Alvo 2", "Cargo Alvo 3"],
  "seniority": "Júnior | Pleno | Sênior | Especialista | Liderança",
  "skills": ["Habilidade 1", "Habilidade 2", "Habilidade 3", "..."]
}}
"""
        raw_response = ""
        if provider == "gemini":
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": cleaned_key
            }
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
            }
            candidate_models = [model_name, "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview"]
            candidate_models = list(dict.fromkeys(candidate_models))

            last_err = ""
            async with httpx.AsyncClient(timeout=35.0) as client:
                for m in candidate_models:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        raw_response = extract_text_from_interaction(resp.json())
                        break
                    else:
                        last_err = resp.text

            if not raw_response:
                raise Exception(f"Erro Gemini: {last_err}")

        elif provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {cleaned_key}"}
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise Exception(f"Erro OpenAI: {resp.text}")
                data = resp.json()
                raw_response = data["choices"][0]["message"]["content"]

        return clean_json_response(raw_response)
