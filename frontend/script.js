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


// ========================================
// CONFIGURAÇÕES
// ========================================

const CHAVE_STORAGE = "pyxie_conversas_v1";

const SAUDACAO = "Olá! Como posso ajudar?";

// Quantas mensagens anteriores vão junto a cada pedido.
// É aqui que se controla o "custo" da memória retroativa:
// 0 = a API só recebe a mensagem atual.
const MENSAGENS_DE_CONTEXTO = 6;

const MAX_CONVERSAS = 50;

// Imagens
const MAX_ARQUIVO_MB = 15;          // recusa arquivos maiores que isso
const IMAGEM_LADO_MAX = 1280;       // a imagem enviada à API é reduzida a isso
const IMAGEM_QUALIDADE = 0.85;
const MINIATURA_LADO_MAX = 320;     // miniatura guardada no histórico do navegador
const MINIATURA_QUALIDADE = 0.6;

const PLACEHOLDER_PADRAO = input.placeholder;
const PLACEHOLDER_COM_IMAGEM = "Pergunte algo sobre a imagem (opcional)";


// ========================================
// ESTADO
// ========================================

let estado = {
    conversas: [],   // { id, titulo, criadaEm, atualizadaEm, mensagens: [{ tipo, texto, miniatura? }] }
    ativa: null
};

// id da conversa que está aguardando resposta da API
let pendenteId = null;

// imagem anexada, ainda não enviada: { dataUrl, miniatura }
let imagemPendente = null;

// câmera
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

    // Fallback para acesso via http fora de localhost
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

    const registro = { tipo: tipo, texto: texto };

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
// SIDEBAR (abrir / fechar)
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
// MENSAGENS NA TELA
// ========================================

function rolarParaOFim() {

    chat.scrollTop = chat.scrollHeight;
}

function desenharMensagem(texto, tipo, miniatura) {

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

        // Texto da resposta (sem balão)
        const textoMensagem = document.createElement("div");

        textoMensagem.textContent = texto;

        // Ações abaixo do texto
        const acoes = document.createElement("div");

        acoes.classList.add("acoes");

        const copiar = document.createElement("button");

        copiar.type = "button";
        copiar.textContent = "Copiar";
        copiar.title = "Copiar resposta";
        copiar.classList.add("copy-button");

        copiar.addEventListener("click", async () => {

            try {

                await navigator.clipboard.writeText(texto);

                copiar.textContent = "Copiado";

                setTimeout(() => {
                    copiar.textContent = "Copiar";
                }, 1500);

            } catch (erro) {

                console.error("Não foi possível copiar:", erro);

            }

        });

        acoes.appendChild(copiar);

        mensagem.appendChild(textoMensagem);
        mensagem.appendChild(acoes);
    }

    chat.appendChild(mensagem);

    rolarParaOFim();
}

function renderizarMensagens() {

    chat.innerHTML = "";

    // A saudação aparece no topo de toda conversa, mas não é salva nem enviada
    desenharMensagem(SAUDACAO, "pyxie");

    const conversa = conversaAtiva();

    if (!conversa) {
        return;
    }

    conversa.mensagens.forEach(m => {
        desenharMensagem(m.texto, m.tipo, m.miniatura);
    });

    // Se voltou para uma conversa que ainda espera resposta
    if (pendenteId === conversa.id) {
        criarIndicador();
    }
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

// Redimensiona (imagem ou frame de vídeo) e devolve um JPEG em data URL
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
        dataUrl: reduzirImagem(fonte, largura, altura, IMAGEM_LADO_MAX, IMAGEM_QUALIDADE),
        miniatura: reduzirImagem(fonte, largura, altura, MINIATURA_LADO_MAX, MINIATURA_QUALIDADE)
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

        definirImagemPendente(imagem, imagem.naturalWidth, imagem.naturalHeight);

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

        // Espelha só a prévia da câmera frontal / webcam (a foto sai normal)
        const config = streamCamera.getVideoTracks()[0].getSettings();

        cameraVideo.classList.toggle("espelhado", config.facingMode !== "environment");

        cameraCapturar.disabled = false;

    } catch (erro) {

        console.error("Erro ao abrir a câmera:", erro);

        cameraErro.textContent = mensagemErroCamera(erro);
    }
}

async function abrirCamera() {

    // Sem getUserMedia (página em http fora de localhost, navegador antigo):
    // cai para a câmera nativa do celular via <input capture>
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        inputArquivoCamera.click();
        return;
    }

    cameraModal.hidden = false;

    await iniciarCamera();

    cameraCapturar.focus();
}

function fecharCamera() {

    // Fecha o stream: a luz da câmera apaga assim que o painel fecha
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

    // Não envia mensagem vazia (texto ou imagem) nem enquanto espera resposta
    if ((!texto && !imagem) || pendenteId) {
        return;
    }

    const conversa = conversaAtiva();

    if (!conversa) {
        return;
    }

    // Contexto: mensagens ANTERIORES a esta (a atual vai em "mensagem").
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
                conversa_id: conversa.id,
                historico: historico,
                imagem: imagem ? imagem.dataUrl : null
            })

        });

        // Verifica erro HTTP
        if (!resposta.ok) {

            throw new Error(
                `Erro HTTP: ${resposta.status}`
            );

        }

        const dados = await resposta.json();

        if (!dados.resposta) {

            throw new Error(
                "A API não retornou uma resposta válida."
            );

        }

        respostaTexto = dados.resposta;

    } catch (erro) {

        console.error(
            "Erro ao conversar com a PYXIE:",
            erro
        );

        deuErro = true;

    } finally {

        pendenteId = null;

        removerIndicador();

        // Reativa controles
        definirCarregando(false);
    }

    // A conversa pode ter sido apagada enquanto esperava
    const aindaExiste = estado.conversas.includes(conversa);

    // Só desenha se o usuário ainda está olhando para essa conversa
    const visivel = estado.ativa === conversa.id;

    if (deuErro) {

        // Erros aparecem na tela, mas não entram no histórico
        if (visivel) {
            desenharMensagem(
                "Desculpe, ocorreu um erro ao tentar falar comigo.",
                "pyxie"
            );
        }

    } else if (aindaExiste) {

        registrarMensagem(conversa, "pyxie", respostaTexto);

        if (visivel) {
            desenharMensagem(respostaTexto, "pyxie");
        }
    }

    // Volta o foco para o campo
    input.focus();
}


// ========================================
// EVENTOS
// ========================================

botao.addEventListener(
    "click",
    enviarMensagem
);

input.addEventListener(
    "keydown",
    function (event) {

        // Enter envia
        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            enviarMensagem();
        }

    }
);

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

// Por privacidade, a câmera não fica ligada com a aba em segundo plano
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

    estado = { conversas: [], ativa: null };

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

// No celular o histórico começa fechado
fecharSidebarNoCelular();