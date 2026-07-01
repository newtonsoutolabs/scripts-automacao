import gspread
import pandas as pd

print("Iniciando o robô, Boss...")

# 1. Configurando a autenticação
caminho_json = (
    r"C:\Users\Newton solto\Documents\Automação\Automacao-planilhas\credenciais.json"
)
gc = gspread.service_account(filename=caminho_json)

# 2. Abrindo a planilha
NOME_DA_PLANILHA = " DEMANDAS DE ABRIL 2026"
NOME_DA_ABA = "APROVADOS"

print("Conectando ao Google Sheets...")
planilha = gc.open(NOME_DA_PLANILHA)
aba = planilha.worksheet(NOME_DA_ABA)

# 3. Puxando os dados de forma segura (sem destruir fórmulas)
print("Baixando os dados...")
linhas = aba.get_all_values()

# Pega a primeira linha (cabeçalho)
cabecalhos = linhas[0]

# O Python vai procurar automaticamente em qual posição estão essas 3 colunas
idx_data = cabecalhos.index("DATA ")
idx_contrato = cabecalhos.index("CONTRATO")
idx_motivo = cabecalhos.index("MOTIVO")

# Cria o DataFrame ignorando a primeira linha (cabeçalho)
df = pd.DataFrame(linhas[1:], columns=cabecalhos)

if not df.empty:
    print("Processando validações de contratos antigos...")

    # Guarda o número da linha real lá do Sheets (linha 1 é cabecalho, os dados começam na 2)
    df["linha_sheet"] = df.index + 2

    # Converte a coluna DATA para o formato de data do Python para conseguir saber quem é mais velho
    df["DATA_FORMATADA"] = pd.to_datetime(
        df.iloc[:, idx_data], format="%d/%m/%Y", errors="coerce"
    )

    # Ordena: Contrato (crescente) e Data (decrescente - a data mais nova fica no topo)
    df_ordenado = df.sort_values(
        by=["CONTRATO", "DATA_FORMATADA"], ascending=[True, False]
    )

    # Encontra os duplicados (como o mais novo tá no topo, keep='first' diz para NÃO marcar ele)
    duplicados_antigos = df_ordenado.duplicated(subset=["CONTRATO"], keep="first")

    # Prepara a lista de atualizações cirúrgicas
    celulas_para_atualizar = []

    # Filtra apenas as linhas que foram marcadas como "duplicadas e velhas"
    df_velhos = df_ordenado[duplicados_antigos]

    for index, row in df_velhos.iterrows():
        linha_atual = row["linha_sheet"]
        # Adiciona a instrução: "Na linha X, coluna MOTIVO, escreva 'campanha antiga'"
        # Soma 1 na coluna pq o Sheets conta a partir do 1 (A=1, B=2...), mas o Python conta do 0.
        celulas_para_atualizar.append(
            gspread.Cell(row=linha_atual, col=idx_motivo + 1, value="CAMPANHA ANTIGA")
        )

    # 4. Enviando a atualização de volta pro Sheets
    if celulas_para_atualizar:
        print(
            f"Encontrei {len(celulas_para_atualizar)} contratos antigos. Atualizando..."
        )
        # Essa função altera apenas as células específicas, não toca no resto da tabela!
        aba.update_cells(celulas_para_atualizar)
        print("Sucesso, Boss! Planilha atualizada preservando as fórmulas.")
    else:
        print("Nenhum contrato antigo duplicado encontrado para alterar.")
else:
    print("A planilha está vazia.")
