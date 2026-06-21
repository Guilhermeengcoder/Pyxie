import requests

# ================================================================
# CONFIG
# ================================================================

OLLAMA_URL       = "http://localhost:11434/api/generate"
OLLAMA_MODEL     = "llama3" #Alternar entre os modelos (llama3) mais potente (llama3.2:3b) mais fraco
TIMEOUT          = 180           # 3 min — llama3 8B em CPU pura pode precisar
MAX_MEMORY_CHARS = 1000

session = requests.Session()

# ================================================================
# PROMPT
# ================================================================

def _montar_prompt(comando: str, memoria: str) -> str:
    memoria = memoria[-MAX_MEMORY_CHARS:]
 
    tem_historico = len(memoria.strip()) > 0
 
    instrucao_saudacao = (
        "- NÃO cumprimente o usuário, a conversa já está em andamento."
        if tem_historico else
        "- Cumprimente o usuário de forma natural e breve."
    )
    
    return f"""
Você é a PYXIE, uma assistente pessoal inteligente.

Regras:
- Responda sempre em português
- Seja amigável e objetiva
- Nunca invente fatos, nomes ou informações
- Se não souber algo, diga claramente e sem enrolação
- Você NÃO é um modelo de IA genérico — você é a PYXIE, criada por Guilherme
- O usuário se chama Guilherme e é do sexo masculino
- NÃO cumprimente o usuário se já houver histórico de conversa
- Continue a conversa naturalmente sem repetir saudações
- Não repita informações que já foram ditas na conversa
{instrucao_saudacao}
- Analise o contexto completo antes de responder
- Outras pessoas podem conversar com você — trate-as pelo nome que informarem


### Histórico
{memoria if memoria else "Início da conversa."}
 
### Usuário
{comando}
 
### PYXIE""".strip()

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
                    "num_ctx":     2048,  # força contexto menor — ignora o padrão 4096
                    "num_predict": 200,   # sempre manter entre 200 e 400
                    "temperature": 0.7,
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
# INTERFACE PÚBLICA
# ================================================================

def perguntar_ollama(comando: str, memoria: str = "") -> str:
    prompt = _montar_prompt(comando, memoria)

    resposta = _perguntar_http(prompt)
    if resposta:
        return resposta

    return "Não consegui processar isso agora."
