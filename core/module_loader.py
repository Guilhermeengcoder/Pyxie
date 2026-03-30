import os
import importlib

def carregar_modulos():
    modulos = {}
    pasta_modulos = "modules"

    for arquivo in os.listdir(pasta_modulos):
        if arquivo.endswith(".py") and arquivo != "__init__.py":

            nome_modulo = arquivo[:-3]
            caminho = f"{pasta_modulos}.{nome_modulo}"

            modulo = importlib.import_module(caminho)

            # procurar classes dentro do módulo
            for atributo in dir(modulo):
                obj = getattr(modulo, atributo)

                if isinstance(obj, type) and hasattr(obj, "run") and hasattr(obj, "name"):
                    instancia = obj()
                    modulos[instancia.name] = instancia

    return modulos