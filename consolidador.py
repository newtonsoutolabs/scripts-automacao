import gspread
import pandas as pd

# 1. Configurações Iniciais
caminho_json = (
    r"C:\Users\Newton solto\Documents\Automação\Automacao-planilhas\credenciais.json"
)
NOME_PLANILHA_ORIGEM = (
    "(JULIO) LISTAS INDIVIDUAIS"  # Sua planilha com as abas dos analistas
)
NOME_NOVA_PLANILHA = "CONSOLIDADO GERAL - NOVO ARQUIVO"
SEU_EMAIL = "newtonsoltoacordo@gmail.com"  # <--- COLOQUE SEU E-MAIL AQUI para conseguir ver o arquivo

COLUNAS_DESEJADAS = ["CONTRATO", "ESCRITÓRIO", "BANCO", "VALOR DO CLIENTE", "SITUAÇÃO"]
ABAS_IGNORADAS = ["RELATÓRIO GERAL", "SISTEMA ANTIGO"]

# Autenticação
gc = gspread.service_account(filename=caminho_json)
planilha_origem = gc.open(NOME_PLANILHA_ORIGEM)

print(f"Lendo dados de '{NOME_PLANILHA_ORIGEM}'...")

lista_dataframes = []

# 2. Coletando os dados das abas
for aba in planilha_origem.worksheets():
    if aba.title not in ABAS_IGNORADAS:
        print(f"Extraindo: {aba.title}")
        dados_brutos = aba.get_all_values()

        # Se a aba estiver vazia ou só tiver cabeçalho, pula
        if not dados_brutos or len(dados_brutos) < 2:
            continue

        # Trata os cabeçalhos para evitar colunas duplicadas
        cabecalhos_originais = dados_brutos[0]
        cabecalhos_limpos = []
        contagem = {}

        for c in cabecalhos_originais:
            nome = str(c).strip()
            if nome in contagem:
                contagem[nome] += 1
                cabecalhos_limpos.append(f"{nome}_{contagem[nome]}")
            else:
                contagem[nome] = 0
                cabecalhos_limpos.append(nome)

        linhas = dados_brutos[1:]

        # Cria o DataFrame com os cabeçalhos já limpos e sem repetições
        df = pd.DataFrame(linhas, columns=cabecalhos_limpos)

        # Filtra as colunas desejadas que existem nesta aba
        colunas_existentes = [c for c in COLUNAS_DESEJADAS if c in df.columns]
        df_filtrado = df[colunas_existentes].copy()

        # Adiciona a coluna com o nome do analista
        df_filtrado["ANALISTA"] = aba.title
        lista_dataframes.append(df_filtrado)

# 3. Enviando os dados para o arquivo final
if lista_dataframes:
    df_final = pd.concat(lista_dataframes, ignore_index=True)

    # Organiza colunas para o ANALISTA ser a primeira
    colunas = ["ANALISTA"] + [c for c in df_final.columns if c != "ANALISTA"]
    df_final = df_final[colunas]

    # Troca os "NaN" (células vazias do Pandas) por textos vazios para o Google aceitar
    df_final = df_final.fillna("")

    print("\nEnviando os dados para a planilha destino...")

    planilha_destino = gc.open("CONSOLIDADO DA EQUIPE")
    aba_destino = planilha_destino.sheet1

    aba_destino.clear()

    # Escreve os dados novos
    aba_destino.update([df_final.columns.values.tolist()] + df_final.values.tolist())

    print("Sucesso, Coach! A consolidação foi salva na sua planilha.")
else:
    print("Nenhum dado encontrado nas abas.")
