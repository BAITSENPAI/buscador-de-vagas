# 🤖 Buscador de Vagas com Inteligência Artificial

Agente autônomo inteligente para busca, curadoria e avaliação de vagas de emprego compatíveis com o seu perfil profissional.

## ✨ Funcionalidades
- **Busca em Múltiplas Fontes**: Coleta automatizada via APIs públicas e RSS (Greenhouse, Lever, RemoteOK, WeWorkRemotely, Remotive, Jobicy).
- **Avaliação Profunda com IA**: Analisa seu currículo em PDF/Texto contra cada vaga usando Google Gemini (Gemini 3 Flash, Flash-Lite) ou OpenAI.
- **Match Personalizado (0-100%)**: Parecer detalhado, pontos fortes, pontos de atenção e verificação de eliminatórias (salário mínimo, trabalho remoto, senioridade).
- **Acesso Seguro Multi-Usuário**: Sistema de contas com **Código de Convite Secreto**, garantindo que apenas pessoas autorizadas acessem e que os currículos e chaves de IA fiquem 100% isolados e privados.
- **Deploy em 1 Clique**: Pronto para hospedar gratuitamente no **Render.com**.

---

## 🚀 Como Hospedar no Render.com (Gratuito)

1. Crie uma conta gratuita em [render.com](https://render.com).
2. Clique no botão **New +** no canto superior e selecione **Web Service**.
3. Conecte sua conta do GitHub e selecione este repositório (`buscador-de-vagas`).
4. Preencha as configurações:
   - **Name:** `buscador-vagas` (ou o nome que preferir)
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free`
5. Em **Environment Variables**, configure a chave do convite:
   - **`INVITE_CODE`**: Uma senha secreta sua (ex: `vagas2025` ou uma frase que só você e as pessoas convidadas conhecem).
6. Clique em **Deploy Web Service**.
7. Pronto! Em 2 a 3 minutos seu app estará no ar com link seguro `https://seu-app.onrender.com`.

---

## 💻 Executando Localmente

### Windows (1 Clique)
Basta dar dois cliques no arquivo `iniciar.bat` ou executar o `.exe` na pasta `dist/BuscadorDeVagas/`.

### Manualmente com Python
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```
O app abrirá automaticamente em seu navegador em `http://127.0.0.1:8000`.
