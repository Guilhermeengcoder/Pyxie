const chat = document.getElementById("chat");
const input = document.getElementById("mensagem");
const botao = document.getElementById("enviar");


// ========================================
// ADICIONAR MENSAGEM AO CHAT
// ========================================

function adicionarMensagem(texto, tipo) {

    const mensagem = document.createElement("div");

    mensagem.classList.add("message");

    if (tipo === "usuario") {

        mensagem.classList.add("user-message");

        mensagem.textContent = texto;

    } else {

        mensagem.classList.add("pyxie-message");

        // Container do texto
        const textoMensagem = document.createElement("span");

        textoMensagem.textContent = texto;

        // Botão de copiar
        const copiar = document.createElement("button");

        copiar.textContent = "📋";

        copiar.title = "Copiar resposta";

        copiar.classList.add("copy-button");

        copiar.addEventListener("click", async () => {

            try {

                await navigator.clipboard.writeText(texto);

                copiar.textContent = "✓";

                setTimeout(() => {
                    copiar.textContent = "📋";
                }, 1500);

            } catch (erro) {

                console.error("Não foi possível copiar:", erro);

            }

        });

        mensagem.appendChild(textoMensagem);
        mensagem.appendChild(copiar);
    }

    chat.appendChild(mensagem);

    // Sempre mostrar a mensagem mais recente
    chat.scrollTop = chat.scrollHeight;
}


// ========================================
// INDICADOR DE PROCESSAMENTO
// ========================================

function criarIndicador() {

    const indicador = document.createElement("div");

    indicador.classList.add(
        "message",
        "pyxie-message"
    );

    indicador.id = "indicador";

    indicador.textContent = "PYXIE está pensando...";

    chat.appendChild(indicador);

    chat.scrollTop = chat.scrollHeight;
}


// ========================================
// REMOVER INDICADOR
// ========================================

function removerIndicador() {

    const indicador = document.getElementById("indicador");

    if (indicador) {
        indicador.remove();
    }
}


// ========================================
// ENVIAR MENSAGEM
// ========================================

async function enviarMensagem() {

    const mensagem = input.value.trim();

    // Não envia mensagem vazia
    if (!mensagem) {
        return;
    }

    // Adiciona mensagem do usuário
    adicionarMensagem(mensagem, "usuario");

    // Limpa campo
    input.value = "";

    // Desativa controles enquanto processa
    input.disabled = true;
    botao.disabled = true;

    botao.textContent = "Pensando...";

    criarIndicador();

    try {

        const resposta = await fetch("/perguntar", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                mensagem: mensagem
            })

        });


        // Verifica erro HTTP
        if (!resposta.ok) {

            throw new Error(
                `Erro HTTP: ${resposta.status}`
            );

        }


        // Converte resposta para JSON
        const dados = await resposta.json();

        removerIndicador();


        // Verifica se a API retornou uma resposta
        if (!dados.resposta) {

            throw new Error(
                "A API não retornou uma resposta válida."
            );

        }


        // Mostra resposta da PYXIE
        adicionarMensagem(
            dados.resposta,
            "pyxie"
        );


    } catch (erro) {

        console.error(
            "Erro ao conversar com a PYXIE:",
            erro
        );

        removerIndicador();

        adicionarMensagem(
            "Desculpe, ocorreu um erro ao tentar falar comigo.",
            "pyxie"
        );

    } finally {

        // Reativa controles
        input.disabled = false;
        botao.disabled = false;

        botao.textContent = "Enviar";

        // Volta o foco para o campo
        input.focus();
    }
}


// ========================================
// BOTÃO ENVIAR
// ========================================

botao.addEventListener(
    "click",
    enviarMensagem
);


// ========================================
// TECLADO
// ========================================

input.addEventListener(
    "keydown",
    function(event) {

        // Enter envia
        // Shift + Enter cria nova linha

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            enviarMensagem();
        }

    }
);