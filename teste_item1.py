import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("GROQ_API_KEY", "chave-falsa")

from fastapi.testclient import TestClient

from api import main as api_main
from core import llm_config as cfg
from core import memory_json

# ---------- 1) API do seletor ----------
tmp = Path(tempfile.mkdtemp()) / "llm_config.json"
client = TestClient(api_main.app)

with patch.object(cfg, "ARQUIVO", tmp), \
     patch.object(memory_json, "_remoto", return_value=False):

    cfg._ultimo_conhecido = None
    cfg.invalidar_cache()

    r = client.get("/modo")
    assert r.status_code == 200 and r.json()["modo"] == "groq", r.text

    for modo in ("gemini", "auto", "groq"):
        r = client.post("/modo", json={"modo": modo})
        assert r.status_code == 200 and r.json()["modo"] == modo, r.text
        assert client.get("/modo").json()["modo"] == modo

    assert client.post("/modo", json={"modo": "xyz"}).status_code == 422
    assert client.get("/modo").json()["modo"] == "groq"
print("1 OK: GET/POST /modo trocam e recusam modo inválido")

# ---------- 2) HTML ----------
html = Path("frontend/index.html").read_text(encoding="utf-8")
js = Path("frontend/script.js").read_text(encoding="utf-8")
css = Path("frontend/style.css").read_text(encoding="utf-8")

assert html.count("<h1>") == html.count("</h1>") == 1
modos = re.findall(r'class="modo-btn"[^>]*data-modo="(\w+)"', html)
assert modos == ["groq", "gemini", "auto"], modos
print("2 OK: <h1> fechado e 3 botões de modo no HTML")

# ---------- 3) ids do script.js existem no HTML ----------
usados = set(re.findall(r'getElementById\("([^"]+)"\)', js))
criados_por_js = {"indicador", "menu-compartilhamento-pyxie"}
ids_html = set(re.findall(r'id="([^"]+)"', html))
faltando = usados - ids_html - criados_por_js
assert not faltando, f"ids do script.js que não existem no HTML: {faltando}"
print("3 OK: todo getElementById do script.js existe no HTML")

# ---------- 4) colagens do JS e do CSS ----------
assert "function trocarModo" in js and "function carregarModo" in js
assert js.count("function trocarModo") == 1
assert re.search(r"carregarUsoInicial\(\);\s*\n\s*(//[^\n]*\n\s*)?carregarModo\(\);", js), \
    "carregarModo() não está logo depois de carregarUsoInicial() no fim"
assert js.index("SELETOR DE MODO") < js.index("INICIALIZAÇÃO")
for seletor in (".seletor-modo", ".modo-btn", ".aviso.aviso-info", ".uso-grupo[hidden]"):
    assert css.count(seletor) >= 1, seletor
assert css.rstrip().endswith("}")
print("4 OK: JS e CSS colados nos lugares certos")