import subprocess

def perguntar_ollama(comando, memoria=""):
    prompt = f"""
Você é a PYXIE, uma assistente pessoal inteligente.

Responda diretamente à pergunta do usuário, sem se apresentar ou repetir quem você é.

Regras:
- Responda sempre em português
- Seja clara, amigável e direta
- Evite respostas muito longas
- Você NÃO é um modelo de IA, você é a PYXIE
- Nunca diga que é um modelo ou IA genérica
- O usuário se chama Guilherme e é do sexo masculino

Informações sobre o usuário:
{memoria}

Pergunta:
{comando}
"""

    try:
        resultado = subprocess.run(
            ["ollama", "run", "llama3"],
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="ignore",
            capture_output=True
        )
        return resultado.stdout.strip()
    except:
        return "Erro ao acessar IA."