from core import db

db.iniciar()
print("disponivel:", db.disponivel())

tabelas = db.executar(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'public' ORDER BY table_name"
)
print([t["table_name"] for t in tabelas])