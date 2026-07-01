import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

def executar_migracao_testes():

    # -------------------------------------------------------------------------
    # 1. CONFIGURAÇÃO DE ACESSO À API DO GOOGLE
    # -------------------------------------------------------------------------
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        creds = Credentials.from_service_account_file("credenciais.json", scopes=scopes)
        client = gspread.authorize(creds)
        print("[-] Autenticação com a API do Google realizada com sucesso.")
    except Exception as e:
        print(f"[X] Erro na autenticação. Verifique o arquivo credenciais.json: {e}")
        return

    # -------------------------------------------------------------------------
    # 2. IDs E CONFIGURAÇÕES
    # -------------------------------------------------------------------------
    id_planilha_origem        = "1kKlidPcR2J9RI9h1I4IkjzQx4CZYRnQ8irm0g8VzWj0"
    id_planilha_destino_teste = "1Wu2uzvCIZbTKgdLuSimB943vcT3VBU9WkWKcBir-yWA"
    nome_aba_destino          = "Página1"
    abas_para_ignorar         = ["RELATÓRIO GERAL", "JAIRANE B.O", "SISTEMA ANTIGO"]

    # Tamanho do lote de linhas gravadas por vez.
    # 2000 é seguro para evitar o limite da API do Google Sheets.
    TAMANHO_LOTE = 2000

    # -------------------------------------------------------------------------
    # 3. LEITURA E CONSOLIDAÇÃO (igual ao script anterior — já estava correto)
    # -------------------------------------------------------------------------
    df_consolidado = pd.DataFrame()
    
    try:
        planilha_origem = client.open_by_key(id_planilha_origem)
        todas_abas = planilha_origem.worksheets()
        print(f"\n[-] Conectado à planilha: {planilha_origem.title}")
        print(f"[-] Encontradas {len(todas_abas)} abas. Iniciando varredura...")
    except Exception as e:
        print(f"[X] Erro ao abrir a planilha de origem: {e}")
        return

    abas_ignorar_upper = [aba.strip().upper() for aba in abas_para_ignorar]

    for idx, worksheet in enumerate(todas_abas, start=1):
        nome_aba = worksheet.title.strip()

        if nome_aba.upper() in abas_ignorar_upper:
            print(f"    [{idx}] Ignorando aba restrita: {nome_aba}")
            continue
            
        try:
            dados_brutos = worksheet.get("A:V")
            
            if not dados_brutos or len(dados_brutos) < 2:
                print(f"    [{idx}] Aba vazia ou sem dados: {nome_aba}")
                continue
                
            headers = [str(h).strip().upper() for h in dados_brutos[0]]
            linhas_brutas = dados_brutos[1:]
            num_colunas = len(headers)
            linhas_corrigidas = []
            
            for linha in linhas_brutas:
                if len(linha) < num_colunas:
                    linha.extend([''] * (num_colunas - len(linha)))
                elif len(linha) > num_colunas:
                    linha = linha[:num_colunas]
                linhas_corrigidas.append(linha)
            
            df_temp = pd.DataFrame(linhas_corrigidas, columns=headers)
            
            if 'CONTRATO' in df_temp.columns:
                total_antes = len(df_temp)
                df_temp['CONTRATO'] = df_temp['CONTRATO'].astype(str).str.strip()
                df_temp = df_temp[
                    (df_temp['CONTRATO'] != '') & 
                    (df_temp['CONTRATO'] != 'None') & 
                    (df_temp['CONTRATO'].notna())
                ]
                total_depois = len(df_temp)
                df_consolidado = pd.concat([df_consolidado, df_temp], ignore_index=True)
                print(f"    [{idx}] '{nome_aba}': {total_depois} contratos válidos (filtrados {total_antes - total_depois} vazios)")
            else:
                print(f"    [!] Coluna CONTRATO não encontrada na aba: {nome_aba}")
                
        except Exception as e:
            print(f"    [X] Erro ao processar '{nome_aba}': {e}")

    # -------------------------------------------------------------------------
    # 4. GRAVAÇÃO EM LOTES — AQUI ESTAVA O PROBLEMA
    # -------------------------------------------------------------------------
    if df_consolidado.empty:
        print("\n[!] Nenhum contrato válido encontrado. Encerrando.")
        return

    print(f"\n[-] Total consolidado: {len(df_consolidado)} linhas válidas.")
    print("[-] Iniciando gravação na planilha de destino em lotes...")

    try:
        planilha_teste = client.open_by_key(id_planilha_destino_teste)
        aba_teste = planilha_teste.worksheet(nome_aba_destino)

        # Limpa tudo que estava na aba antes de gravar
        aba_teste.clear()
        print("[-] Aba de destino limpa com sucesso.")

        # Prepara os dados: substitui NaN por vazio e converte tudo para texto
        df_consolidado = df_consolidado.fillna("").astype(str)

        # Monta a lista completa: primeira linha = cabeçalho, resto = dados
        todas_as_linhas = [df_consolidado.columns.tolist()] + df_consolidado.values.tolist()

        # -----------------------------------------------------------------
        # GRAVAÇÃO EM LOTES
        # Em vez de mandar 8935 linhas de uma vez (o que truncava),
        # mandamos de TAMANHO_LOTE em TAMANHO_LOTE.
        # A variável `linha_atual` controla em qual linha da planilha
        # vamos gravar o próximo lote (começa em 1 = linha A1).
        # -----------------------------------------------------------------
        linha_atual = 1  # linha da planilha onde o próximo lote será colado

        for i in range(0, len(todas_as_linhas), TAMANHO_LOTE):

            # Fatia o lote atual (ex: linhas 0 a 1999, depois 2000 a 3999...)
            lote = todas_as_linhas[i : i + TAMANHO_LOTE]

            # Converte o número da linha para notação A1 do Sheets (ex: linha 1 = "A1")
            celula_inicio = f"A{linha_atual}"

            # Grava o lote na planilha a partir da célula calculada
            aba_teste.update(celula_inicio, lote)

            # Calcula até qual linha foi gravada neste lote para o log
            linha_fim = linha_atual + len(lote) - 1
            print(f"    [-] Lote gravado: linhas {linha_atual} até {linha_fim} ({len(lote)} registros)")

            # Avança o ponteiro para a próxima linha disponível
            linha_atual += len(lote)

        print(f"\n[+] MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print(f"[+] Total gravado na planilha de destino: {len(df_consolidado)} registros.")

    except Exception as e:
        print(f"[X] Erro crítico ao gravar os dados: {e}")

if __name__ == "__main__":
    executar_migracao_testes()