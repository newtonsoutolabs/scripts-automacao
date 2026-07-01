import gspread
from google.oauth2.service_account import Credentials

def realizar_auditoria():

    # -------------------------------------------------------------------------
    # 1. CONEXÃO COM A API DO GOOGLE
    # Lê o arquivo de credenciais e autoriza o acesso às planilhas
    # -------------------------------------------------------------------------
    creds = Credentials.from_service_account_file("credenciais.json", scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)

    # IDs das planilhas (os mesmos usados na migração)
    id_origem = "1kKlidPcR2J9RI9h1I4IkjzQx4CZYRnQ8irm0g8VzWj0"
    id_teste  = "1Wu2uzvCIZbTKgdLuSimB943vcT3VBU9WkWKcBir-yWA"

    # Abas que devem ser ignoradas — mesma lista da migração
    abas_ignorar = ["RELATÓRIO GERAL", "JAIRANE B.O", "SISTEMA ANTIGO"]

    # Coluna C (número 3) é onde fica o número do contrato em cada aba da origem
    # A=1, B=2, C=3 na contagem do gspread
    COLUNA_CONTRATO_ORIGEM = 3

    # Na planilha de destino, após a migração, CONTRATO fica na coluna A (=1)
    # porque o DataFrame é gravado a partir da célula A1
    COLUNA_CONTRATO_DESTINO = 3

    print("[-] Iniciando auditoria de integridade...")

    # -------------------------------------------------------------------------
    # 2. CONTAGEM NA PLANILHA DE ORIGEM (aba por aba)
    # -------------------------------------------------------------------------
    planilha_origem = client.open_by_key(id_origem)
    total_origem = 0

    print("\n[Relatório de Origem por Aba]:")
    for aba in planilha_origem.worksheets():

        # Normaliza o nome da aba para comparação sem sensibilidade a maiúsculas
        if aba.title.strip().upper() in [a.strip().upper() for a in abas_ignorar]:
            print(f" - {aba.title}: [IGNORADA]")
            continue

        # Lê todos os valores da coluna C, pulando a linha 1 (cabeçalho)
        valores = aba.col_values(COLUNA_CONTRATO_ORIGEM)[1:]

        # Conta apenas células que têm algum conteúdo (não estão vazias)
        validos = [v for v in valores if str(v).strip() != ""]
        total_origem += len(validos)

        print(f" - {aba.title}: {len(validos)} contratos")

    # -------------------------------------------------------------------------
    # 3. CONTAGEM NA PLANILHA DE DESTINO (tudo em uma aba só)
    # -------------------------------------------------------------------------
    planilha_teste  = client.open_by_key(id_teste)
    aba_teste       = planilha_teste.worksheet("Página1")

    # Lê todos os valores da coluna A (CONTRATO), pulando o cabeçalho
    valores_teste  = aba_teste.col_values(COLUNA_CONTRATO_DESTINO)[1:]
    validos_teste  = [v for v in valores_teste if str(v).strip() != ""]
    total_teste    = len(validos_teste)

    # -------------------------------------------------------------------------
    # 4. RESULTADO FINAL
    # -------------------------------------------------------------------------
    print(f"\n" + "=" * 30)
    print(f"TOTAL ESPERADO NA ORIGEM : {total_origem}")
    print(f"TOTAL ENCONTRADO NO TESTE: {total_teste}")
    print("=" * 30)

    if total_origem == total_teste:
        print("\n[SUCESSO] Conferência batida! A migração foi 100% fiel.")
    else:
        diferenca = total_origem - total_teste
        sinal = "faltando" if diferenca > 0 else "sobrando"
        print(f"\n[ALERTA] Divergência encontrada! {abs(diferenca)} registros {sinal}.")

if __name__ == "__main__":
    realizar_auditoria()