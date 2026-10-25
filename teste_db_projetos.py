from core import db

projeto = None

try:
    projeto = db.criar_projeto(
        "TESTE_PYXIE_DB",
        "Projeto temporário para testar o banco."
    )

    if not projeto:
        raise RuntimeError("Não foi possível criar o projeto.")

    projeto_id = projeto["id"]
    print("1. Projeto criado:", projeto_id)

    primeiro = db.salvar_arquivo_projeto(
        projeto_id,
        "teste.txt",
        "Versão inicial"
    )
    print("2. Arquivo criado:", primeiro["conteudo"])

    segundo = db.salvar_arquivo_projeto(
        projeto_id,
        "teste.txt",
        "Versão atualizada"
    )
    print("3. Arquivo atualizado:", segundo["conteudo"])

    arquivos = db.listar_arquivos_projeto(projeto_id)
    print("4. Quantidade de arquivos:", len(arquivos))

    arquivo = db.buscar_arquivo_projeto(projeto_id, "teste.txt")
    print("5. Conteúdo final:", arquivo["conteudo"])

    assert len(arquivos) == 1, "O arquivo foi duplicado!"
    assert arquivo["conteudo"] == "Versão atualizada"

    print("\nTESTE CONCLUÍDO COM SUCESSO!")

finally:
    if projeto:
        db.excluir_projeto(projeto["id"])
        print("Projeto temporário removido.")
