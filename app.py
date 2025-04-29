import json
import pandas as pd
import os
from datetime import datetime
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)

class SistemaConvocacao:
    def __init__(self, caminho_arquivo_json):
        """Inicializa o sistema de convocação com o arquivo JSON de candidatos."""
        self.caminho_arquivo_json = caminho_arquivo_json
        self.df = None
        self.convocados_final = None
        self.data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")

        # Registrar fonte Arial
        try:
            pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))
        except:
            print("Aviso: Fonte Arial não encontrada. Usando Helvetica como alternativa.")

    def carregar_dados(self):
        """Carrega e prepara os dados do arquivo JSON, removendo convocados"""
        try:
            with open(self.caminho_arquivo_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.df = pd.DataFrame(data)

            # Limpeza e preparação dos dados
            self.df.columns = self.df.columns.str.strip()

            # Converter a coluna de inscrição para string para garantir compatibilidade
            self.df["INSCRIÇÃO"] = self.df["INSCRIÇÃO"].astype(str).str.strip()

            # Remover candidatos já convocados
            self.df = self.df[self.df["SITUAÇÃO"] != "CONVOCADO"].copy()
            self.df.reset_index(drop=True, inplace=True) # Resetar o índice após a filtragem

            # Converter colunas numéricas (onde a conversão para float é possível)
            numeric_cols = ['CLAS. AMPLA', 'CLAS. COTAS', 'LP', 'LI', 'RLM', 'AT', 'LEG. PMDF', 'CONH. BÁS.', 'CONH. ESP.', 'TOTAL OBJETIVA', 'REDAÇÃO', 'NOTA TOTAL']
            for col in numeric_cols:
                if col in self.df.columns:
                    # Tentar converter para float, substituindo vírgula por ponto
                    self.df[col] = pd.to_numeric(self.df[col].str.replace(',', '.'), errors='coerce')

            # Cria coluna para identificar cotistas
            self.df["cotista"] = self.df["CLAS. COTAS"].notna()

            print(f"Dados carregados com sucesso do JSON. Total de {len(self.df)} candidatos.")
            print(f"Primeiras 5 inscrições no dataframe: {self.df['INSCRIÇÃO'].head(5).tolist()}")
            print(f"Últimas 5 inscrições no dataframe: {self.df['INSCRIÇÃO'].tail(5).tolist()}")

            return True
        except Exception as e:
            print(f"Erro ao carregar o arquivo JSON: {e}")
            return False

    def simular_convocacao(self, num_inscricao, total_vagas, desconsiderar_sub_judice=False):
        """
        Simula o processo de convocação baseado no número de vagas especificado.
        Implementa a regra: cotistas com classificação para ampla são convocados como ampla,
        liberando vaga para outros cotistas.
        Opção para desconsiderar candidatos Sub Judice.
        """
        if self.df is None:
            print("É necessário carregar os dados primeiro.")
            return "Erro: dados não carregados", None

        # Filtrar candidatos Sub Judice se a opção estiver marcada
        if desconsiderar_sub_judice:
            print("ENTROU NO BLOCO DE DESCONSIDERAR SUB JUDICE")
            self.df = self.df[~self.df['NOME'].str.contains('(Sub Judice)', case=False)].copy()
            self.df.reset_index(drop=True, inplace=True)
            print(f"Total de candidatos após remover Sub Judice: {len(self.df)}")

        # Garantir que o número de inscrição seja tratado como string
        num_inscricao = str(num_inscricao).strip()

        # NOVO: Logs adicionais para depuração
        print(f"Verificando a inscrição: {num_inscricao}")
        print(f"Total de candidatos no dataframe: {len(self.df)}")
        print(f"Inscrição encontrada no dataframe original: {num_inscricao in self.df['INSCRIÇÃO'].values}")

        # NOVO: Verificar informações do candidato no dataframe original
        if num_inscricao in self.df["INSCRIÇÃO"].values:
            candidato_df = self.df[self.df["INSCRIÇÃO"] == num_inscricao].iloc[0]
            print(f"Candidato encontrado no dataframe original: {candidato_df['NOME']}")
            print(f"Classificação ampla: {candidato_df['CLAS. AMPLA']}")
            print(f"Classificação cotas: {candidato_df['CLAS. COTAS'] if not pd.isna(candidato_df['CLAS. COTAS']) else 'N/A'}")
        else:
            print(f"ATENÇÃO: A inscrição {num_inscricao} não foi encontrada no dataframe original!")
            # Verificar se há alguma inscrição similar para detectar possíveis problemas de formatação
            print("Verificando inscrições similares...")
            for inscr in self.df['INSCRIÇÃO'].values[:20]:  # Verificar as primeiras 20 inscrições
                print(f"Comparando com: '{inscr}' (tipo: {type(inscr)})")

        # Calcular a quantidade de vagas para cotistas (20%) e ampla (80%)
        vagas_cotas = int(total_vagas * 0.20)
        vagas_ampla = total_vagas - vagas_cotas  # Garante que o total seja exato

        print(f"Simulando convocação para {total_vagas} vagas ({vagas_ampla} ampla e {vagas_cotas} cotas)")

        # Ordenar todos os candidatos por classificação ampla
        df_ampla = self.df.sort_values(by="CLAS. AMPLA").copy()

        # 1. Selecionar primeiro os candidatos dentro do limite de vagas de ampla concorrência
        convocados_ampla_inicial = df_ampla.head(vagas_ampla).copy()
        convocados_ampla_inicial['TIPO_CONVOCACAO'] = 'Ampla Concorrência'

        # Contar quantos cotistas foram convocados pela ampla
        cotistas_na_ampla = convocados_ampla_inicial[convocados_ampla_inicial['cotista'] == True]
        print(f"Cotistas aprovados pela ampla concorrência: {len(cotistas_na_ampla)}")

        # 2. Selecionar cotistas que não foram convocados pela ampla
        todos_cotistas = self.df[self.df['cotista'] == True].copy()
        cotistas_restantes = todos_cotistas[~todos_cotistas['INSCRIÇÃO'].isin(convocados_ampla_inicial['INSCRIÇÃO'])]
        cotistas_restantes = cotistas_restantes.sort_values(by="CLAS. COTAS")

        # 3. Definir o número necessário de cotistas adicionais para atingir o mínimo de 20%
        # Precisamos convocar (vagas_cotas) cotistas no total
        cotistas_adicionais_necessarios = vagas_cotas

        # MODIFICAÇÃO: Verificar se há cotistas suficientes para preencher as vagas reservadas
        if len(cotistas_restantes) < cotistas_adicionais_necessarios:
            print(f"AVISO: Não há cotistas suficientes para preencher todas as vagas reservadas!")
            print(f"- Vagas reservadas para cotas: {cotistas_adicionais_necessarios}")
            print(f"- Cotistas disponíveis: {len(cotistas_restantes)}")

            # Usar todos os cotistas disponíveis
            convocados_cotas = cotistas_restantes.copy()
            convocados_cotas['TIPO_CONVOCACAO'] = 'Cotas'

            # Calcular quantas vagas de cotas sobraram para serem preenchidas por candidatos da ampla
            vagas_cotas_nao_preenchidas = cotistas_adicionais_necessarios - len(convocados_cotas)
            print(f"- Vagas de cotas não preenchidas: {vagas_cotas_nao_preenchidas}")

            # Selecionar candidatos adicionais da ampla concorrência para preencher as vagas restantes
            # Excluir candidatos já convocados (pela ampla ou cotas)
            inscritos_ja_convocados = list(convocados_ampla_inicial['INSCRIÇÃO']) + list(convocados_cotas['INSCRIÇÃO'])
            candidatos_ampla_adicional = df_ampla[~df_ampla['INSCRIÇÃO'].isin(inscritos_ja_convocados)].head(vagas_cotas_nao_preenchidas).copy()
            candidatos_ampla_adicional['TIPO_CONVOCACAO'] = 'Ampla Concorrência (Remanejada)'

            print(f"- Candidatos adicionais da ampla selecionados para completar o total: {len(candidatos_ampla_adicional)}")

            # Combinar todos os convocados
            self.convocados_final = pd.concat([convocados_ampla_inicial, convocados_cotas, candidatos_ampla_adicional])
            print("--- Lista dos 50 primeiros convocados (após a simulação para 1200 vagas): ---")
            print(self.convocados_final.head(50)['INSCRIÇÃO'].tolist())
            print("--- Fim da lista ---")
        else:
            # Lógica original quando há cotistas suficientes
            convocados_cotas = cotistas_restantes.head(cotistas_adicionais_necessarios).copy()
            convocados_cotas['TIPO_CONVOCACAO'] = 'Cotas'

            # Combinar todos os convocados
            self.convocados_final = pd.concat([convocados_ampla_inicial, convocados_cotas])
            print("--- Lista dos 50 primeiros convocados (após a simulação para 1200 vagas): ---")
            print(self.convocados_final.head(50)['INSCRIÇÃO'].tolist())
            print("--- Fim da lista ---")

        # NOVO: Log para verificar o total de convocados
        print(f"Total de candidatos convocados na simulação: {len(self.convocados_final)}")

        # Estatísticas sobre a convocação
        total_convocados = len(self.convocados_final)
        total_cotistas = len(self.convocados_final[self.convocados_final['cotista'] == True])
        percentual_cotistas = (total_cotistas / total_convocados) * 100 if total_convocados > 0 else 0

        print(f"Total de candidatos convocados: {total_convocados}")
        print(f"Total de cotistas convocados: {total_cotistas} ({percentual_cotistas:.1f}%)")
        print(f"- Pela ampla concorrência: {len(cotistas_na_ampla)}")
        print(f"- Pelas vagas reservadas: {len(convocados_cotas)}")

        # Verificar se o candidato informado está na lista
        resultado = "NÃO foi convocado"
        candidato_info = None

        # NOVO: Converter para string antes de comparar
        if num_inscricao in self.convocados_final["INSCRIÇÃO"].astype(str).str.strip().values:
            candidato = self.convocados_final[self.convocados_final["INSCRIÇÃO"].astype(str).str.strip() == num_inscricao].iloc[0]
            tipo_vaga = candidato['TIPO_CONVOCACAO']

            # Definir qual classificação mostrar com base no tipo de vaga
            if tipo_vaga.startswith('Ampla'):
                posicao = candidato['CLAS. AMPLA']
                classificacao_str = f"Classificação Ampla: {posicao}"
            else:
                posicao = candidato['CLAS. COTAS']
                classificacao_str = f"Classificação Cotas: {posicao}"

            # Verificar se é cotista convocado pela ampla
            e_cotista = candidato['cotista']
            info_adicional = " (Cotista aprovado pela Ampla)" if e_cotista and tipo_vaga.startswith('Ampla') else ""

            resultado = f"CONVOCADO! Nome: {candidato['NOME']}, Tipo: {tipo_vaga}{info_adicional}, {classificacao_str}"

            candidato_info = {
                'nome': candidato['NOME'],
                'inscricao': candidato['INSCRIÇÃO'],
                'tipo': tipo_vaga,
                'classificacao': posicao,
                'cotista': bool(candidato['cotista']) # CONVERTER PARA bool DO PYTHON
            }
        else:
            print(f"ATENÇÃO: A inscrição {num_inscricao} NÃO foi encontrada na lista final de convocados!")
            # Verificar se há alguma inscrição similar na lista final
            for inscr in self.convocados_final['INSCRIÇÃO'].values[:10]:  # Verificar as primeiras 10 inscrições
                print(f"Comparando com inscrição convocada: '{inscr}'")
            
            resultado = f"Candidato com inscrição {num_inscricao} não encontrado na lista de convocados para a simulação com o número de vagas informado."

        return resultado, candidato_info

    def gerar_pdf(self, nome_arquivo="lista_convocados.pdf"):
        """Gera um PDF formatado com a lista de convocados."""
        if self.convocados_final is None or len(self.convocados_final) == 0:
            print("Não há convocados para gerar o PDF.")
            return False

        # Criar diretório para relatórios se não existir
        diretorio = os.path.dirname(nome_arquivo)
        if diretorio and not os.path.exists(diretorio):
            os.makedirs(diretorio)

        # Configurar o documento
        doc = SimpleDocTemplate(
            nome_arquivo,
            pagesize=landscape(A4),
            rightMargin=1.5*cm,    # Reduzindo as margens para aproveitar melhor o espaço A4
            leftMargin=1.5*cm,
            topMargin=1.5*cm,
            bottomMargin=1.5*cm
        )

        # Estilos para o documento
        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle(
            'TituloStyle',
            parent=styles['Heading1'],
            fontName='Arial' if 'Arial' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
            fontSize=16,
            alignment=1,  # Centralizado
            spaceAfter=10
        )

        subtitulo_style = ParagraphStyle(
            'SubtituloStyle',
            parent=styles['Heading2'],
            fontName='Arial' if 'Arial' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
            fontSize=12,
            alignment=1,
            spaceAfter=5
        )

        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['Normal'],
            fontName='Arial' if 'Arial' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
            fontSize=12,
            alignment=0  # Esquerda
        )

        # Elementos do documento
        elementos = []

        # Título do documento
        titulo = Paragraph("POLÍCIA MILITAR DO DISTRITO FEDERAL", titulo_style)
        elementos.append(titulo)
        elementos.append(Spacer(1, 5*mm))

        subtitulo = Paragraph("Lista de Convocados para o Curso de Formação", subtitulo_style)
        elementos.append(subtitulo)
        elementos.append(Spacer(1, 3*mm))

        data_geracao = Paragraph(f"Gerado em: {self.data_geracao}", normal_style)
        elementos.append(data_geracao)
        elementos.append(Spacer(1, 10*mm))

        # Estatísticas sobre as vagas
        total_vagas = len(self.convocados_final)
        convocados_ampla_regular = self.convocados_final[self.convocados_final['TIPO_CONVOCACAO'] == 'Ampla Concorrência']
        convocados_ampla_remanejada = self.convocados_final[self.convocados_final['TIPO_CONVOCACAO'] == 'Ampla Concorrência (Remanejada)']
        convocados_cotas = self.convocados_final[self.convocados_final['TIPO_CONVOCACAO'] == 'Cotas']

        cotistas_na_ampla = convocados_ampla_regular[convocados_ampla_regular['cotista'] == True]

        # Criar resumo estatístico
        elementos.append(Paragraph("Resumo da simulação:", subtitulo_style))
        elementos.append(Spacer(1, 3*mm))

        elementos.append(Paragraph(f"• Total de convocados: {total_vagas} candidatos", normal_style))
        elementos.append(Paragraph(f"• Convocados pela ampla concorrência: {len(convocados_ampla_regular) + len(convocados_ampla_remanejada)}", normal_style))
        elementos.append(Paragraph(f"  - Sendo {len(cotistas_na_ampla)} cotistas aprovados pela ampla", normal_style))
        if len(convocados_ampla_remanejada) > 0:
            elementos.append(Paragraph(f"  - Sendo {len(convocados_ampla_remanejada)} por remanejamento de vagas de cotas não preenchidas", normal_style))
        elementos.append(Paragraph(f"• Convocados pelas cotas: {len(convocados_cotas)}", normal_style))
        elementos.append(Paragraph(f"• Total de cotistas convocados: {len(cotistas_na_ampla) + len(convocados_cotas)}", normal_style))

        elementos.append(Spacer(1, 10*mm))

        # Definir cores personalizadas para a tabela
        cor_ampla = colors.Color(0.85, 0.95, 0.85)   # Verde claro
        cor_cotas = colors.Color(0.95, 0.9, 0.8)     # Marrom claro (pardo)
        cor_remanejada = colors.Color(0.9, 0.9, 1.0)  # Azul bem claro para vagas remanejadas
        cor_cabecalho = colors.Color(0.2, 0.2, 0.7)  # Azul escuro para o cabeçalho

        # Preparação dos dados para a tabela
        colunas = ['Nº', 'Inscrição', 'Nome do Candidato', 'Tipo de Vaga', 'Class. Ampla', 'Class. Cotas', 'Observação']

        # Ajustar o tamanho das colunas para melhor utilização do espaço A4
        larguras_colunas = [1.0*cm, 2.5*cm, 10*cm, 4*cm, 2*cm, 2*cm, 6*cm]

        # Adicionar os dados dos convocados
        dados_tabela = [colunas]

        # Em vez de usar itertuples, vamos trabalhar com valores diretamente
        for i, (_, candidato) in enumerate(self.convocados_final.iterrows(), 1):
            # Definir a observação para cotistas na ampla ou para vagas remanejadas
            observacao = ""
            if candidato['cotista'] and candidato['TIPO_CONVOCACAO'] == 'Ampla Concorrência':
                observacao = "Cotista aprovado pela ampla"
            elif candidato['TIPO_CONVOCACAO'] == 'Ampla Concorrência (Remanejada)':
                observacao = "Vaga remanejada de cotas"

            # Formatação das classificações - acessando colunas pelo nome, que é mais seguro
            class_ampla = int(candidato['CLAS. AMPLA']) if not pd.isna(candidato['CLAS. AMPLA']) else "-"
            class_cotas = int(candidato['CLAS. COTAS']) if not pd.isna(candidato['CLAS. COTAS']) else "-"

            # Simplificar o tipo de vaga para exibição
            tipo_vaga_exibicao = "Ampla Concorrência" if candidato['TIPO_CONVOCACAO'].startswith('Ampla') else candidato['TIPO_CONVOCACAO']

            dados_tabela.append([
                i,
                candidato['INSCRIÇÃO'],
                candidato['NOME'],
                tipo_vaga_exibicao,
                class_ampla,
                class_cotas,
                observacao
            ])

        # Criar a tabela com larguras específicas para cada coluna
        tabela = Table(dados_tabela, colWidths=larguras_colunas)

        # Estilos da tabela
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), cor_cabecalho),  # Cabeçalho azul
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Arial-Bold' if 'Arial-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), cor_ampla),  # Cor padrão para ampla
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        # Aplicar cores específicas para cotas e vagas remanejadas
        for i, linha in enumerate(dados_tabela[1:], 1):
            if linha[3] == 'Cotas':
                tabela.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), cor_cotas)]))
            elif linha[3] == 'Ampla Concorrência (Remanejada)':
                tabela.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), cor_remanejada)]))

        elementos.append(tabela)

        try:
            doc.build(elementos)
            print(f"PDF gerado com sucesso: {nome_arquivo}")
            return True
        except Exception as e:
            print(f"Erro ao gerar o PDF: {e}")
            return False

    def salvar_convocados_csv(self, nome_arquivo="convocados.csv"):
        """Salva a lista de convocados em um arquivo CSV."""
        if self.convocados_final is None or len(self.convocados_final) == 0:
            print("Não há convocados para salvar em CSV.")
            return False

        try:
            self.convocados_final.to_csv(nome_arquivo, index=False, encoding='utf-8')
            print(f"Lista de convocados salva em: {nome_arquivo}")
            return True
        except Exception as e:
            print(f"Erro ao salvar em CSV: {e}")
            return False

# Instanciar o sistema de convocação com o arquivo JSON
sistema = SistemaConvocacao("dados_candidatos.json")

# Carregar os dados
if not sistema.carregar_dados():
    print("Erro ao carregar os dados do JSON. O programa será encerrado.")
    exit()

@app.route('/')
def index():
    return render_template('index.html')  # Assumindo que você tem um index.html

@app.route('/simular', methods=['POST'])
def simular():
    print("Requisição POST para /simular recebida!")
    try:
        data = request.get_json()
        inscricao = data['inscricao']
        total_vagas = int(data['total_vagas'])
        desconsiderar_sub_judice = data.get('desconsiderar_sub_judice', False) # Recebe o parâmetro, com valor padrão False se não vier
        print(f"Inscrição recebida: {inscricao}, Total de Vagas: {total_vagas}, Desconsiderar Sub Judice: {desconsiderar_sub_judice}")

        # NOVO: Adicionar logs para verificar o tipo de dados
        print(f"Tipo de inscricao: {type(inscricao)}")
        print(f"Tipo de total_vagas: {type(total_vagas)}")
        print(f"Tipo de desconsiderar_sub_judice: {type(desconsiderar_sub_judice)}") # ADICIONEI O LOG FALTANTE

        resultado, candidato_info = sistema.simular_convocacao(inscricao, total_vagas, desconsiderar_sub_judice)
        print(f"Resultado da simulação: {resultado}")
        print(f"Candidato Info: {candidato_info}")
        return jsonify({'resultado': resultado, 'candidato': candidato_info})
    except Exception as e:
        print(f"Ocorreu um erro na função simular: {e}")
        return jsonify({'erro': str(e)})

@app.route('/gerar_pdf/<inscricao>', methods=['GET'])
def gerar_pdf(inscricao):
    try:
        # Obter o total de vagas do parâmetro de consulta
        total_vagas = int(request.args.get('total_vagas', 0))
        print(f"Requisição GET para /gerar_pdf/{inscricao}?total_vagas={total_vagas}")
        
        # Verificar se já existe uma simulação ou realizar nova simulação
        if sistema.convocados_final is None or len(sistema.convocados_final) == 0:
            resultado, _ = sistema.simular_convocacao(inscricao, total_vagas)
            print(f"Nova simulação realizada para geração do PDF: {resultado}")
        
        # Gerar um PDF baseado na simulação atual
        nome_arquivo = f"pdfs/simulacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        if sistema.gerar_pdf(nome_arquivo):
            return send_file(nome_arquivo, as_attachment=True, download_name=f"convocados_{total_vagas}_vagas.pdf")
        else:
            return jsonify({'erro': 'Não foi possível gerar o PDF. Verifique se uma simulação foi realizada.'})
    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        return jsonify({'erro': str(e)})

if __name__ == '__main__':
    print("Entrando no bloco if __name__ == '__main__':")
    try:
        # Criar diretório para PDFs se não existir
        if not os.path.exists('pdfs'):
            os.makedirs('pdfs')
            print("Diretório 'pdfs' criado")

        app.run(debug=True, host='0.0.0.0', port=5001)  # Alterei a porta para 5001
        print("Servidor Flask finalizou (isso geralmente não acontece em modo debug)")
    except Exception as e:
        print(f"Erro ao executar app.run(): {e}")