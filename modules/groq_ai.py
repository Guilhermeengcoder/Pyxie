from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

MAX_MEMORY_CHARS = 1000
GROQ_MODEL = "openai/gpt-oss-120b"

api_key = os.getenv("GROQ_API_KEY")


client = Groq(
    api_key=api_key
)

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

def perguntar_groq(comando: str, memoria: str = "") -> str:
    prompt = _montar_prompt(comando, memoria)
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
         
        return response.choices[0].message.content

    except Exception as e:
        print(f"[Groq] {e}")
        return "Não consegui processar isso agora."