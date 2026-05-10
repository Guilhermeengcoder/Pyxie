import subprocess
import requests

# ================================================================
# CONFIG
# ================================================================

OLLAMA_URL       = "http://localhost:11434/api/generate"
OLLAMA_MODEL     = "llama3"
TIMEOUT          = 180           # 3 min — llama3 8B em CPU pura pode precisar
MAX_MEMORY_CHARS = 1500

session = requests.Session()

# ================================================================
# PROMPT
# ================================================================

def _montar_prompt(comando: str, memoria: str) -> str:
    memoria = memoria[-MAX_MEMORY_CHARS:]
    return f"""
Você é a PYXIE, uma assistente pessoal inteligente.

Regras:
- Responda sempre em português
- Seja amigável e objetiva
- Nunca invente fatos, nomes ou informações
- Se não souber algo, diga claramente
- Você NÃO é um modelo de IA genérico
- O usuário se chama Guilherme e é do sexo masculino

Memória:
{memoria}

Usuário:
{comando}
""".strip()

# ================================================================
# HTTP (principal)
# ================================================================

def _perguntar_http(prompt: str):
    try:
        response = session.post(
            OLLAMA_URL,
            json={
                "model":      OLLAMA_MODEL,
                "prompt":     prompt,
                "stream":     False,
                "keep_alive": "30m",
                "options": {
                    "num_ctx":     1024,  # força contexto menor — ignora o padrão 4096
                    "num_predict": 400,   # suficiente para respostas completas
                    "temperature": 0.7,
                    "num_thread":  4,     # limita threads de CPU do modelo
                }
            },
            timeout=TIMEOUT,
        )

        if response.status_code == 200:
            return response.json()["response"].strip()

    except Exception:
        pass

    return None

# ================================================================
# FALLBACK subprocess
# ================================================================

def _fallback(prompt: str):
    try:
        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL],
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=TIMEOUT,
        )
        return result.stdout.strip() or None

    except Exception:
        return None

# ================================================================
# INTERFACE PÚBLICA
# ================================================================

def perguntar_ollama(comando: str, memoria: str = "") -> str:
    prompt = _montar_prompt(comando, memoria)

    resposta = _perguntar_http(prompt)
    if resposta:
        return resposta

    resposta = _fallback(prompt)
    if resposta:
        return resposta

    return "Não consegui processar isso agora."