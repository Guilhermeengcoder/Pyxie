
// ========================================
// ELEMENTOS
// ========================================

const chat = document.getElementById("chat");
const input = document.getElementById("mensagem");
const botao = document.getElementById("enviar");
const containerChat = document.querySelector(".chat-container");

const lista = document.getElementById("lista-conversas");
const botaoNova = document.getElementById("nova-conversa");
const botaoLimpar = document.getElementById("limpar-tudo");
const botaoMenu = document.getElementById("menu");
const overlay = document.getElementById("overlay");

// Imagem e câmera
const botaoAnexar = document.getElementById("anexar");
const botaoCamera = document.getElementById("camera");
const inputArquivo = document.getElementById("arquivo");
const inputArquivoCamera = document.getElementById("arquivo-camera");
const previa = document.getElementById("previa");
const previaImg = document.getElementById("previa-img");
const previaRemover = document.getElementById("previa-remover");
const aviso = document.getElementById("aviso");

const cameraModal = document.getElementById("camera-modal");
const cameraVideo = document.getElementById("camera-video");
const cameraErro = document.getElementById("camera-erro");
const cameraCancelar = document.getElementById("camera-cancelar");
const cameraVirar = document.getElementById("camera-virar");
const cameraCapturar = document.getElementById("camera-capturar");

function gerarChatId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "chat-" + Date.now() + "-" + Math.random().toString(36).slice(2);
}

let chatId = gerarChatId(); // reload da página = chat novo


// ========================================
// CONFIGURAÇÕES
// ========================================

const CHAVE_STORAGE = "pyxie_conversas_v1";

const SAUDACAO = "Olá! Como posso ajudar?";

// Quantas mensagens anteriores vão junto a cada pedido.
const MENSAGENS_DE_CONTEXTO = 6;

const MAX_CONVERSAS = 50;

// Imagens
const MAX_ARQUIVO_MB = 15;
const IMAGEM_LADO_MAX = 1280;
const IMAGEM_QUALIDADE = 0.85;
const MINIATURA_LADO_MAX = 320;
const MINIATURA_QUALIDADE = 0.6;

const PLACEHOLDER_PADRAO = input.placeholder;
const PLACEHOLDER_COM_IMAGEM = "Pergunte algo sobre a imagem (opcional)";


// ========================================
// ESTADO
// ========================================

let estado = {
    conversas: [],
    ativa: null
};

// ID da conversa que está aguardando resposta da API
let pendenteId = null;

// Imagem anexada, ainda não enviada
let imagemPendente = null;

// Câmera
let streamCamera = null;
let cameraFrontal = false;

let timerAviso = null;


// ========================================
// ARMAZENAMENTO LOCAL
// ========================================

function carregarEstado() {
    try {
        const bruto = localStorage.getItem(CHAVE_STORAGE);

        if (!bruto) {
            return;
        }

        const dados = JSON.parse(bruto);

        if (dados && Array.isArray(dados.conversas)) {
            estado = {
                conversas: dados.conversas,
                ativa: dados.ativa || null
            };
        }
    } catch (erro) {
        console.warn("Não foi possível ler o histórico salvo:", erro);
    }
}

function salvarEstado() {
    try {
        localStorage.setItem(CHAVE_STORAGE, JSON.stringify(estado));
    } catch (erro) {
        console.warn("Não foi possível salvar o histórico:", erro);
    }
}


// ========================================
// CONVERSAS
// ========================================

function criarId() {
    if (window.crypto && typeof crypto.randomUUID === "function") {
        return crypto.randomUUID();
    }

    // Fallback para acesso via HTTP fora de localhost
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
}

function ordenarConversas() {
    estado.conversas.sort((a, b) => b.atualizadaEm - a.atualizadaEm);
}

function conversaAtiva() {
    return estado.conversas.find(c => c.id === estado.ativa) || null;
}

function novaConversa() {
    // Reaproveita uma conversa vazia em vez de empilhar várias
    const vazia = estado.conversas.find(c => c.mensagens.length === 0);

    if (vazia) {
        vazia.atualizadaEm = Date.now();
        abrirConversa(vazia.id);
        return;
    }

    const agora = Date.now();

    estado.conversas.unshift({
        id: criarId(),
        titulo: "Nova conversa",
        criadaEm: agora,
        atualizadaEm: agora,
        mensagens: []
    });

    ordenarConversas();

    if (estado.conversas.length > MAX_CONVERSAS) {
        estado.conversas = estado.conversas.slice(0, MAX_CONVERSAS);
    }

    abrirConversa(estado.conversas[0].id);
}

function abrirConversa(id) {
    estado.ativa = id;

    salvarEstado();
    renderizarMensagens();
    renderizarLista();

    // No celular, focar abriria o teclado sem o usuário pedir
    if (!estaNoCelular()) {
        input.focus();
    }
}

function apagarConversa(id) {
    if (!confirm("Apagar esta conversa?")) {
        return;
    }

    fetch(`/chat/${encodeURIComponent(id)}`, {
        method: "DELETE"
    }).catch(() => { });

    estado.conversas = estado.conversas.filter(c => c.id !== id);

    if (estado.ativa === id) {
        estado.ativa = null;

        ordenarConversas();

        if (estado.conversas.length > 0) {
            abrirConversa(estado.conversas[0].id);
        } else {
            novaConversa();
        }

        return;
    }

    salvarEstado();
    renderizarLista();
}

function registrarMensagem(conversa, tipo, texto, miniatura) {
    const registro = {
        tipo: tipo,
        texto: texto
    };

    if (miniatura) {
        registro.miniatura = miniatura;
    }

    conversa.mensagens.push(registro);
    conversa.atualizadaEm = Date.now();

    // A primeira mensagem do usuário vira o título da conversa
    if (tipo === "usuario" && conversa.titulo === "Nova conversa") {
        const base = texto || "Imagem";

        conversa.titulo = base.length > 40
            ? base.slice(0, 40).trim() + "…"
            : base;
    }

    salvarEstado();
    renderizarLista();
}


// ========================================
// LISTA LATERAL (HISTÓRICO)
// ========================================

function rotuloDoGrupo(timestamp) {
    const dia = 24 * 60 * 60 * 1000;

    const inicioHoje = new Date().setHours(0, 0, 0, 0);
    const inicioDaConversa = new Date(timestamp).setHours(0, 0, 0, 0);

    const diferenca = inicioHoje - inicioDaConversa;

    if (diferenca <= 0) return "Hoje";
    if (diferenca <= dia) return "Ontem";
    if (diferenca <= 7 * dia) return "Últimos 7 dias";

    return "Mais antigas";
}

function renderizarLista() {
    ordenarConversas();

    lista.innerHTML = "";

    let grupoAtual = null;

    estado.conversas.forEach(conversa => {
        const grupo = rotuloDoGrupo(conversa.atualizadaEm);

        if (grupo !== grupoAtual) {
            grupoAtual = grupo;

            const titulo = document.createElement("div");
            titulo.classList.add("grupo-titulo");
            titulo.textContent = grupo;

            lista.appendChild(titulo);
        }

        const item = document.createElement("div");
        item.classList.add("item-conversa");

        if (conversa.id === estado.ativa) {
            item.classList.add("ativa");
        }

        const abrir = document.createElement("button");
        abrir.type = "button";
        abrir.classList.add("item-titulo");
        abrir.textContent = conversa.titulo;
        abrir.title = conversa.titulo;

        abrir.addEventListener("click", () => {
            abrirConversa(conversa.id);
            fecharSidebarNoCelular();
        });

        const apagar = document.createElement("button");
        apagar.type = "button";
        apagar.classList.add("item-apagar");
        apagar.textContent = "×";
        apagar.title = "Apagar conversa";
        apagar.setAttribute("aria-label", "Apagar conversa: " + conversa.titulo);

        apagar.addEventListener("click", () => {
            apagarConversa(conversa.id);
        });

        item.appendChild(abrir);
        item.appendChild(apagar);

        lista.appendChild(item);
    });
}


// ========================================
// SIDEBAR (ABRIR / FECHAR)
// ========================================

function estaNoCelular() {
    return window.matchMedia("(max-width: 800px)").matches;
}

function alternarSidebar() {
    document.body.classList.toggle(
        estaNoCelular() ? "sidebar-aberta" : "sidebar-fechada"
    );
}

function fecharSidebarNoCelular() {
    document.body.classList.remove("sidebar-aberta");
}


// ========================================
// CÓPIA DE TEXTO
// ========================================

// Tenta usar a Clipboard API e oferece uma alternativa para navegadores
// que não permitem navigator.clipboard.writeText().
async function copiarTexto(texto) {
    if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(texto);
        return;
    }

    const temporario = document.createElement("textarea");

    temporario.value = texto;
    temporario.setAttribute("readonly", "");
    temporario.style.position = "fixed";
    temporario.style.left = "-9999px";
    temporario.style.top = "0";

    document.body.appendChild(temporario);
    temporario.select();

    let copiou = false;

    try {
        copiou = document.execCommand("copy");
    } finally {
        temporario.remove();
    }

    if (!copiou) {
        throw new Error("O navegador não permitiu copiar o texto.");
    }
}


// ========================================
// ÍCONES DAS AÇÕES DAS RESPOSTAS
// ========================================

// Cria SVGs diretamente pelo JavaScript, sem bibliotecas externas
// e sem inserir HTML recebido da IA.
function criarIcone(nome) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");

    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "18");
    svg.setAttribute("height", "18");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.8");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    svg.classList.add("icone-acao");

    const criarElemento = (tipo, atributos) => {
        const elemento = document.createElementNS(
            "http://www.w3.org/2000/svg",
            tipo
        );

        Object.entries(atributos).forEach(([chave, valor]) => {
            elemento.setAttribute(chave, valor);
        });

        return elemento;
    };

    if (nome === "copiar") {
        svg.append(
            criarElemento("rect", {
                x: "8",
                y: "8",
                width: "13",
                height: "13",
                rx: "2"
            }),
            criarElemento("path", {
                d: "M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"
            })
        );
    }

    if (nome === "regenerar") {
        svg.append(
            criarElemento("path", {
                d: "M20 7v5h-5"
            }),
            criarElemento("path", {
                d: "M4 17v-5h5"
            }),
            criarElemento("path", {
                d: "M5.5 9a7 7 0 0 1 11.6-2.6L20 12"
            }),
            criarElemento("path", {
                d: "M4 12l2.9 5.6A7 7 0 0 0 18.5 15"
            })
        );
    }

    if (nome === "compartilhar") {
        svg.append(
            criarElemento("circle", {
                cx: "18",
                cy: "5",
                r: "3"
            }),
            criarElemento("circle", {
                cx: "6",
                cy: "12",
                r: "3"
            }),
            criarElemento("circle", {
                cx: "18",
                cy: "19",
                r: "3"
            }),
            criarElemento("path", {
                d: "m8.7 10.5 6.6-4"
            }),
            criarElemento("path", {
                d: "m8.7 13.5 6.6 4"
            })
        );
    }

    return svg;
}

// Botão somente com ícone, mantendo nome acessível e dica ao passar o mouse.
function criarBotaoAcao(nomeIcone, descricao, classeAdicional = "") {
    const botaoAcao = document.createElement("button");

    botaoAcao.type = "button";
    botaoAcao.classList.add("copy-button", "message-action-button");

    if (classeAdicional) {
        botaoAcao.classList.add(classeAdicional);
    }

    botaoAcao.setAttribute("aria-label", descricao);
    botaoAcao.title = descricao;

    botaoAcao.appendChild(criarIcone(nomeIcone));

    return botaoAcao;
}


// ========================================
// BLOCOS DE CÓDIGO NAS RESPOSTAS
// ========================================

// Cria um botão de cópia para cada bloco de código.
function criarBlocoCodigo(codigo, linguagem) {
    const bloco = document.createElement("div");
    bloco.classList.add("code-block");

    const cabecalho = document.createElement("div");
    cabecalho.classList.add("code-block-header");

    const nomeLinguagem = document.createElement("span");
    nomeLinguagem.classList.add("code-block-language");
    nomeLinguagem.textContent = linguagem || "código";

    const copiar = document.createElement("button");
    copiar.type = "button";
    copiar.classList.add("copy-button", "code-copy-button");
    copiar.textContent = "Copiar código";
    copiar.title = "Copiar este bloco de código";

    copiar.addEventListener("click", async () => {
        try {
            await copiarTexto(codigo);

            copiar.textContent = "Copiado!";

            setTimeout(() => {
                copiar.textContent = "Copiar código";
            }, 1500);
        } catch (erro) {
            console.error("Não foi possível copiar o código:", erro);
            mostrarAviso("Não foi possível copiar o código.");
        }
    });

    cabecalho.appendChild(nomeLinguagem);
    cabecalho.appendChild(copiar);

    const pre = document.createElement("pre");
    const code = document.createElement("code");

    // textContent impede que conteúdo retornado pela IA seja interpretado como HTML.
    code.textContent = codigo;

    if (linguagem) {
        code.classList.add("language-" + linguagem);
    }

    pre.appendChild(code);

    bloco.appendChild(cabecalho);
    bloco.appendChild(pre);

    return bloco;
}

// Interpreta cercas Markdown de código sem usar innerHTML.
// O conteúdo da resposta é sempre inserido como texto, de forma segura.
function renderizarTextoComCodigo(conteudo, destino) {
    const texto = String(conteudo ?? "");
    const regex = /```([^\n`]*)\r?\n([\s\S]*?)```/g;

    let posicao = 0;
    let resultado;

    while ((resultado = regex.exec(texto)) !== null) {
        // Texto comum que aparece antes do bloco de código
        if (resultado.index > posicao) {
            const parteTexto = document.createElement("div");

            parteTexto.classList.add("texto-resposta");
            parteTexto.textContent = texto.slice(posicao, resultado.index);
            parteTexto.style.whiteSpace = "pre-wrap";
            parteTexto.style.overflowWrap = "anywhere";

            destino.appendChild(parteTexto);
        }

        const linguagem = resultado[1].trim().split(/\s+/)[0] || "";
        const codigo = resultado[2].replace(/\n$/, "");

        destino.appendChild(criarBlocoCodigo(codigo, linguagem));

        posicao = regex.lastIndex;
    }

    // Texto que aparece depois do último bloco
    if (posicao < texto.length) {
        const parteTexto = document.createElement("div");

        parteTexto.classList.add("texto-resposta");
        parteTexto.textContent = texto.slice(posicao);
        parteTexto.style.whiteSpace = "pre-wrap";
        parteTexto.style.overflowWrap = "anywhere";

        destino.appendChild(parteTexto);
    }

    // Resposta vazia: mantém um elemento no lugar do conteúdo.
    if (!texto) {
        const vazio = document.createElement("div");
        vazio.classList.add("texto-resposta");
        destino.appendChild(vazio);
    }
}


// ========================================
// MENSAGENS NA TELA
// ========================================

function rolarParaOFim() {
    chat.scrollTop = chat.scrollHeight;
}

function desenharMensagem(texto, tipo, miniatura, opcoes = {}) {
    const mensagem = document.createElement("div");

    mensagem.classList.add("message");

    if (tipo === "usuario") {
        mensagem.classList.add("user-message");

        if (miniatura) {
            const imagem = document.createElement("img");

            imagem.src = miniatura;
            imagem.alt = "Imagem enviada";
            imagem.classList.add("anexo");

            mensagem.appendChild(imagem);
        }

        if (texto) {
            const textoUsuario = document.createElement("div");

            textoUsuario.textContent = texto;

            mensagem.appendChild(textoUsuario);
        }
    } else {
        mensagem.classList.add("pyxie-message");

        // Resposta com suporte a blocos de código
        const textoMensagem = document.createElement("div");
        textoMensagem.classList.add("conteudo-resposta");

        renderizarTextoComCodigo(texto, textoMensagem);

        // Ações abaixo da resposta
        const acoes = document.createElement("div");
        acoes.classList.add("acoes");

        // Copiar a resposta inteira
        const copiar = criarBotaoAcao("copiar", "Copiar resposta");

        copiar.addEventListener("click", async () => {
            try {
                await copiarTexto(String(texto ?? ""));

                copiar.title = "Resposta copiada";
                copiar.setAttribute("aria-label", "Resposta copiada");

                mostrarAviso("Resposta copiada!");

                setTimeout(() => {
                    copiar.title = "Copiar resposta";
                    copiar.setAttribute("aria-label", "Copiar resposta");
                }, 1500);
            } catch (erro) {
                console.error("Não foi possível copiar:", erro);
                mostrarAviso("Não foi possível copiar a resposta.");
            }
        });

        acoes.appendChild(copiar);

        // Regenerar somente quando esta for a última resposta salva.
        if (opcoes.permitirRegenerar === true && opcoes.conversaId) {
            const regenerar = criarBotaoAcao(
                "regenerar",
                "Gerar outra resposta",
                "regenerate-button"
            );

            regenerar.addEventListener("click", () => {
                regenerarResposta(opcoes.conversaId);
            });

            acoes.appendChild(regenerar);
        }

// Compartilhar esta resposta em redes sociais e aplicativos.
if (opcoes.conversaId) {
    const compartilhar = criarBotaoAcao(
        "compartilhar",
        "Compartilhar resposta"
    );

    compartilhar.addEventListener("click", () => {
        abrirMenuCompartilhamento(String(texto ?? ""));
    });

    acoes.appendChild(compartilhar);
}

        mensagem.appendChild(textoMensagem);
        mensagem.appendChild(acoes);
    }

    chat.appendChild(mensagem);

    rolarParaOFim();
}

function renderizarMensagens() {
    chat.innerHTML = "";

    // A saudação aparece no topo de toda conversa, mas não é salva nem enviada.
    desenharMensagem(SAUDACAO, "pyxie");

    const conversa = conversaAtiva();

    if (!conversa) {
        return;
    }

    conversa.mensagens.forEach((m, indice) => {
        const ehUltimaMensagem =
            indice === conversa.mensagens.length - 1;

        const temPerguntaAnterior = conversa.mensagens
            .slice(0, indice)
            .some(anterior => anterior.tipo === "usuario");

        const permitirRegenerar =
            ehUltimaMensagem &&
            m.tipo === "pyxie" &&
            temPerguntaAnterior;

        desenharMensagem(m.texto, m.tipo, m.miniatura, {
            permitirRegenerar: permitirRegenerar,
            conversaId: m.tipo === "pyxie" ? conversa.id : null
        });
    });

    // Se voltou para uma conversa que ainda espera resposta
    if (pendenteId === conversa.id) {
        criarIndicador();
    }
}


// ========================================
// REGENERAR ÚLTIMA RESPOSTA
// ========================================

async function regenerarResposta(conversaId) {
    // Impede requisições simultâneas.
    if (pendenteId) {
        return;
    }

    const conversa = estado.conversas.find(c => c.id === conversaId);

    if (!conversa || !Array.isArray(conversa.mensagens)) {
        mostrarAviso("Não encontrei essa conversa.");
        return;
    }

    const ultimaMensagem = conversa.mensagens[conversa.mensagens.length - 1];

    // A última mensagem precisa ser uma resposta da PYXIE.
    if (!ultimaMensagem || ultimaMensagem.tipo !== "pyxie") {
        mostrarAviso("Não há uma resposta recente para regenerar.");
        return;
    }

    const temPergunta = conversa.mensagens
        .slice(0, -1)
        .some(m => m.tipo === "usuario");

    if (!temPergunta) {
        mostrarAviso("Não encontrei a pergunta que originou essa resposta.");
        return;
    }

    pendenteId = conversa.id;
    definirCarregando(true);

    if (estado.ativa === conversa.id) {
        criarIndicador();
    }

    try {
        const resposta = await fetch(
            `/regenerar/${encodeURIComponent(conversa.id)}`,
            {
                method: "POST"
            }
        );

        let dados = {};

        try {
            dados = await resposta.json();
        } catch (_) {
            dados = {};
        }

        if (!resposta.ok) {
            throw new Error(
                dados.detail ||
                dados.erro ||
                `A API retornou o erro HTTP ${resposta.status}.`
            );
        }

        if (!dados.resposta || typeof dados.resposta !== "string") {
            throw new Error("A API não retornou uma resposta válida.");
        }

        // A conversa pode ter sido apagada durante a requisição.
        if (!estado.conversas.includes(conversa)) {
            mostrarAviso("A conversa foi removida antes de a resposta terminar.");
            return;
        }

        const ultimaAtual = conversa.mensagens[conversa.mensagens.length - 1];

        // Evita substituir uma mensagem que tenha mudado durante a requisição.
        if (ultimaAtual !== ultimaMensagem) {
            mostrarAviso("A conversa mudou durante a regeneração. Tente novamente.");
            return;
        }

        // Substitui a resposta anterior; não adiciona outra mensagem.
        ultimaMensagem.texto = dados.resposta;
        conversa.atualizadaEm = Date.now();

        salvarEstado();
        renderizarLista();

        if (dados.uso) {
            atualizarPainelUso(dados.uso);
        }

    } catch (erro) {
        console.error("Erro ao regenerar a resposta:", erro);

        mostrarAviso(
            erro.message ||
            "Não foi possível regenerar a resposta."
        );
    } finally {
        pendenteId = null;

        removerIndicador();
        definirCarregando(false);

        // Atualiza a conversa que estiver aberta, sem trocar a seleção atual.
        if (conversaAtiva()) {
            renderizarMensagens();
        }
    }
}

// ========================================
// COMPARTILHAMENTO DE RESPOSTAS
// ========================================

function fecharMenuCompartilhamento() {
    const menu = document.getElementById("menu-compartilhamento-pyxie");

    if (menu) {
        menu.remove();
    }

    document.removeEventListener(
        "keydown",
        tratarTeclaMenuCompartilhamento
    );
}

function tratarTeclaMenuCompartilhamento(event) {
    if (event.key === "Escape") {
        fecharMenuCompartilhamento();
    }
}

function criarOpcaoCompartilhamento({
    nome,
    descricao,
    icone,
    cor,
    acao
}) {
    const botaoOpcao = document.createElement("button");

    botaoOpcao.type = "button";
    botaoOpcao.style.cssText = `
        display: flex;
        align-items: center;
        gap: 12px;
        width: 100%;
        padding: 12px;
        border: 1px solid #2a2a2a;
        border-radius: 10px;
        background: #111;
        color: #ececec;
        text-align: left;
        cursor: pointer;
        font: inherit;
        transition: background .15s, border-color .15s;
    `;

    botaoOpcao.addEventListener("mouseenter", () => {
        botaoOpcao.style.background = "#202020";
        botaoOpcao.style.borderColor = "#444";
    });

    botaoOpcao.addEventListener("mouseleave", () => {
        botaoOpcao.style.background = "#111";
        botaoOpcao.style.borderColor = "#2a2a2a";
    });

    const simbolo = document.createElement("span");

    simbolo.textContent = icone;
    simbolo.style.cssText = `
        display: flex;
        align-items: center;
        justify-content: center;
        width: 38px;
        height: 38px;
        flex-shrink: 0;
        border-radius: 10px;
        background: ${cor};
        color: white;
        font-size: 18px;
        font-weight: 700;
    `;

    const textos = document.createElement("span");

    textos.style.cssText = `
        display: flex;
        flex-direction: column;
        gap: 3px;
        min-width: 0;
    `;

    const titulo = document.createElement("strong");
    titulo.textContent = nome;
    titulo.style.cssText = "font-size: 14px; font-weight: 600;";

    const subtitulo = document.createElement("span");
    subtitulo.textContent = descricao;
    subtitulo.style.cssText = `
        color: #999;
        font-size: 12px;
        line-height: 1.4;
    `;

    textos.append(titulo, subtitulo);
    botaoOpcao.append(simbolo, textos);

    botaoOpcao.addEventListener("click", () => {
        fecharMenuCompartilhamento();
        acao();
    });

    return botaoOpcao;
}

function abrirDestinoCompartilhamento(url) {
    const novaJanela = window.open(
        url,
        "_blank",
        "noopener,noreferrer"
    );

    if (!novaJanela) {
        mostrarAviso(
            "O navegador bloqueou a janela. Permita pop-ups para este site e tente novamente."
        );
    }
}

async function compartilharTextoNativo(texto) {
    if (typeof navigator.share !== "function") {
        mostrarAviso(
            "O compartilhamento do dispositivo não está disponível neste navegador. Escolha WhatsApp ou Telegram, ou copie o texto."
        );
        return;
    }

    try {
        await navigator.share({
            title: "Resposta da PYXIE",
            text: texto
        });
    } catch (erro) {
        // O usuário pode fechar o menu nativo sem compartilhar.
        if (erro.name !== "AbortError") {
            console.error("Erro no compartilhamento:", erro);
            mostrarAviso("Não foi possível abrir o compartilhamento.");
        }
    }
}

async function copiarTextoCompartilhamento(texto) {
    try {
        await copiarTexto(texto);
        mostrarAviso("Resposta copiada!");
    } catch (erro) {
        console.error("Erro ao copiar resposta:", erro);
        mostrarAviso("Não foi possível copiar a resposta.");
    }
}

function abrirMenuCompartilhamento(texto) {
    fecharMenuCompartilhamento();

    const conteudo = String(texto || "").trim();

    if (!conteudo) {
        mostrarAviso("Não há conteúdo para compartilhar.");
        return;
    }

    const overlayMenu = document.createElement("div");
    overlayMenu.id = "menu-compartilhamento-pyxie";

    overlayMenu.style.cssText = `
        position: fixed;
        inset: 0;
        z-index: 1000;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 16px;
        background: rgba(0, 0, 0, .75);
        backdrop-filter: blur(4px);
    `;

    const painel = document.createElement("div");

    painel.setAttribute("role", "dialog");
    painel.setAttribute("aria-modal", "true");
    painel.setAttribute("aria-labelledby", "titulo-compartilhamento-pyxie");

    painel.style.cssText = `
        width: 100%;
        max-width: 420px;
        max-height: 85vh;
        overflow-y: auto;
        padding: 20px;
        border: 1px solid #333;
        border-radius: 16px;
        background: #080808;
        color: #ececec;
        box-shadow: 0 20px 60px rgba(0, 0, 0, .5);
    `;

    const cabecalho = document.createElement("div");

    cabecalho.style.cssText = `
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 8px;
    `;

    const titulo = document.createElement("h2");
    titulo.id = "titulo-compartilhamento-pyxie";
    titulo.textContent = "Compartilhar resposta";
    titulo.style.cssText = "font-size: 19px; font-weight: 650;";

    const fechar = document.createElement("button");

    fechar.type = "button";
    fechar.textContent = "×";
    fechar.title = "Fechar";
    fechar.setAttribute("aria-label", "Fechar compartilhamento");

    fechar.style.cssText = `
        width: 32px;
        height: 32px;
        flex-shrink: 0;
        border: none;
        border-radius: 8px;
        background: transparent;
        color: #aaa;
        font-size: 25px;
        cursor: pointer;
    `;

    fechar.addEventListener("click", fecharMenuCompartilhamento);

    cabecalho.append(titulo, fechar);

    const descricao = document.createElement("p");
    descricao.textContent = "Escolha onde deseja enviar o texto.";
    descricao.style.cssText = `
        margin-bottom: 16px;
        color: #999;
        font-size: 13px;
        line-height: 1.5;
    `;

    const opcoes = document.createElement("div");

    opcoes.style.cssText = `
        display: flex;
        flex-direction: column;
        gap: 8px;
    `;

    // WhatsApp: abre a seleção de contatos com o texto preparado.
    opcoes.appendChild(criarOpcaoCompartilhamento({
        nome: "WhatsApp",
        descricao: "Enviar para um contato ou grupo",
        icone: "W",
        cor: "#128C4A",
        acao: () => {
            const url =
                "https://wa.me/?text=" + encodeURIComponent(conteudo);

            abrirDestinoCompartilhamento(url);
        }
    }));

    // Telegram: abre o fluxo de compartilhamento com o texto.
    opcoes.appendChild(criarOpcaoCompartilhamento({
        nome: "Telegram",
        descricao: "Escolher uma conversa para enviar",
        icone: "➤",
        cor: "#229ED9",
        acao: () => {
            const url =
                "https://t.me/share/url?url=&text=" +
                encodeURIComponent(conteudo);

            abrirDestinoCompartilhamento(url);
        }
    }));

    // LinkedIn: o compartilhamento web oficial exige um URL.
    // Não existe um parâmetro universal para preencher uma publicação
    // apenas com texto. Por isso, copiamos o texto e abrimos o LinkedIn.
    opcoes.appendChild(criarOpcaoCompartilhamento({
        nome: "LinkedIn",
        descricao: "Copiar o texto e abrir o LinkedIn",
        icone: "in",
        cor: "#0A66C2",
        acao: async () => {
            try {
                await copiarTexto(conteudo);
                abrirDestinoCompartilhamento(
                    "https://www.linkedin.com/feed/"
                );
                mostrarAviso(
                    "Texto copiado. No LinkedIn, cole-o em uma publicação."
                );
            } catch (erro) {
                mostrarAviso(
                    "Não foi possível copiar o texto para o LinkedIn."
                );
            }
        }
    }));

    // Reddit: abre o formulário de publicação com título e texto.
    opcoes.appendChild(criarOpcaoCompartilhamento({
        nome: "Reddit",
        descricao: "Preparar uma publicação de texto",
        icone: "r/",
        cor: "#FF4500",
        acao: () => {
            const primeiraLinha = conteudo
                .split("\n")
                .map(linha => linha.trim())
                .find(Boolean) || "Resposta da PYXIE";

            const tituloReddit = primeiraLinha.length > 200
                ? primeiraLinha.slice(0, 197) + "..."
                : primeiraLinha;

            const parametros = new URLSearchParams({
                type: "TEXT",
                title: tituloReddit,
                text: conteudo
            });

            abrirDestinoCompartilhamento(
                "https://www.reddit.com/submit?" + parametros.toString()
            );
        }
    }));

    // O Instagram não permite preencher qualquer chat com texto
    // por um link web universal. O menu nativo pode oferecer o app
    // se o sistema e o navegador permitirem.
    opcoes.appendChild(criarOpcaoCompartilhamento({
        nome: "Instagram e outros aplicativos",
        descricao: "Abrir o menu de compartilhamento do dispositivo",
        icone: "↗",
        cor: "#C13584",
        acao: () => compartilharTextoNativo(conteudo)
    }));

    opcoes.appendChild(criarOpcaoCompartilhamento({
        nome: "Copiar texto",
        descricao: "Copiar a resposta para colar onde quiser",
        icone: "▢",
        cor: "#333333",
        acao: () => copiarTextoCompartilhamento(conteudo)
    }));

    painel.append(cabecalho, descricao, opcoes);
    overlayMenu.appendChild(painel);

    overlayMenu.addEventListener("click", event => {
        if (event.target === overlayMenu) {
            fecharMenuCompartilhamento();
        }
    });

    document.body.appendChild(overlayMenu);

    document.addEventListener(
        "keydown",
        tratarTeclaMenuCompartilhamento
    );

    fechar.focus();
}

// ========================================
// INDICADOR DE PROCESSAMENTO
// ========================================

function criarIndicador() {
    if (document.getElementById("indicador")) {
        return;
    }

    const indicador = document.createElement("div");

    indicador.classList.add(
        "message",
        "pyxie-message",
        "digitando"
    );

    indicador.id = "indicador";

    indicador.setAttribute("role", "status");
    indicador.setAttribute("aria-label", "PYXIE está pensando");

    indicador.innerHTML = "<span></span><span></span><span></span>";

    chat.appendChild(indicador);

    rolarParaOFim();
}

function removerIndicador() {
    const indicador = document.getElementById("indicador");

    if (indicador) {
        indicador.remove();
    }
}


// ========================================
// AVISOS
// ========================================

function mostrarAviso(texto) {
    if (!aviso) {
        console.warn(texto);
        return;
    }

    aviso.textContent = texto;
    aviso.hidden = false;

    clearTimeout(timerAviso);

    timerAviso = setTimeout(() => {
        aviso.hidden = true;
    }, 5000);
}


// ========================================
// IMAGENS
// ========================================

// Abre um arquivo de imagem como elemento <img>
function carregarImagem(arquivo) {
    return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(arquivo);
        const imagem = new Image();

        imagem.onload = () => {
            URL.revokeObjectURL(url);
            resolve(imagem);
        };

        imagem.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error("Não foi possível decodificar a imagem."));
        };

        imagem.src = url;
    });
}

// Redimensiona imagem ou frame de vídeo e devolve JPEG em data URL
function reduzirImagem(fonte, largura, altura, ladoMaximo, qualidade) {
    const escala = Math.min(1, ladoMaximo / Math.max(largura, altura));

    const canvas = document.createElement("canvas");

    canvas.width = Math.max(1, Math.round(largura * escala));
    canvas.height = Math.max(1, Math.round(altura * escala));

    const ctx = canvas.getContext("2d");

    // PNG com transparência viraria fundo preto em JPEG
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.drawImage(fonte, 0, 0, canvas.width, canvas.height);

    return canvas.toDataURL("image/jpeg", qualidade);
}

function definirImagemPendente(fonte, largura, altura) {
    if (!largura || !altura) {
        mostrarAviso("Não consegui ler essa imagem.");
        return;
    }

    imagemPendente = {
        dataUrl: reduzirImagem(
            fonte,
            largura,
            altura,
            IMAGEM_LADO_MAX,
            IMAGEM_QUALIDADE
        ),
        miniatura: reduzirImagem(
            fonte,
            largura,
            altura,
            MINIATURA_LADO_MAX,
            MINIATURA_QUALIDADE
        )
    };

    renderizarPrevia();

    if (!estaNoCelular()) {
        input.focus();
    }
}

function renderizarPrevia() {
    if (imagemPendente) {
        previaImg.src = imagemPendente.miniatura;
        previa.hidden = false;

        input.placeholder = PLACEHOLDER_COM_IMAGEM;
    } else {
        previa.hidden = true;
        previaImg.removeAttribute("src");

        input.placeholder = PLACEHOLDER_PADRAO;
    }
}

function removerImagemPendente() {
    imagemPendente = null;

    renderizarPrevia();
}

// Ponto de entrada comum: seletor de arquivo, colar, arrastar
async function adicionarArquivo(arquivo) {
    if (!arquivo) {
        return;
    }

    if (!arquivo.type.startsWith("image/")) {
        mostrarAviso("Por enquanto só imagens são aceitas (JPG, PNG, WebP...).");
        return;
    }

    if (arquivo.size > MAX_ARQUIVO_MB * 1024 * 1024) {
        mostrarAviso(`A imagem passa de ${MAX_ARQUIVO_MB} MB.`);
        return;
    }

    try {
        const imagem = await carregarImagem(arquivo);

        definirImagemPendente(
            imagem,
            imagem.naturalWidth,
            imagem.naturalHeight
        );
    } catch (erro) {
        console.error("Erro ao abrir imagem:", erro);

        mostrarAviso("Não consegui abrir essa imagem. Tente um arquivo JPG ou PNG.");
    }
}


// ========================================
// CÂMERA
// ========================================

function mensagemErroCamera(erro) {
    switch (erro && erro.name) {
        case "NotAllowedError":
        case "SecurityError":
            return "O acesso à câmera foi negado. Libere a câmera para este site nas configurações do navegador.";

        case "NotFoundError":
        case "OverconstrainedError":
            return "Nenhuma câmera foi encontrada neste dispositivo.";

        case "NotReadableError":
            return "A câmera está sendo usada por outro aplicativo.";

        default:
            return "Não foi possível abrir a câmera.";
    }
}

function pararCamera() {
    if (streamCamera) {
        streamCamera.getTracks().forEach(faixa => faixa.stop());

        streamCamera = null;
    }

    cameraVideo.srcObject = null;
}

async function iniciarCamera() {
    pararCamera();

    cameraErro.textContent = "";
    cameraCapturar.disabled = true;

    try {
        streamCamera = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: cameraFrontal ? "user" : "environment",
                width: { ideal: 1280 },
                height: { ideal: 720 }
            },
            audio: false
        });

        cameraVideo.srcObject = streamCamera;

        // Espelha só a prévia da câmera frontal / webcam.
        const config = streamCamera.getVideoTracks()[0].getSettings();

        cameraVideo.classList.toggle(
            "espelhado",
            config.facingMode !== "environment"
        );

        cameraCapturar.disabled = false;
    } catch (erro) {
        console.error("Erro ao abrir a câmera:", erro);

        cameraErro.textContent = mensagemErroCamera(erro);
    }
}

async function abrirCamera() {
    // Fallback para a câmera nativa do celular
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        inputArquivoCamera.click();
        return;
    }

    cameraModal.hidden = false;

    await iniciarCamera();

    cameraCapturar.focus();
}

function fecharCamera() {
    // Fecha o stream: a luz da câmera apaga assim que o painel fecha.
    pararCamera();

    cameraModal.hidden = true;
    cameraErro.textContent = "";

    botaoCamera.focus();
}

function capturarFoto() {
    const largura = cameraVideo.videoWidth;
    const altura = cameraVideo.videoHeight;

    if (!largura || !altura) {
        cameraErro.textContent = "A câmera ainda não está pronta. Tente de novo.";
        return;
    }

    definirImagemPendente(cameraVideo, largura, altura);

    fecharCamera();
}


// ========================================
// ENVIAR MENSAGEM
// ========================================

function definirCarregando(carregando) {
    input.disabled = carregando;
    botao.disabled = carregando;
    botaoAnexar.disabled = carregando;
    botaoCamera.disabled = carregando;
}

async function enviarMensagem() {
    const texto = input.value.trim();
    const imagem = imagemPendente;

    // Não envia mensagem vazia nem enquanto espera resposta.
    if ((!texto && !imagem) || pendenteId) {
        return;
    }

    const conversa = conversaAtiva();

    if (!conversa) {
        return;
    }

    // Contexto: mensagens anteriores à atual.
    // Imagens antigas não são reenviadas: só o texto delas.
    const historico = conversa.mensagens
        .slice(-MENSAGENS_DE_CONTEXTO)
        .map(m => ({
            role: m.tipo === "usuario" ? "user" : "assistant",
            content: m.texto || "[imagem enviada]"
        }));

    const miniatura = imagem ? imagem.miniatura : null;

    registrarMensagem(conversa, "usuario", texto, miniatura);
    desenharMensagem(texto, "usuario", miniatura);

    // Limpa campo e anexo
    input.value = "";
    removerImagemPendente();

    // Desativa controles enquanto processa
    pendenteId = conversa.id;

    definirCarregando(true);
    criarIndicador();

    let respostaTexto = null;
    let deuErro = false;

    try {
        const resposta = await fetch("/perguntar", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                mensagem: texto,
                chat_id: conversa.id,
                historico: historico,
                imagem: imagem ? imagem.dataUrl : null
            })
        });

        if (!resposta.ok) {
            throw new Error(`Erro HTTP: ${resposta.status}`);
        }

        const dados = await resposta.json();

        if (!dados.resposta) {
            throw new Error("A API não retornou uma resposta válida.");
        }

        respostaTexto = dados.resposta;

        if (dados.uso) {
            atualizarPainelUso(dados.uso);
        }
    } catch (erro) {
        console.error("Erro ao conversar com a PYXIE:", erro);

        deuErro = true;
    } finally {
        pendenteId = null;

        removerIndicador();

        // Reativa controles
        definirCarregando(false);
    }

    // A conversa pode ter sido apagada enquanto esperava.
    const aindaExiste = estado.conversas.includes(conversa);

    // Só desenha se o usuário ainda está olhando para essa conversa.
    const visivel = estado.ativa === conversa.id;

    if (deuErro) {
        // Erros aparecem na tela, mas não entram no histórico.
        if (visivel) {
            desenharMensagem(
                "Desculpe, ocorreu um erro ao tentar falar comigo.",
                "pyxie"
            );
        }
    } else if (aindaExiste) {
        registrarMensagem(conversa, "pyxie", respostaTexto);

        if (visivel) {
            // Redesenha para habilitar o botão de regeneração na última resposta.
            renderizarMensagens();
        }
    }

    // Volta o foco para o campo
    input.focus();
}


// ========================================
// PAINEL DE USO (GROQ)
// ========================================

const botaoUso = document.getElementById("uso-toggle");
const painelUso = document.getElementById("painel-uso");
const overlayUso = document.getElementById("overlay-uso");

function estaNoCelularUso() {
    return window.matchMedia("(max-width: 800px)").matches;
}

function alternarPainelUso() {
    document.body.classList.toggle(
        estaNoCelularUso() ? "uso-aberta" : "uso-fechada"
    );
}

function fecharPainelUsoNoCelular() {
    document.body.classList.remove("uso-aberta");
}

function formatarNumero(n) {
    if (n === null || n === undefined) return "—";
    return n.toLocaleString("pt-BR");
}

function atualizarBarra(barraEl, restante, limite) {
    if (
        limite === null ||
        limite === undefined ||
        limite === 0 ||
        restante === null
    ) {
        barraEl.style.width = "0%";
        return;
    }

    const pct = Math.max(0, Math.min(100, (restante / limite) * 100));

    barraEl.style.width = pct + "%";

    // Fica amarelo/vermelho quando o uso está baixo.
    barraEl.classList.toggle("barra-atencao", pct <= 25 && pct > 10);
    barraEl.classList.toggle("barra-critica", pct <= 10);
}

function atualizarPainelUso(uso) {
    if (!uso || !painelUso) return;

    const elModelo = document.getElementById("uso-modelo");
    const elTokensTexto = document.getElementById("uso-tokens-texto");
    const elTokensBarra = document.getElementById("uso-tokens-barra");
    const elTokensReset = document.getElementById("uso-tokens-reset");
    const elPedidosTexto = document.getElementById("uso-pedidos-texto");
    const elPedidosBarra = document.getElementById("uso-pedidos-barra");
    const elVazio = document.getElementById("uso-vazio");
    const elConteudo = document.getElementById("uso-conteudo");

    if (!uso.modelo) {
        // Ainda não houve nenhuma chamada à Groq nesta sessão do servidor.
        if (elVazio) elVazio.hidden = false;
        if (elConteudo) elConteudo.hidden = true;
        return;
    }

    if (elVazio) elVazio.hidden = true;
    if (elConteudo) elConteudo.hidden = false;

    if (elModelo) elModelo.textContent = uso.modelo;

    if (elTokensTexto) {
        elTokensTexto.textContent =
            formatarNumero(uso.tokens_restantes) +
            " / " +
            formatarNumero(uso.tokens_limite);
    }

    if (elTokensBarra) {
        atualizarBarra(
            elTokensBarra,
            uso.tokens_restantes,
            uso.tokens_limite
        );
    }

    if (elTokensReset && uso.tokens_reset) {
        elTokensReset.textContent = "reseta em " + uso.tokens_reset;
    }

    if (elPedidosTexto) {
        elPedidosTexto.textContent =
            formatarNumero(uso.requests_restantes) +
            " / " +
            formatarNumero(uso.requests_limite);
    }

    if (elPedidosBarra) {
        atualizarBarra(
            elPedidosBarra,
            uso.requests_restantes,
            uso.requests_limite
        );
    }
}

async function carregarUsoInicial() {
    try {
        const resposta = await fetch("/uso");

        if (!resposta.ok) return;

        const dados = await resposta.json();

        atualizarPainelUso(dados);
    } catch (erro) {
        console.warn("Não foi possível carregar o uso inicial:", erro);
    }
}

if (botaoUso) {
    botaoUso.addEventListener("click", alternarPainelUso);
}

if (overlayUso) {
    overlayUso.addEventListener("click", fecharPainelUsoNoCelular);
}


// ========================================
// EVENTOS
// ========================================

botao.addEventListener("click", enviarMensagem);

input.addEventListener("keydown", function (event) {
    // Enter envia
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();

        enviarMensagem();
    }
});

// Colar imagem (Ctrl+V / Cmd+V) no campo de texto
input.addEventListener("paste", function (event) {
    const itens = Array.from(
        (event.clipboardData && event.clipboardData.items) || []
    );

    const item = itens.find(i => i.type.startsWith("image/"));

    if (item) {
        event.preventDefault();

        adicionarArquivo(item.getAsFile());
    }
});

// Arrastar e soltar uma imagem na tela
containerChat.addEventListener("dragover", function (event) {
    event.preventDefault();

    containerChat.classList.add("arrastando");
});

containerChat.addEventListener("dragleave", function (event) {
    if (!event.relatedTarget || !containerChat.contains(event.relatedTarget)) {
        containerChat.classList.remove("arrastando");
    }
});

containerChat.addEventListener("drop", function (event) {
    event.preventDefault();

    containerChat.classList.remove("arrastando");

    if (pendenteId) {
        return;
    }

    const arquivo = event.dataTransfer && event.dataTransfer.files[0];

    adicionarArquivo(arquivo);
});

botaoAnexar.addEventListener("click", () => inputArquivo.click());

botaoCamera.addEventListener("click", abrirCamera);

function aoEscolherArquivo(event) {
    const arquivo = event.target.files[0];

    // Limpa para permitir escolher o mesmo arquivo de novo
    event.target.value = "";

    adicionarArquivo(arquivo);
}

inputArquivo.addEventListener("change", aoEscolherArquivo);
inputArquivoCamera.addEventListener("change", aoEscolherArquivo);

previaRemover.addEventListener("click", removerImagemPendente);

cameraCancelar.addEventListener("click", fecharCamera);
cameraCapturar.addEventListener("click", capturarFoto);

cameraVirar.addEventListener("click", () => {
    cameraFrontal = !cameraFrontal;

    iniciarCamera();
});

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !cameraModal.hidden) {
        fecharCamera();
    }
});

// Por privacidade, a câmera não fica ligada com a aba em segundo plano.
document.addEventListener("visibilitychange", function () {
    if (document.hidden && !cameraModal.hidden) {
        fecharCamera();
    }
});

botaoNova.addEventListener("click", () => {
    novaConversa();
    fecharSidebarNoCelular();
});

botaoLimpar.addEventListener("click", () => {
    if (!confirm("Apagar todo o histórico de conversas deste navegador?")) {
        return;
    }

    estado.conversas.forEach(c =>
        fetch(`/chat/${encodeURIComponent(c.id)}`, {
            method: "DELETE"
        }).catch(() => { })
    );

    estado = {
        conversas: [],
        ativa: null
    };

    novaConversa();
    fecharSidebarNoCelular();
});

botaoMenu.addEventListener("click", alternarSidebar);

overlay.addEventListener("click", fecharSidebarNoCelular);


// ========================================
// INICIALIZAÇÃO
// ========================================

carregarEstado();

ordenarConversas();

if (conversaAtiva()) {
    abrirConversa(estado.ativa);
} else if (estado.conversas.length > 0) {
    abrirConversa(estado.conversas[0].id);
} else {
    novaConversa();
}

// No celular o histórico começa fechado.
fecharSidebarNoCelular();

// Mostra alguma coisa no painel de uso antes da primeira mensagem.
carregarUsoInicial();