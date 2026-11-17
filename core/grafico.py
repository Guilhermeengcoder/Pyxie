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

import re
import threading
import unicodedata
import uuid
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sem janela: roda em servidor
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

PASTA = Path(__file__).resolve().parent.parent / "data" / "imagens"

MAX_PONTOS = 40
MAX_ROTULO_CHARS = 30
MAX_TITULO_CHARS = 80

# O pyplot não é thread-safe e os endpoints rodam em threads.
_lock = threading.Lock()

# Cores combinando com o tema escuro da PYXIE
FUNDO = "#0d0b10"
TEXTO = "#ececec"
SUAVE = "#9d96ae"
GRADE = "#2a2733"
DESTAQUE = "#f02d50"
NEUTRA = "#6d5b94"
PALETA = [
    "#f02d50", "#8b5cf6", "#3b82f6", "#10b981", "#f59e0b",
    "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#a78bfa",
]

# Rótulos que formam uma sequência (não devem ser reordenados)
_SEQUENCIA = {
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
    "agosto", "setembro", "outubro", "novembro", "dezembro",
    "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set",
    "out", "nov", "dez",
    "segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo",
    "seg", "ter", "qua", "qui", "sex", "sab", "dom",
}


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


# ---------------- formatação ----------------

def _num(v: float) -> str:
    """1200.5 -> '1.200,5' (padrão brasileiro)."""
    texto = f"{v:,.2f}".rstrip("0").rstrip(".")
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_valor(v: float, unidade: str = "") -> str:
    """Usada também pelo brain (comentário do gráfico)."""
    texto = _num(v)
    if unidade == "R$":
        return f"R$ {texto}"
    return f"{texto} {unidade}".strip()


def _pct(v: float, total: float) -> str:
    return f"{v / total * 100:.0f}%"


def _eh_sequencia(rotulos) -> bool:
    """Meses, dias da semana, anos, trimestres: ordem importa."""
    def token(r):
        t = unicodedata.normalize("NFD", str(r).lower())
        t = t.encode("ascii", "ignore").decode()
        achado = re.findall(r"[a-z0-9]+", t)
        return achado[0] if achado else ""

    tokens = [token(r) for r in rotulos]
    return bool(tokens) and all(
        t in _SEQUENCIA or re.fullmatch(r"(19|20)\d{2}|\d{1,2}|[qt]\d", t)
        for t in tokens
    )


# ---------------- estilo ----------------

def _estilizar(fig, ax):
    fig.patch.set_facecolor(FUNDO)
    ax.set_facecolor(FUNDO)
    ax.tick_params(colors=SUAVE, labelsize=11, length=0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRADE)


def _cabecalho(fig, titulo, subtitulo) -> float:
    """Título, subtítulo e marca. Devolve o topo livre para o gráfico."""
    y = 0.955
    if titulo:
        fig.text(0.05, y, titulo, color=TEXTO, fontsize=17,
                 fontweight="bold", ha="left", va="top")
        y -= 0.075
    if subtitulo:
        fig.text(0.05, y, subtitulo, color=SUAVE, fontsize=11.5,
                 ha="left", va="top")
        y -= 0.055
    fig.text(0.985, 0.02, "PYXIE", color="#4a4455", fontsize=9,
             fontweight="bold", ha="right", va="bottom")
    return max(0.5, y - 0.005)


def _subtitulo(tipo, rotulos, valores, unidade) -> str:
    total = sum(valores)

    if tipo == "linha":
        if len(valores) > 1 and valores[0] != 0:
            var = (valores[-1] - valores[0]) / abs(valores[0]) * 100
            return f"Variação do primeiro ao último ponto: {var:+.0f}%"
        return ""

    positivos = len(valores) > 1 and total > 0 and all(v >= 0 for v in valores)
    maior = ""
    if positivos:
        i = valores.index(max(valores))
        maior = f"maior: {rotulos[i]} ({_pct(valores[i], total)})"

    if tipo == "pizza":
        return maior.capitalize()

    base = f"Total: {formatar_valor(total, unidade)}"
    return f"{base}  ·  {maior}" if maior else base


def _eixo_valor(ax, eixo: str):
    formato = FuncFormatter(lambda v, _: _num(v))
    if eixo == "y":
        ax.yaxis.set_major_formatter(formato)
        ax.yaxis.grid(True, color=GRADE, linewidth=0.8)
    else:
        ax.xaxis.set_major_formatter(formato)
        ax.xaxis.grid(True, color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)


# ---------------- tipos de gráfico ----------------

def _barras(ax, rotulos, valores, unidade):
    n = len(valores)
    total = sum(valores)
    mostrar_pct = n > 1 and total > 0 and all(v >= 0 for v in valores)
    amp = max(abs(v) for v in valores) or 1
    i_max = valores.index(max(valores))
    cores = [DESTAQUE if (i == i_max and n > 1) else NEUTRA for i in range(n)]

    horizontal = (
        (n > 6 or max(len(r) for r in rotulos) > 14)
        and not _eh_sequencia(rotulos)
    )

    if horizontal:
        barras = ax.barh(rotulos, valores, color=cores, height=0.62)
        ax.invert_yaxis()  # o maior fica no topo
        _eixo_valor(ax, "x")
        for b, v in zip(barras, valores):
            txt = formatar_valor(v, unidade)
            if mostrar_pct:
                txt += f"  ·  {_pct(v, total)}"
            ax.annotate(
                txt, (v, b.get_y() + b.get_height() / 2),
                textcoords="offset points", xytext=(8 if v >= 0 else -8, 0),
                ha="left" if v >= 0 else "right", va="center",
                color=TEXTO, fontsize=10.5, fontweight="bold",
            )
        ax.set_xlim(min(0, min(valores) - amp * 0.05),
                    max(0, max(valores)) + amp * 0.38)
        return

    denso = n > 8
    barras = ax.bar(rotulos, valores, color=cores, width=0.62)
    _eixo_valor(ax, "y")
    for b, v in zip(barras, valores):
        txt = formatar_valor(v, unidade)
        if mostrar_pct and not denso:
            txt += f"\n{_pct(v, total)}"
        ax.annotate(
            txt, (b.get_x() + b.get_width() / 2, v),
            textcoords="offset points", xytext=(0, 6 if v >= 0 else -6),
            ha="center", va="bottom" if v >= 0 else "top",
            color=TEXTO, fontsize=9 if denso else 10.5,
            fontweight="bold", linespacing=1.3,
        )
    ax.set_ylim(min(0, min(valores) - amp * 0.12),
                max(0, max(valores)) + amp * 0.24)
    if denso:
        plt.setp(ax.get_xticklabels(), rotation=35, ha="right")


def _linha(ax, rotulos, valores, unidade):
    n = len(valores)
    x = list(range(n))
    base = min(0, min(valores))
    amp = max(abs(v) for v in valores) or 1

    ax.plot(x, valores, color=DESTAQUE, linewidth=2.8, marker="o",
            markersize=7, markerfacecolor=FUNDO, markeredgewidth=2.2)
    ax.fill_between(x, valores, base, alpha=0.12, color=DESTAQUE)
    ax.plot([x[-1]], [valores[-1]], marker="o", markersize=11, color=DESTAQUE)

    if n <= 12:
        rotular = set(x)
    else:  # muitos pontos: só início, fim, pico e vale
        rotular = {0, n - 1, valores.index(max(valores)), valores.index(min(valores))}

    for i in sorted(rotular):
        ax.annotate(
            formatar_valor(valores[i], unidade), (i, valores[i]),
            textcoords="offset points", xytext=(0, 11),
            ha="center", color=TEXTO, fontsize=10, fontweight="bold",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(rotulos)
    if n > 8:
        plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    _eixo_valor(ax, "y")
    ax.set_ylim(base, max(valores) + amp * 0.16)


def _pizza(ax, rotulos, valores, unidade):
    total = sum(valores)
    cores = [PALETA[i % len(PALETA)] for i in range(len(valores))]

    wedges, _t, _a = ax.pie(
        valores,
        colors=cores,
        startangle=90,
        counterclock=False,
        autopct=lambda p: f"{p:.0f}%" if p >= 5 else "",
        pctdistance=0.79,
        textprops={"color": "#ffffff", "fontsize": 11, "fontweight": "bold"},
        wedgeprops={"width": 0.42, "edgecolor": FUNDO, "linewidth": 2},
    )
    ax.text(0, 0, f"Total\n{formatar_valor(total, unidade)}",
            ha="center", va="center", color=TEXTO,
            fontsize=14, fontweight="bold", linespacing=1.4)
    ax.axis("equal")

    ax.legend(
        wedges,
        [f"{r}   {formatar_valor(v, unidade)}  ({_pct(v, total)})"
         for r, v in zip(rotulos, valores)],
        loc="center left", bbox_to_anchor=(1.04, 0.5),
        frameon=False, labelcolor=TEXTO, fontsize=11, labelspacing=1.0,
    )


# ---------------- desenho ----------------

def _desenhar(tipo, titulo, rotulos, valores, unidade, caminho: Path):
    # Barras e pizza: do maior para o menor (exceto meses, anos etc.)
    if tipo in ("barras", "pizza") and not _eh_sequencia(rotulos):
        pares = sorted(zip(rotulos, valores), key=lambda p: p[1], reverse=True)
        rotulos = [p[0] for p in pares]
        valores = [p[1] for p in pares]

    fig, ax = plt.subplots(figsize=(9, 5.6), dpi=140)

    try:
        subtitulo = _subtitulo(tipo, rotulos, valores, unidade)

        if tipo == "pizza":
            fig.patch.set_facecolor(FUNDO)
            ax.set_facecolor(FUNDO)
            topo = _cabecalho(fig, titulo, subtitulo)
            _pizza(ax, rotulos, valores, unidade)
            fig.subplots_adjust(left=0.03, right=0.60, top=topo, bottom=0.06)
        else:
            _estilizar(fig, ax)
            topo = _cabecalho(fig, titulo, subtitulo)
            if tipo == "linha":
                _linha(ax, rotulos, valores, unidade)
            else:
                _barras(ax, rotulos, valores, unidade)
            fig.tight_layout(rect=(0.02, 0.05, 0.98, topo))

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
        "titulo": "Despesas mensais",
        "rotulos": ["Aluguel", "Mercado", "Transporte"],
        "valores": [1200, 650, 180],
        "unidade": "R$",
    })
    print("Gerado:", r["arquivo"])