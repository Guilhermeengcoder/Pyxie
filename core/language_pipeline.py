import unicodedata
import re


class LanguagePipeline:

    def __init__(self):
        # ==================================================
        # DICIONÁRIO DE CORREÇÕES
        # Corrige abreviações e erros comuns de digitação
        # ==================================================
        self.correcoes = {
            "pq": "por que",
            "q": "que",
            "n": "nao",
            "tb": "tambem",
            "vc": "voce",
            "vcs": "voces",
            "blz": "beleza",
            "msg": "mensagem"
        }

    # ==================================================
    # EXTRAÇÃO DE PALAVRAS-CHAVE
    # Remove palavras muito curtas (ex: "de", "a", "e")
    # sem destruir o contexto geral
    # ==================================================
    def extrair_palavras_chave(self, tokens):
        return [t for t in tokens if len(t) > 2]

    # ==================================================
    # NORMALIZAÇÃO DE TEXTO
    # - Converte para minúsculas
    # - Remove acentos (ex: "ação" → "acao")
    # ==================================================
    def normalizar(self, texto):
        texto = texto.lower()
        texto = unicodedata.normalize("NFD", texto)
        texto = texto.encode("ascii", "ignore").decode("utf-8")
        return texto

    # ==================================================
    # CORREÇÃO ORTOGRÁFICA SIMPLES
    # - Aplica correções com base no dicionário
    # - Usa tokenização para evitar problemas com pontuação
    # ==================================================
    def corrigir(self, texto):
        tokens = self.tokenizar(texto)

        tokens_corrigidos = [
            self.correcoes.get(t, t) for t in tokens
        ]

        return " ".join(tokens_corrigidos)

    # ==================================================
    # TOKENIZAÇÃO
    # - Divide o texto em palavras
    # - Ignora pontuação automaticamente
    # ==================================================
    def tokenizar(self, texto):
        return re.findall(r'\b\w+\b', texto)

    # ==================================================
    # PIPELINE COMPLETO
    # Executa todas as etapas de processamento e retorna
    # múltiplas versões do texto para diferentes usos
    # ==================================================
    def processar(self, texto):

        # Texto original (sem alterações)
        texto_original = texto

        # Texto normalizado (minúsculo + sem acento)
        texto_normalizado = self.normalizar(texto)

        # Texto corrigido (abreviações ajustadas)
        texto_corrigido = self.corrigir(texto_normalizado)

        # Lista de palavras (tokens)
        tokens = self.tokenizar(texto_corrigido)

        # Palavras-chave (filtragem leve)
        palavras_chave = self.extrair_palavras_chave(tokens)

        # Retorna tudo organizado
        return {
            "original": texto_original,
            "normalizado": texto_normalizado,
            "corrigido": texto_corrigido,
            "tokens": tokens,
            "palavras_chave": palavras_chave
        }


# ==================================================
# INSTÂNCIA GLOBAL DA PIPELINE
# Pode ser importada em outros módulos da PYXIE
# ==================================================
pipeline = LanguagePipeline()