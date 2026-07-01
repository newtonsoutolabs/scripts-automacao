# -*- coding: utf-8 -*-
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

def padronizar_planilhas():
    # -------------------------------------------------------------------------
    # CONFIGURAÇÃO DE CREDENCIAIS E ACESSO
    # -------------------------------------------------------------------------
    # Certifique-se de que o arquivo 'credenciais.json' esteja na mesma pasta do script
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    try:
        creds = Credentials.from_service_account_file('credenciais.json', scopes=SCOPES)
        client = gspread.authorize(creds)
    except Exception as e:
        print(f"Erro ao carregar o arquivo 'credenciais.json': {e}")
        print("Certifique-se de baixar suas credenciais da conta de serviço do Google Cloud.")
        return

    # IMPORTANTE: Insira aqui os IDs longos das suas planilhas (presentes na URL do navegador)
    ID_PLANILHA_ORIGINAL = '1kKlidPcR2J9RI9h1I4IkjzQx4CZYRnQ8irm0g8VzWj0'
    ID_PLANILHA_TESTE = '1MhzpTAVYVmnj0WbXHJ8Wkb3HNVzQ09kJtq36HwnfsXg'

    print("Conectando às planilhas...")
    try:
        planilha_origem = client.open_by_key(ID_PLANILHA_ORIGINAL)
        planilha_destino = client.open_by_key(ID_PLANILHA_TESTE)
    except Exception as e:
        print(f"Erro ao abrir as planilhas. Verifique se os IDs estão corretos e se o e-mail da conta de serviço foi compartilhado com elas: {e}")
        return

    # -------------------------------------------------------------------------
    # DEFINIÇÃO DE REGRAS (PARAMETRIZAÇÃO)
    # -------------------------------------------------------------------------
    # 1. Lista oficial de colunas na ordem exata solicitada
    COLUNAS_OFICIAIS = [
        "DATA ENTRADA NA PLANILHA", "DATA RESOLUÇÃO", "CONTRATO", "ESCRITÓRIO", 
        "ÚLTIMO PAGAMENTO", "PRAZO BANCO", "DATA QUALIDADE", "PRAZO SETE", 
        "BANCO", "CÓD", "VALOR DO CLIENTE", "CONTATO", "ULTIMA NEGOCIAÇÃO", 
        "SITUAÇÃO", "%", "OBSERVAÇÃO"
    ]

    # 3. Abas que devem ser completamente ignoradas pelo robô
    ABAS_IGNORADAS = ["RELATÓRIO GERAL", "SISTEMA ANTIGO"]

    # Percorrer todas as abas da planilha original
    for aba in planilha_origem.worksheets():
        nome_aba = aba.title
        
        if nome_aba in ABAS_IGNORADAS:
            print(f"[-] Ignorando aba desmarcada: {nome_aba}")
            continue
            
        print(f"[+] Processando dados da aba: {nome_aba}")
        
        # Obter todos os dados brutos (preserva linhas e colunas vazias)
        dados_brutos = aba.get_all_values()
        if not dados_brutos:
            print(f"    [Aviso] Aba {nome_aba} está totalmente vazia. Pulando...")
            continue
            
        # O primeiro elemento é a linha de cabeçalhos
        # Limpa espaços extras e padroniza para maiúsculas para evitar erros de digitação
        cabecalho_original = [str(c).strip().upper() for c in dados_brutos[0]]
        linhas_dados = dados_brutos[1:]
        
        # Criar DataFrame com os dados das linhas
        df = pd.DataFrame(linhas_dados, columns=cabecalho_original)
        
        # 2. Identificar colunas extras adicionadas pelos analistas (que não estão nas oficiais)
        colunas_extras = [col for col in cabecalho_original if col not in COLUNAS_OFICIAIS and col != '']
        
        # Garantir que todas as colunas oficiais exigidas existam (se não existirem, cria vazias)
        for col_oficial in COLUNAS_OFICIAIS:
            if col_oficial not in df.columns:
                df[col_oficial] = ""
                
        # Montar a ordem final: Colunas oficiais primeiro, colunas extras no final
        ordem_final_colunas = COLUNAS_OFICIAIS + colunas_extras
        
        # Reordenar o DataFrame baseado na nova estrutura de colunas
        df_padronizado = df[ordem_final_colunas]
        
        # Substituir valores nulos/NaN por strings vazias para o Google Sheets aceitar
        df_padronizado = df_padronizado.fillna("")
        
        # Preparar a matriz final de dados (Cabeçalho + Linhas) para envio
        dados_finais = [df_padronizado.columns.tolist()] + df_padronizado.values.tolist()
        
        # Verificar e gerenciar a aba correspondente na planilha de teste
        try:
            aba_destino = planilha_destino.worksheet(nome_aba)
            aba_destino.clear()  # Limpa o conteúdo e formatações antigas da aba de teste
            print(f"    Limpar dados antigos da aba '{nome_aba}' na planilha de teste.")
        except gspread.exceptions.WorksheetNotFound:
            # Se a aba do analista não existir na planilha de teste, cria dinamicamente
            linhas_necessarias = max(len(dados_finais) + 20, 100)
            colunas_necessarias = max(len(ordem_final_colunas) + 5, 26)
            aba_destino = planilha_destino.add_worksheet(
                title=nome_aba, 
                rows=linhas_necessarias, 
                cols=colunas_necessarias
            )
            print(f"    Criada nova aba '{nome_aba}' na planilha de teste.")
            
        # 4. Atualizar a aba de destino enviando o bloco completo de dados de uma vez só (otimizado)
        aba_destino.update('A1', dados_finais)
        print(f"    [Sucesso] Dados reinseridos e ordenados na aba de teste!")

    print("\n[CONCLUÍDO] Todas as abas elegíveis foram processadas e padronizadas na planilha de teste.")

if __name__ == '__main__':
    padronizar_planilhas()