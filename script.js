async function simularConvocacao() {
    const inscricao = document.getElementById("inscricao").value.trim(); // Adicionar .trim()
    const totalVagas = document.getElementById("total_vagas").value; // Pegar o valor do total de vagas
    const desconsiderarSubJudice = document.getElementById("desconsiderar_sub_judice").checked; // Captura o estado do checkbox
    const resultadoDiv = document.getElementById("resultado");
    const mensagemConvocacao = document.getElementById("mensagem-convocacao");
    const mensagemAjudaDiv = document.getElementById("mensagem-ajuda");

    console.log("Enviando requisição para simular com inscrição:", inscricao, "e total de vagas:", totalVagas);

    const response = await fetch('/simular', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            inscricao: inscricao,
            total_vagas: totalVagas,
            desconsiderar_sub_judice: desconsiderarSubJudice // Envia o estado do checkbox
        })
    });

    const data = await response.json();

    console.log("Resposta do servidor:", data);
    console.log("Resultado da convocação:", data.resultado);

    mensagemConvocacao.textContent = data.resultado; // Exibir a mensagem de resultado do servidor

    resultadoDiv.classList.remove('resultado-oculto');
    mensagemAjudaDiv.classList.remove('mensagem-ajuda-oculto');
}

async function gerarPDF() {
    const inscricao = document.getElementById("inscricao").value;
    const totalVagas = document.getElementById("total_vagas").value;
    if (inscricao) {
        window.open(`/gerar_pdf/${inscricao}?total_vagas=${totalVagas}`, '_blank');
    } else {
        alert("Por favor, insira o número de inscrição antes de gerar o PDF.");
    }
}