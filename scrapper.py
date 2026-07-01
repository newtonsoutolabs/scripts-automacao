"""
SeteCRM Contract Scraper
========================
Dado um número de contrato, faz login no classic.setecrm.com.br,
busca o contrato, extrai todos os dados e salva no Supabase (ou Google Sheets).

Instalação:
    pip install playwright supabase python-dotenv
    playwright install chromium

Uso:
    python setecrm_scraper.py --contrato 221004
    python setecrm_scraper.py --lista contratos.txt   (vários de uma vez)
"""

import asyncio
import argparse
import json
import re
import os
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

load_dotenv()

# ============================================================
# CONFIGURAÇÕES — preencha no arquivo .env ou direto aqui
# ============================================================
SETE_URL = "https://classic.setecrm.com.br"
SETE_EMAIL = os.getenv("SETE_EMAIL", "seu@email.com")
SETE_PASSWORD = os.getenv("SETE_PASSWORD", "sua_senha")

# Supabase (opcional por agora — pode deixar vazio e só imprime o JSON)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

HEADLESS = True  # False = abre janela do browser (útil pra debugar)


# ============================================================
# HELPERS
# ============================================================
def limpar_valor(texto: str) -> str:
    """Remove espaços extras e caracteres desnecessários."""
    return str(texto or "").strip()


def extrair_numero(texto: str) -> str:
    """Extrai só os dígitos de um texto como 'R$ 1.234,56'."""
    return re.sub(r"[^\d,.]", "", texto).strip()


# ============================================================
# LOGIN
# ============================================================
async def fazer_login(page):
    print("  🔐 Fazendo login...")
    await page.goto(f"{SETE_URL}/users/sign_in", wait_until="networkidle")

    # Tenta os seletores mais comuns para campo de email/senha em Rails
    await page.fill(
        'input[type="email"], input[name*="email"], #user_email', SETE_EMAIL
    )
    await page.fill(
        'input[type="password"], input[name*="password"], #user_password', SETE_PASSWORD
    )
    await page.click('input[type="submit"], button[type="submit"]')
    await page.wait_for_load_state("networkidle")

    if "sign_in" in page.url:
        raise Exception("❌ Login falhou — verifique email/senha no .env")
    print("  ✅ Login OK")


# ============================================================
# BUSCAR CONTRATO (encontrar a URL com customer_id + contract_id)
# ============================================================
async def buscar_url_contrato(page, numero_contrato: str) -> str:
    """
    O URL tem formato /customers/XXXXX/analysis/YYYYY
    Precisamos do customer_id. Buscamos pelo número do contrato.
    """
    print(f"  🔍 Buscando contrato {numero_contrato}...")

    # Tenta a URL de busca direta do SeteCRM
    search_urls = [
        f"{SETE_URL}/analyses?q={numero_contrato}",
        f"{SETE_URL}/analyses?search={numero_contrato}",
        f"{SETE_URL}/customers?q={numero_contrato}",
    ]

    for url in search_urls:
        await page.goto(url, wait_until="networkidle")

        # Procura link com o número do contrato na URL
        link = await page.query_selector(f'a[href*="/analysis/{numero_contrato}"]')
        if link:
            href = await link.get_attribute("href")
            full_url = f"{SETE_URL}{href}" if href.startswith("/") else href
            print(f"  ✅ Contrato encontrado: {full_url}")
            return full_url

    # Fallback: tenta URL direta sem customer_id (alguns sistemas aceitam)
    fallback = f"{SETE_URL}/analyses/{numero_contrato}"
    print(f"  ⚠️  Busca não encontrou — tentando URL direta: {fallback}")
    return fallback


# ============================================================
# EXTRAIR DADOS DA PÁGINA DO CONTRATO
# ============================================================
async def extrair_dados(page, numero_contrato: str) -> dict:
    """
    Extrai todos os campos da FICHA DO CONTRATO do SeteCRM.
    Baseado nos campos visíveis nas screenshots:
      - Cabeçalho: status, escritório, UF, consultor, cliente
      - DADOS DO FINANCIAMENTO: banco, parcelas, valor, último pagamento
      - CONTRATANTE: nome, cpf, rg, nascimento, sexo, estado civil, profissão
      - TITULAR: idem (pode ser diferente do contratante)
    """

    dados = {"id_contrato": numero_contrato, "extraido_em": datetime.now().isoformat()}

    # --- Cabeçalho / Ficha ---
    try:
        # "Status : Aprovar Documentos : Escritório : Ponta Grossa, PR : Consultor : Nome"
        header = await page.inner_text("body")

        # Status do contrato
        m = re.search(r"Status\s*:\s*([^\n:]+?)(?:\s*:|\n)", header)
        dados["status_contrato"] = limpar_valor(m.group(1)) if m else ""

        # Escritório + UF  ex: "Ponta Grossa, PR"
        m = re.search(r"Escrit[oó]rio\s*:\s*([^\n:]+?)(?:\s*:|\n)", header)
        if m:
            partes = m.group(1).strip().split(",")
            dados["escritorio"] = limpar_valor(partes[0])
            dados["uf"] = limpar_valor(partes[1]) if len(partes) > 1 else ""
        else:
            dados["escritorio"] = ""
            dados["uf"] = ""

        # Consultor
        m = re.search(r"Consultor\s*:\s*([^\n]+)", header)
        dados["consultor"] = limpar_valor(m.group(1)) if m else ""

    except Exception as e:
        print(f"    ⚠️  Erro no cabeçalho: {e}")

    # --- Nome do cliente (breadcrumb: INÍCIO › CLIENTES › Nome › ANÁLISE BANCO) ---
    try:
        breadcrumb = await page.query_selector(
            "nav, .breadcrumb, [class*='breadcrumb']"
        )
        if breadcrumb:
            texto_bc = await breadcrumb.inner_text()
            # Pega o item entre CLIENTES e ANÁLISE
            m = re.search(
                r"CLIENTES\s*[›>]\s*(.+?)\s*[›>]\s*AN[AÁ]LISE", texto_bc, re.IGNORECASE
            )
            dados["nome_cliente"] = limpar_valor(m.group(1)) if m else ""
        else:
            # Tenta link de cliente no header
            link_cliente = await page.query_selector('a[href*="/customers/"]')
            dados["nome_cliente"] = (
                await link_cliente.inner_text() if link_cliente else ""
            )
    except Exception as e:
        print(f"    ⚠️  Erro no nome do cliente: {e}")
        dados["nome_cliente"] = ""

    # --- DADOS DO FINANCIAMENTO ---
    try:
        # Tipo: EMPRÉSTIMO / CARTÃO / etc
        m = re.search(r"DADOS DO FINANCIAMENTO\s*:\s*([^\n]+)", header, re.IGNORECASE)
        dados["tipo_divida"] = limpar_valor(m.group(1)) if m else ""

        # Instituição/Banco
        m = re.search(r"Institui[cç][aã]o\s*:\s*([^\n]+)", header, re.IGNORECASE)
        dados["banco"] = limpar_valor(m.group(1)) if m else ""

        # Parcelas no plano (prazo total)
        m = re.search(r"Parcelas no plano\s*:\s*(\d+)", header, re.IGNORECASE)
        dados["prazo_total"] = limpar_valor(m.group(1)) if m else ""

        # Parcelas pagas
        m = re.search(r"Parcelas pagas\s*:\s*(\d+)", header, re.IGNORECASE)
        dados["parcelas_pagas"] = limpar_valor(m.group(1)) if m else ""

        # Parcelas atrasadas
        m = re.search(r"Parcelas atrasadas\s*:\s*(\d+)", header, re.IGNORECASE)
        dados["parcelas_atrasadas"] = limpar_valor(m.group(1)) if m else ""

        # Valor da parcela
        m = re.search(r"Valor da parcela\s*:\s*(R\$\s*[\d\.,]+)", header, re.IGNORECASE)
        dados["valor_parcela"] = limpar_valor(m.group(1)) if m else ""

        # Último pagamento
        m = re.search(r"[UÚ]ltimo pagamento\s*:\s*([^\n]+)", header, re.IGNORECASE)
        dados["ultimo_pagamento"] = limpar_valor(m.group(1)) if m else ""

        # Entrada
        m = re.search(r"Entrada\s*:\s*(R\$\s*[\d\.,]+)", header, re.IGNORECASE)
        dados["entrada"] = limpar_valor(m.group(1)) if m else ""

    except Exception as e:
        print(f"    ⚠️  Erro nos dados do financiamento: {e}")

    # --- CONTRATANTE ---
    try:
        m = re.search(
            r"CONTRATANTE E OU RESPONS[AÁ]VEL\s*:\s*([^\n]+)", header, re.IGNORECASE
        )
        dados["nome_contratante"] = limpar_valor(m.group(1)) if m else ""

        m = re.search(r"CPF\s*:\s*([\d\.\-]+)", header)
        dados["cpf"] = limpar_valor(m.group(1)) if m else ""

        m = re.search(r"Nascimento\s*:\s*([^\n]+)", header)
        dados["nascimento"] = limpar_valor(m.group(1)) if m else ""

        m = re.search(r"Sexo\s*:\s*([^\n]+)", header)
        dados["sexo"] = limpar_valor(m.group(1)) if m else ""

        m = re.search(r"Profiss[aã]o\s*:\s*([^\n]+)", header)
        dados["profissao"] = limpar_valor(m.group(1)) if m else ""

    except Exception as e:
        print(f"    ⚠️  Erro nos dados do contratante: {e}")

    return dados


# ============================================================
# SALVAR NO SUPABASE
# ============================================================
async def salvar_supabase(dados: dict):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("  ℹ️  Supabase não configurado — pulando envio")
        return

    from supabase import create_client

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Tenta upsert pelo id_contrato (não duplica se rodar de novo)
    result = sb.table("contratos").upsert(dados, on_conflict="id_contrato").execute()

    if result.data:
        print(f"  ✅ Supabase: contrato {dados['id_contrato']} salvo")
    else:
        print(f"  ⚠️  Supabase retornou vazio: {result}")


# ============================================================
# PIPELINE PRINCIPAL (1 contrato)
# ============================================================
async def processar_contrato(page, numero_contrato: str) -> dict:
    print(f"\n📄 Processando contrato: {numero_contrato}")
    try:
        url = await buscar_url_contrato(page, numero_contrato)
        await page.goto(url, wait_until="networkidle", timeout=30000)
        dados = await extrair_dados(page, numero_contrato)

        print(f"  📦 Dados extraídos:")
        for k, v in dados.items():
            if v:
                print(f"     {k}: {v}")

        await salvar_supabase(dados)
        return dados

    except PWTimeout:
        print(f"  ❌ Timeout ao carregar contrato {numero_contrato}")
        return {"id_contrato": numero_contrato, "erro": "timeout"}
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return {"id_contrato": numero_contrato, "erro": str(e)}


# ============================================================
# ENTRY POINT
# ============================================================
async def main(contratos: list[str]):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
        )
        page = await context.new_page()

        await fazer_login(page)

        resultados = []
        for contrato in contratos:
            contrato = contrato.strip()
            if not contrato:
                continue
            resultado = await processar_contrato(page, contrato)
            resultados.append(resultado)
            await asyncio.sleep(
                1
            )  # pausa entre contratos — não sobrecarrega o servidor

        await browser.close()

    # Salva resultado local em JSON também (backup)
    saida = f"contratos_extraidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Concluído. Resultados salvos em: {saida}")
    return resultados


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SeteCRM Scraper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--contrato", type=str, help="Número de um contrato")
    group.add_argument(
        "--lista", type=str, help="Arquivo .txt com um contrato por linha"
    )
    args = parser.parse_args()

    if args.contrato:
        contratos = [args.contrato]
    else:
        with open(args.lista, "r", encoding="utf-8") as f:
            contratos = f.readlines()

    asyncio.run(main(contratos))
