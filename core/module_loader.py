import os
import time
import inspect
import importlib

# =============================================================
# Cache global
# Carrega módulos apenas uma vez durante toda a sessão.
# Enquanto o processo Python estiver rodando, essa variável
# persiste na memória e carregar_modulos() retorna instantâneo.
# =============================================================
_cache: dict | None = None


def carregar_modulos() -> dict:
    global _cache

    # Retorna instantaneamente se já estiver carregado
    if _cache is not None:
        return _cache

    inicio = time.perf_counter()
    modulos = {}
    pasta_modulos = "modules"

    # Segurança: verifica se a pasta existe
    if not os.path.exists(pasta_modulos):
        print(f"[module_loader] Pasta '{pasta_modulos}' não encontrada.")
        return {}

    for arquivo in os.listdir(pasta_modulos):
        if not arquivo.endswith(".py") or arquivo == "__init__.py":
            continue

        nome_modulo = arquivo[:-3]
        caminho = f"{pasta_modulos}.{nome_modulo}"

        try:
            modulo = importlib.import_module(caminho)
        except Exception as e:
            print(f"[module_loader] Erro ao importar {caminho}: {e}")
            continue

        # inspect.getmembers é mais robusto que dir() + getattr():
        # já entrega objetos filtrados, sem precisar de getattr extra
        for _, obj in inspect.getmembers(modulo, inspect.isclass):
            if hasattr(obj, "run") and hasattr(obj, "name"):
                try:
                    # Instancia aqui, uma única vez, e guarda a instância.
                    # O brain.py espera instâncias prontas — não classes.
                    instancia = obj()
                    if instancia.name:
                        modulos[instancia.name] = instancia
                except Exception as e:
                    print(f"[module_loader] Erro ao instanciar {obj.__name__}: {e}")

    _cache = modulos
    fim = time.perf_counter()

    print(
        f"[module_loader] {len(_cache)} módulo(s) carregado(s) "
        f"em {(fim - inicio):.3f}s"
    )
    print(f"[module_loader] Módulos: {list(_cache.keys())}")

    return _cache


def recarregar_modulos() -> dict:
    """
    Força recarregamento completo dos módulos.
    Use apenas se adicionar um módulo novo sem reiniciar a PYXIE.
    """
    global _cache
    _cache = None
    return carregar_modulos()