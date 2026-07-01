# 📊 Automações de Dados e Web Scraping

Este repositório contém um conjunto de scripts desenvolvidos em Python focados em engenharia de dados, automação de rotinas administrativas, web scraping e integração com APIs (Google Sheets e Supabase). O objetivo destas ferramentas é consolidar, auditar e padronizar grandes volumes de dados.

## 🛠️ Tecnologias Utilizadas
* **Linguagem:** Python 3
* **Manipulação de Dados:** `pandas`
* **Integração Google Workspace:** `gspread`, `google-auth`
* **Automação Web/Scraping:** `playwright` e `asyncio`
* **Banco de Dados/Integração:** `supabase`

---

## 🔒 Aviso de Segurança (Como rodar este projeto)

Para proteger dados sensíveis, as chaves de API e senhas não estão neste repositório. Para executar os scripts na sua máquina, siga estes passos:

1. **Google Sheets (Scripts de Planilha):** 
   * Crie um arquivo chamado `credenciais.json` na raiz da pasta.
   * Adicione suas chaves de conta de serviço do Google Cloud neste arquivo (baseie-se na estrutura padrão do GCP).
2. **SeteCRM Scraper:**
   * Crie um arquivo `.env` na raiz do projeto.
   * Adicione as seguintes variáveis com seus dados:
     ```env
     SETE_EMAIL=seu_email@aqui.com
     SETE_PASSWORD=sua_senha
     SUPABASE_URL=sua_url_aqui (Opcional)
     SUPABASE_KEY=sua_key_aqui (Opcional)
     ```

---

## 📂 Documentação dos Scripts

### 1. Padronizador de Planilhas (`padronizar_planilhas.py`)
* **Visão Geral:** Este script padroniza abas de planilhas originais, garantindo que as colunas oficiais apareçam na ordem exata solicitada e que colunas extras adicionadas pelos analistas fiquem posicionadas no final[cite: 1]. 
* **Funcionalidades:** Ele ignora abas específicas (como "RELATÓRIO GERAL") e envia os dados limpos de uma vez só para uma planilha de teste, criando novas abas dinamicamente caso não existam[cite: 1].

### 2. Robô Atualizador de Campanhas (`robo.py`)
* **Visão Geral:** Focado em higienização de base de dados, este script ordena os registros por contrato e data para identificar duplicidades antigas[cite: 2].
* **Funcionalidades:** Ele atualiza cirurgicamente a coluna "MOTIVO" preenchendo com "CAMPANHA ANTIGA" apenas nas linhas marcadas como velhas, utilizando o método `update_cells` para preservar o restante da planilha e suas fórmulas originais[cite: 2].

### 3. Consolidador e Mapeador Avançado (`consolidador.py`)
* **Visão Geral:** Script robusto que consolida informações de listas individuais, separando as informações em duas matrizes relacionais: "Contratos" e "Negociacao"[cite: 3].
* **Funcionalidades:** Mapeia dinamicamente nomes antigos de analistas para os novos e gera IDs únicos (UUID)[cite: 3]. O script faz a deduplicação mantendo apenas a ocorrência mais recente de cada contrato e não altera tabelas de consulta existentes (Escritórios, Bancos, Analistas)[cite: 3].

### 4. SeteCRM Scraper (`scrapper.py`)
* **Visão Geral:** Automação web assíncrona construída com Playwright que faz login no sistema, busca contratos via URL e extrai todos os detalhes[cite: 4].
* **Funcionalidades:** Extrai dados de financiamento (banco, prazos, valores), informações do cliente e detalhes do contratante[cite: 4]. Os dados podem ser salvos localmente em formato JSON (com timestamp) ou enviados via "upsert" diretamente para um banco de dados no Supabase[cite: 4].

### 5. Auditoria de Migração (`auditoria.py`)
* **Visão Geral:** Ferramenta de verificação de integridade pós-migração.
* **Funcionalidades:** Conta os contratos válidos (células não vazias) na coluna C de cada aba elegível da planilha de origem e compara com o total consolidado na coluna A da planilha de destino[cite: 5]. O sistema emite um alerta matemático no terminal se houver divergências ou confirma se a migração foi 100% fiel[cite: 5].

### 6. Distribuidor por Instituição Bancária (`bancos.py`)
* **Visão Geral:** Processa abas de anos anteriores e categoriza contratos por banco.
* **Funcionalidades:** Calcula dinamicamente o tempo de contrato em meses considerando a data de qualidade frente à data atual, padroniza o primeiro nome do diretor em letras maiúsculas e distribui os dados formatados em abas específicas por instituição (ex: C6, Porto Seguro, Inter)[cite: 6].

### 7. Consolidador Simples (`consolidacao_simples.py`)
* **Visão Geral:** Uma versão simplificada para extração rápida de indicadores[cite: 7].
* **Funcionalidades:** Varre abas de analistas, limpa nomes de cabeçalhos duplicados, extrai cinco colunas específicas (Contrato, Escritório, Banco, Valor, Situação) e anexa uma nova coluna identificando o analista responsável antes de enviar os dados em bloco para um novo arquivo[cite: 7].

### 8. Migrador em Lotes Seguros (`migracao_lotes.py`)
* **Visão Geral:** Projetado para lidar com grandes volumes de dados sem exceder limites de requisição[cite: 8].
* **Funcionalidades:** Após consolidar e filtrar apenas contratos válidos (removendo campos vazios ou 'None'), ele realiza a gravação no destino dividindo a matriz de dados em lotes definidos (ex: 2000 linhas por vez), gerenciando o cálculo da célula de início dinamicamente[cite: 8].
