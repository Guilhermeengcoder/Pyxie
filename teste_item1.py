import re
import subprocess
import sys
from pathlib import Path

from core.filtro_segredos import detectar_segredos

ESTE = Path(__file__).name
falhas = []


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print("git falhou:", r.stderr.strip())
        sys.exit(1)
    return r.stdout


rastreados = git("ls-files").splitlines()
status = git("status", "--porcelain").splitlines()


def ok(msg):
    print("OK:", msg)


def falha(msg):
    falhas.append(msg)
    print("FALHOU:", msg)


# 1) testes soltos
soltos = [f for f in rastreados if re.match(r"^(teste|testar)[_\w]*\.py$", Path(f).name) and f != ESTE]
presentes = [p.name for p in Path(".").glob("teste*.py") if p.name != ESTE] + \
            [p.name for p in Path(".").glob("testar*.py")]
if soltos or presentes:
    falha(f"testes ainda no projeto: rastreados={soltos} locais={sorted(set(presentes))}")
else:
    ok("nenhum teste_*.py / testar_*.py no projeto")

# 2) nada sensível no git status nem rastreado
sens = re.compile(r"(^|/)(\.env|memory\.json(\.bak)?|data/(?!identity\.json)[^/]+|data/stm/.*)$")
no_status = [l for l in status if sens.search(l[3:].strip().strip('"'))]
no_git = [f for f in rastreados if sens.search(f)]
if no_status or no_git:
    falha(f"arquivos sensíveis/locais: status={no_status} rastreados={no_git}")
else:
    ok("git status e git ls-files sem .env, memory.json nem data/ (exceto identity.json)")

# 3) .gitignore cobre o que o app gera
gi = Path(".gitignore").read_text(encoding="utf-8").splitlines()
precisa = [".env", "memory.json", "memory.json.bak", "data/stm/", "data/llm_config.json",
           "data/knowledge.json", "data/reminders.json", "data/gemini_uso.json"]
faltam = [p for p in precisa if p not in gi]
if faltam:
    falha(f".gitignore sem: {faltam}")
else:
    ok(".gitignore cobre os arquivos gerados pelo app")

# 4) requirements
req = Path("requirements.txt").read_text(encoding="utf-8").lower()
faltam = [p for p in ("tzdata", "google-genai", "groq", "fastapi", "uvicorn", "requests", "python-dotenv")
          if p not in req]
if faltam:
    falha(f"requirements.txt sem: {faltam}")
else:
    ok("requirements.txt tem tzdata e as dependências dos provedores")

# 5) .env: só nomes de variáveis, nunca valores
env = Path(".env")
if env.exists():
    nomes = {l.split("=", 1)[0].strip() for l in env.read_text(encoding="utf-8").splitlines()
             if "=" in l and not l.lstrip().startswith("#")}
    if "GROQ_BASE_URL" in nomes:
        falha("GROQ_BASE_URL ainda está no .env (apague a linha)")
    else:
        ok("GROQ_BASE_URL não está no .env")
    obrig = {"GROQ_API_KEY", "GEMINI_API_KEY", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"}
    if obrig - nomes:
        falha(f".env sem as variáveis: {sorted(obrig - nomes)}")
    else:
        ok(".env tem as 4 variáveis obrigatórias (valores não lidos)")
else:
    print("PULADO: .env não existe aqui")

# 6) nenhum segredo literal em arquivo rastreado
achados = []
for f in rastreados:
    if f == ESTE or not f.endswith((".py", ".js", ".html", ".css", ".json", ".sh", ".txt", ".md")):
        continue
    try:
        texto = Path(f).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    tipos = detectar_segredos(texto)
    if tipos:
        achados.append((f, tipos))
if achados:
    falha(f"possíveis segredos em arquivos rastreados: {achados}")
else:
    ok("nenhum padrão de chave/senha nos arquivos rastreados")

print()
if falhas:
    print(f"{len(falhas)} pendência(s) antes do push.")
    sys.exit(1)
print("Tudo certo para o push. Apague este teste_item4.py antes do commit.")