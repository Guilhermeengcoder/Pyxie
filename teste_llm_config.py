import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import core.llm as llm
from core import llm_config as cfg
from core import memory_json
from core.brain import brain
from api import main as api_main

tmp = Path(tempfile.mkdtemp()) / "llm_config.json"
client = TestClient(api_main.app)
gemini_falso = {"provedor": "gemini", "pedidos_usados": 3}

with patch.object(cfg, "ARQUIVO", tmp), \
     patch.object(memory_json, "_remoto", return_value=False), \
     patch.object(api_main.usage_gemini, "obter",
                  side_effect=lambda *a, **k: dict(gemini_falso)):

    cfg._ultimo_conhecido = None
    cfg.invalidar_cache()

    # 1) GET /modo
    r = client.get("/modo")
    assert r.status_code == 200 and r.json()["modo"] == "groq", r.text
    assert r.json()["modos"] == ["groq", "gemini", "auto"]
    print("1 OK: GET /modo")

    # 2) POST /modo troca e rejeita modo inválido
    r = client.post("/modo", json={"modo": "gemini"})
    assert r.status_code == 200 and r.json()["modo"] == "gemini"
    assert client.get("/modo").json()["modo"] == "gemini"
    assert client.post("/modo", json={"modo": "xyz"}).status_code == 422
    print("2 OK: POST /modo troca; modo inválido recusado")

    # 3) modo gemini: /uso devolve o contador do Gemini
    u = client.get("/uso").json()
    assert u["provedor"] == "gemini" and u["modo"] == "gemini"
    assert u["pedidos_usados"] == 3
    print("3 OK: /uso mostra o Gemini")

    # 4) modo groq: /uso devolve o formato do Groq
    client.post("/modo", json={"modo": "groq"})
    u = client.get("/uso").json()
    assert u["provedor"] == "groq" and "tokens_limite" in u
    print("4 OK: /uso mostra o Groq")

    # 5) auto: segue o último que respondeu
    client.post("/modo", json={"modo": "auto"})
    with patch.object(llm, "_ultimo_provedor", None):
        assert client.get("/uso").json()["provedor"] == "groq"
    with patch.object(llm, "_ultimo_provedor", "gemini"):
        assert client.get("/uso").json()["provedor"] == "gemini"
    print("5 OK: auto segue o último provedor")

    # 6) /perguntar devolve uso com provedor e modo
    client.post("/modo", json={"modo": "groq"})
    with patch.object(brain, "process", return_value="ok"):
        r = client.post("/perguntar", json={"mensagem": "oi", "chat_id": "t"})
    assert r.status_code == 200, r.text
    assert r.json()["uso"]["provedor"] == "groq"
    assert r.json()["uso"]["modo"] == "groq"
    print("6 OK: /perguntar inclui provedor e modo no uso")