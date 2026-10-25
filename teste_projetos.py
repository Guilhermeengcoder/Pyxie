from dotenv import load_dotenv
load_dotenv(override=True)

from core import db

for tabela in ("projetos", "projeto_mensagens", "projeto_arquivos"):
    resultado = db.executar(f"SELECT COUNT(*) AS total FROM {tabela}")
    print(f"{tabela}: {resultado[0]['total']}")
