# =============================================================
# core/grafico.py — Geração de gráficos (matplotlib)
#
# Contrato (usado pelo core/brain.py):
#   gerar(spec) -> {"id", "arquivo", "formato"}
#   spec = {"tipo": "barras|linha|pizza", "titulo": str,
#           "rotulos": [str], "valores": [número], "unidade": str}
#
# Levanta ValueError / KeyError / TypeError se o spec for inválido
# (o brain captura esses três). A imagem é salva em data/imagens/
# com id de 32 hex, para o endpoint /imagens/{id} encontrá-la.
# =============================================================

import threading
import uuid
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sem janela: roda em servidor
import matplotlib.pyplot as plt  # noqa: E402

PASTA = Path(__file__).resolve().parent.parent / "data" / "imagens"

MAX_PONTOS = 40
MAX_ROTULO_CHARS = 30
MAX_TITULO_CHARS = 80

# O pyplot não é thread-safe e os endpoints rodam em threads.
_lock = threading.Lock()

# Cores combinando com o tema escuro da PYXIE
FUNDO = "#0d0b10"
TEXTO = "#ececec"
GRADE = "#2a2a2a"
DESTAQUE = "#f02d50"
PALETA = [
    "#f02d50", "#8b5cf6", "#3b82f6", "#10b981", "#f59e0b",
    "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#a78bfa",
]


def _validar(spec: dict):
    if not isinstance(spec, dict):
        raise TypeError("spec precisa ser um dicionário")

    tipo = str(spec.get("tipo", "barras")).strip().lower()
    if tipo in ("barra", "bar", "bars", "coluna", "colunas"):
        tipo = "barras"
    elif tipo in ("line", "linhas"):
        tipo = "linha"
    elif tipo in ("pie", "torta", "setores"):
        tipo = "pizza"

    if tipo not in ("barras", "linha", "pizza"):
        raise ValueError(f"tipo de gráfico não suportado: {tipo!r}")

    rotulos = spec["rotulos"]
    valores = spec["valores"]

    if not isinstance(rotulos, (list, tuple)) or not isinstance(valores, (list, tuple)):
        raise TypeError("rotulos e valores precisam ser listas")
    if not rotulos or len(rotulos) != len(valores):
        raise ValueError("rotulos e valores precisam ter o mesmo tamanho (e não ser vazios)")
    if len(rotulos) > MAX_PONTOS:
        raise ValueError(f"pontos demais (máximo {MAX_PONTOS})")

    rotulos = [str(r)[:MAX_ROTULO_CHARS] for r in rotulos]
    valores = [float(v) for v in valores]  # ValueError/TypeError se não for número

    if tipo == "pizza":
        if any(v < 0 for v in valores) or sum(valores) <= 0:
            raise ValueError("gráfico de pizza precisa de valores positivos")

    titulo = str(spec.get("titulo", "") or "").strip()[:MAX_TITULO_CHARS]
    unidade = str(spec.get("unidade", "") or "").strip()[:12]

    return tipo, titulo, rotulos, valores, unidade


def _fmt(v: float, unidade: str) -> str:
    texto = f"{v:,.2f}".rstrip("0").rstrip(".")
    # separador brasileiro: 1.200,50
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{unidade} {texto}".strip() if unidade == "R$" else f"{texto} {unidade}".strip()


def _estilizar(fig, ax):
    fig.patch.set_facecolor(FUNDO)
    ax.set_facecolor(FUNDO)
    ax.tick_params(colors=TEXTO)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRADE)
    ax.yaxis.grid(True, color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)


def _desenhar(tipo, titulo, rotulos, valores, unidade, caminho: Path):
    fig, ax = plt.subplots(figsize=(8, 5), dpi=130)

    try:
        if tipo == "pizza":
            fig.patch.set_facecolor(FUNDO)
            ax.set_facecolor(FUNDO)
            cores = [PALETA[i % len(PALETA)] for i in range(len(valores))]
            ax.pie(
                valores,
                labels=rotulos,
                colors=cores,
                autopct="%1.0f%%",
                startangle=90,
                textprops={"color": TEXTO, "fontsize": 10},
                wedgeprops={"edgecolor": FUNDO, "linewidth": 2},
            )
            ax.axis("equal")

        elif tipo == "linha":
            _estilizar(fig, ax)
            x = range(len(valores))
            ax.plot(x, valores, color=DESTAQUE, linewidth=2.5, marker="o", markersize=7)
            ax.fill_between(x, valores, alpha=0.12, color=DESTAQUE)
            ax.set_xticks(list(x))
            ax.set_xticklabels(rotulos)
            topo = max(abs(v) for v in valores) or 1
            for i, v in enumerate(valores):
                ax.annotate(
                    _fmt(v, unidade), (i, v),
                    textcoords="offset points", xytext=(0, 9),
                    ha="center", color=TEXTO, fontsize=9,
                )
            ax.set_ylim(min(0, min(valores)), max(valores) + topo * 0.12)

        else:  # barras
            _estilizar(fig, ax)
            cores = [PALETA[i % len(PALETA)] for i in range(len(valores))]
            barras = ax.bar(rotulos, valores, color=cores, width=0.6)
            for barra, v in zip(barras, valores):
                ax.annotate(
                    _fmt(v, unidade),
                    (barra.get_x() + barra.get_width() / 2, barra.get_height()),
                    textcoords="offset points",
                    xytext=(0, 4 if v >= 0 else -14),
                    ha="center", color=TEXTO, fontsize=9,
                )
            topo = max(abs(v) for v in valores) or 1
            ax.set_ylim(min(0, min(valores) - topo * 0.1), max(valores) + topo * 0.12)

        if tipo != "pizza" and unidade:
            ax.set_ylabel(unidade, color=TEXTO)

        if len(rotulos) > 6 and tipo != "pizza":
            plt.setp(ax.get_xticklabels(), rotation=35, ha="right")

        if titulo:
            ax.set_title(titulo, color=TEXTO, fontsize=14, fontweight="bold", pad=14)

        fig.tight_layout()
        fig.savefig(caminho, facecolor=fig.get_facecolor(), format="png")
    finally:
        plt.close(fig)  # libera a memória mesmo se der erro


def gerar(spec: dict) -> dict:
    """Gera o gráfico, salva em data/imagens/ e devolve {"id","arquivo","formato"}."""
    tipo, titulo, rotulos, valores, unidade = _validar(spec)

    imagem_id = uuid.uuid4().hex
    PASTA.mkdir(parents=True, exist_ok=True)
    caminho = PASTA / f"{imagem_id}.png"

    with _lock:
        _desenhar(tipo, titulo, rotulos, valores, unidade, caminho)

    return {"id": imagem_id, "arquivo": str(caminho), "formato": "png"}


# Teste direto:  python -m core.grafico
if __name__ == "__main__":
    r = gerar({
        "tipo": "barras",
        "titulo": "Gastos de março",
        "rotulos": ["Aluguel", "Mercado", "Transporte"],
        "valores": [1200, 650, 180],
        "unidade": "R$",
    })
    print("Gerado:", r["arquivo"])