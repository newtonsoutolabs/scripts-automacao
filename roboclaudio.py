import gspread
import pandas as pd
import uuid
from datetime import datetime

# ============================================================
# CONFIGURAÇÕES
# ============================================================
CAMINHO_JSON = (
    r"C:\Users\Newton solto\Documents\Automação\Automacao-planilhas\credenciais.json"
)

PLANILHA_ORIGEM = (
    "(JULIO) LISTAS INDIVIDUAIS"  # sua planilha velha com abas por analista
)
PLANILHA_DESTINO = "CONSOLIDADO DA EQUIPE"  # sua planilha nova com as 5 abas

ABAS_IGNORADAS = ["RELATÓRIO GERAL", "SISTEMA ANTIGO"]

# ============================================================
# MAPEAMENTO: nome da aba antiga → nome do analista na nova tabela
# Ajuste conforme seus nomes reais
# ============================================================
MAPA_ANALISTAS = {
    "ANA GESSICA": "AMANDA SATANA",  # <- ajuste se o nome for diferente
    "FELIPE": "FELIPE TORRES",
    "ANA LIDIA": "FRANSICA LOPES",
    "JULIANE": "JULIANA BATISTA",
    "NUNO": "NUNO SOUSA",
    "MATHEUS": "THALISSON SERRA",
    "VIVIANE": "ALINE SALVADOR",
    "ELISANGELA": "AMANDA SATANA",  # <- ajuste conforme necessário
    "POLIANA": "FRANSICA LOPES",  # <- ajuste conforme necessário
    "SABRINA": "JULIANA BATISTA",  # <- ajuste conforme necessário
}

# ============================================================
# MAPEAMENTO: colunas antigas → colunas novas
# Baseado no que li nas suas screenshots
# ============================================================
# Colunas antigas (podem variar por aba):
#   DATA, RESOLUÇÃO, CONTRATO, ESCRITÓRIO, ÚLTIMO PAGAMENTO,
#   PRAZO (E), ENTRADA, PRAZO (H), BANCO, SITUAÇÃO (J=tipo dívida),
#   VALOR DO CLIENTE, CONTATO, NEGOCIAÇÃO, SITUAÇÃO (N=status workflow),
#   VALOR DO DESCONTO

MAPA_COLUNAS = {
    "CONTRATO": "id_contrato",
    "ESCRITÓRIO": "escritorio",
    "BANCO": "banco",
    "VALOR DO CLIENTE": "total_divida",
    "DATA": "data_qualidade",
    "ÚLTIMO PAGAMENTO": "data_ultimo_pagamento",
    "RESOLUÇÃO": "data_resolucao",
    # SITUAÇÃO col J (tipo da dívida: EMPRÉSTIMO, CARTÃO, etc.)
    # SITUAÇÃO col N (status: APROVADO, PENDENTE, etc.) → situacao_atual
    # Após deduplicação no script antigo, a segunda vira SITUAÇÃO_1
}

# ============================================================
# AUTENTICAÇÃO
# ============================================================
gc = gspread.service_account(filename=CAMINHO_JSON)
planilha_origem = gc.open(PLANILHA_ORIGEM)
planilha_destino = gc.open(PLANILHA_DESTINO)

print(f"✅ Conectado. Lendo '{PLANILHA_ORIGEM}'...")

# ============================================================
# PASSO 1: Ler lookup tables existentes na planilha destino
# (Escritórios, Bancos, Analistas) — não vamos sobrescrever, só consultar
# ============================================================
aba_analistas = planilha_destino.worksheet("Analistas")
aba_escritorios = planilha_destino.worksheet("Escritórios")
aba_bancos = planilha_destino.worksheet("Bancos")
aba_contratos = planilha_destino.worksheet("Contratos")
aba_negociacao = planilha_destino.worksheet("Negociacao")

df_analistas = pd.DataFrame(aba_analistas.get_all_records())
df_escritorios = pd.DataFrame(aba_escritorios.get_all_records())

# Mapa: nome analista → id_analista
mapa_id_analista = {
    str(row["nome"]).strip().upper(): int(row["id_analista"])
    for _, row in df_analistas.iterrows()
}

# Mapa: escritório → uf, diretor (para enriquecer Contratos)
# A coluna de escritório na tabela Escritórios se chama 'escritorio'
df_escritorios.columns = [c.strip().lower() for c in df_escritorios.columns]
mapa_escritorio = {
    str(row.get("escritorio", "")).strip().upper(): {
        "uf": row.get("uf", ""),
        "diretor": row.get("diretor", ""),
    }
    for _, row in df_escritorios.iterrows()
}

print(f"   → {len(mapa_id_analista)} analistas carregados")
print(f"   → {len(mapa_escritorio)} escritórios carregados")

# ============================================================
# PASSO 2: Ler e consolidar todas as abas dos analistas
# ============================================================
lista_contratos = []
lista_negociacoes = []

for aba in planilha_origem.worksheets():
    nome_aba = aba.title.strip().upper()

    if nome_aba in [a.upper() for a in ABAS_IGNORADAS]:
        print(f"   ⏭  Ignorando: {aba.title}")
        continue

    dados = aba.get_all_values()
    if not dados or len(dados) < 2:
        print(f"   ⚠️  Aba vazia: {aba.title}")
        continue

    print(f"   📋 Lendo: {aba.title}")

    # --- Limpa cabeçalhos duplicados ---
    cabecalhos_raw = dados[0]
    cabecalhos = []
    contagem = {}
    for c in cabecalhos_raw:
        nome = str(c).strip().upper()
        if nome in contagem:
            contagem[nome] += 1
            cabecalhos.append(f"{nome}_{contagem[nome]}")
        else:
            contagem[nome] = 0
            cabecalhos.append(nome)

    df = pd.DataFrame(dados[1:], columns=cabecalhos)
    df = df.replace("", pd.NA)

    # Remove linhas sem contrato
    if "CONTRATO" not in df.columns:
        print(f"   ⚠️  Sem coluna CONTRATO em: {aba.title}")
        continue

    df = df.dropna(subset=["CONTRATO"])
    df = df[df["CONTRATO"].str.strip() != ""]

    # --- Resolve id_analista ---
    nome_analista_novo = MAPA_ANALISTAS.get(nome_aba, nome_aba)
    id_analista = mapa_id_analista.get(nome_analista_novo.upper(), None)

    if id_analista is None:
        print(
            f"   ⚠️  Analista '{nome_analista_novo}' não encontrado na tabela Analistas. Usando NULL."
        )

    # --- Determina qual coluna é o STATUS de workflow ---
    # Após deduplicação: primeira SITUAÇÃO = tipo dívida (col J)
    #                    SITUAÇÃO_1 = status workflow (col N)
    col_situacao_atual = "SITUAÇÃO_1" if "SITUAÇÃO_1" in df.columns else "SITUAÇÃO"

    # ============================================================
    # MONTA CONTRATOS
    # ============================================================
    for _, row in df.iterrows():
        contrato_id = str(row.get("CONTRATO", "")).strip()
        if not contrato_id:
            continue

        escritorio_raw = str(row.get("ESCRITÓRIO", "") or "").strip().upper()
        info_esc = mapa_escritorio.get(escritorio_raw, {"uf": "", "diretor": ""})

        contrato = {
            "id_contrato": contrato_id,
            "id_analista": id_analista or "",
            "regiao": nome_analista_novo,  # ou pode ser o diretor/região real
            "data_qualidade": str(row.get("DATA", "") or "").strip(),
            "data_ultimo_pagamento": str(row.get("ÚLTIMO PAGAMENTO", "") or "").strip(),
            "total_divida": str(row.get("VALOR DO CLIENTE", "") or "").strip(),
            "escritorio": str(row.get("ESCRITÓRIO", "") or "").strip(),
            "banco": str(row.get("BANCO", "") or "").strip(),
            "codigo": "",  # não existe no sistema antigo
            "situacao_atual": str(row.get(col_situacao_atual, "") or "").strip(),
            "tem_processo": "",  # não existe no sistema antigo
            "uf": info_esc.get("uf", ""),
            "diretor": info_esc.get("diretor", ""),
            "consultor": "",  # não existe no sistema antigo
        }
        lista_contratos.append(contrato)

        # ============================================================
        # MONTA NEGOCIACAO (só se tiver valor de desconto ou nota)
        # ============================================================
        valor_desconto = str(row.get("VALOR DO DESCONTO", "") or "").strip()
        negociacao_txt = str(row.get("NEGOCIAÇÃO", "") or "").strip()
        contato = str(row.get("CONTATO", "") or "").strip()

        if valor_desconto or negociacao_txt:
            negociacao = {
                "id_historico": str(uuid.uuid4())[:8],
                "id_analista": id_analista or "",
                "id_registro": str(uuid.uuid4())[:8],
                "valor_desconto": valor_desconto,
                "valor_analise": "",
                "precisa_minuta": "",
                "id_contrato": contrato_id,
                "data_hora": datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                "tipo_contato": contato,
                "resultado_contato": negociacao_txt,
                "situacao_nova": str(row.get(col_situacao_atual, "") or "").strip(),
                "observacao": negociacao_txt,
            }
            lista_negociacoes.append(negociacao)

# ============================================================
# PASSO 3: Deduplicar Contratos (mesmo contrato em 2 abas → fica 1)
# ============================================================
df_contratos = pd.DataFrame(lista_contratos)
df_negociacoes = pd.DataFrame(lista_negociacoes)

# Se um contrato aparece em mais de uma aba, fica a última ocorrência
df_contratos = df_contratos.drop_duplicates(subset=["id_contrato"], keep="last")
df_contratos = df_contratos.fillna("").astype(str)

if not df_negociacoes.empty:
    df_negociacoes = df_negociacoes.fillna("").astype(str)

print(f"\n📊 Resumo:")
print(f"   → {len(df_contratos)} contratos únicos")
print(f"   → {len(df_negociacoes)} registros de negociação")

# ============================================================
# PASSO 4: Escrever na planilha destino
# ============================================================
print("\n🚀 Enviando para a planilha destino...")

# --- Contratos ---
aba_contratos.clear()
aba_contratos.update([df_contratos.columns.tolist()] + df_contratos.values.tolist())
print(f"   ✅ Aba 'Contratos' atualizada com {len(df_contratos)} linhas")

# --- Negociacao ---
if not df_negociacoes.empty:
    aba_negociacao.clear()
    aba_negociacao.update(
        [df_negociacoes.columns.tolist()] + df_negociacoes.values.tolist()
    )
    print(f"   ✅ Aba 'Negociacao' atualizada com {len(df_negociacoes)} linhas")
else:
    print("   ⚠️  Nenhum dado de negociação encontrado")

# --- Timestamp de controle ---
print(f"\n✅ Migração concluída em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
print("   Lookup tables (Escritórios, Bancos, Analistas) não foram alteradas.")
