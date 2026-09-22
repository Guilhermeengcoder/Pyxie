# =============================================================
# modules/groq_vision.py — Visão (imagens) via Groq
#
# Por que um arquivo separado:
#   O modelo de texto da PYXIE (openai/gpt-oss-120b) NÃO enxerga
#   imagens. Para imagens é preciso um modelo multimodal.
#   Aqui reaproveitamos o client e o prompt do groq_ai.py.
#
# Trocar de modelo sem mexer no código:
#   defina GROQ_VISION_MODEL no .env (ex.: GROQ_VISION_MODEL=...)
#   Modelos com visão: https://console.groq.com/docs/vision
# =============================================================

import os
import re

from modules.groq_ai import client, _montar_prompt

GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")

MAX_TOKENS_RESPOSTA = 1024


def perguntar_groq_imagem(comando: str, imagem_data_url: str, memoria: str = "") -> str:
    """
    comando          -> o que o usuário escreveu (pode vir vazio)
    imagem_data_url  -> "data:image/jpeg;base64,...."
    memoria          -> histórico curto da conversa (texto)
    """
    pergunta = (comando or "").strip() or "Descreva o que você vê nesta imagem."

    # O prompt-base termina com "### PYXIE", então o aviso da imagem
    # entra junto da pergunta e não depois dele.
    pergunta += "\n(O usuário anexou uma imagem. Responda com base no que você vê nela.)"

    prompt = _montar_prompt(pergunta, memoria)

    try:
        response = client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": imagem_data_url}},
                    ],
                }
            ],
            max_completion_tokens=MAX_TOKENS_RESPOSTA,
        )

        texto = response.choices[0].message.content or ""

        # Segurança: remove raciocínio interno caso o modelo devolva <think>
        texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()

        return texto or "Não consegui analisar essa imagem."

    except Exception as e:
        print(f"[Groq visão] {e}")
        return "Não consegui analisar essa imagem agora."