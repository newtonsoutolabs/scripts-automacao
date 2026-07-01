import gspread
import csv
from datetime import datetime

# 1. Autenticação
gc = gspread.service_account(filename='credenciais.json')
planilha = gc.open('bancos') 

# Função para calcular meses com segurança
def calcular_tempo_contrato(data_str):
    if not data_str or str(data_str).strip() == "":
        return "" 
    try:
        data_limpa = str(data_str).strip().split(' ')[0]
        data_q = datetime.strptime(data_limpa, "%d/%m/%Y")
        hoje = datetime.now()
        meses = (hoje.year - data_q.year) * 12 + (hoje.month - data_q.month)
        if hoje.day < data_q.day:
            meses -= 1
        return str(max(0, meses))
    except:
        return ""

abas_de_origem = [
    "SINOSSERRA_ 2022",
    "CREDITAS_SINOSSERRA_PORTO_2023",
    "CREDITAS_SINOSSERRA_PORTO_C6_2024",
    "PORTO_C6_2025",
    "CREDITAS_SINOSSERRA_PORTO_C6_INTER_2026"
]

mapa_bancos = {"C6": "C6 BANK", "PORTO SEGURO": "PORTO SEGURO", "SINOSSERRA": "SINOSSERRA", "CREDITAS": "CREDITAS", "INTER": "INTER"}
dados_para_inserir = {nome: [] for nome in mapa_bancos.values()}

print("Iniciando leitura...")
hoje = datetime.now()

for nome_aba in abas_de_origem:
    print(f"Processando aba: {nome_aba}")
    try:
        aba = planilha.worksheet(nome_aba)
        linhas = aba.get_all_values()[1:]
        
        for linha in linhas:
            if len(linha) == 1:
                try:
                    linha_txt = str(linha[0]).encode('latin1').decode('utf-8')
                    colunas = list(csv.reader([linha_txt]))[0]
                except: continue
            else:
                colunas = linha

            if len(colunas) < 16: continue
            
            # Dados extraídos
            data_qualidade_str = colunas[1]
            id_contrato = colunas[2]
            banco = colunas[9]
            
            # --- NOVA LÓGICA: Primeiro nome em MAIÚSCULO ---
            diretor_full = str(colunas[14])
            diretor_formatado = diretor_full.split(' ')[0].upper()
            # ------------------------------------------------
            
            data_ultimo_pag = colunas[15]

            # Cálculo do tempo
            tempo_contrato = calcular_tempo_contrato(data_qualidade_str)

            for chave, nome_banco in mapa_bancos.items():
                if chave.upper() in banco.upper():
                    # Usando diretor_formatado aqui:
                    dados_para_inserir[nome_banco].append(["", id_contrato, diretor_formatado, tempo_contrato, data_ultimo_pag, "", ""])
                    break
    except Exception as e:
        print(f"Erro na aba {nome_aba}: {e}")

print("Distribuindo...")
cabecalho = ["QTT", "Nº DO CONTRATO", "DIRETOR", "TEMPO DE CONTRATO", "ULTIMA DATA DE PAGAMENTO", "SITUAÇÃO", "CAMPANHA"]

for nome_aba, linhas_novas in dados_para_inserir.items():
    if not linhas_novas: continue
    
    try:
        aba = planilha.worksheet(nome_aba)
    except:
        aba = planilha.add_worksheet(title=nome_aba, rows="1000", cols="10")
        aba.append_row(cabecalho)
    
    ultima_linha = len(aba.col_values(1))
    for i, linha in enumerate(linhas_novas):
        linha[0] = ultima_linha + 1 + i
    
    aba.append_rows(linhas_novas, value_input_option='USER_ENTERED')
    print(f"-> {len(linhas_novas)} linhas enviadas para {nome_aba}")

print("Concluído!")