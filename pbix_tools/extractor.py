import os
import subprocess
import json
import tempfile

# Caminho para o executável do pbi-tools. Permite sobrescrever via variável de
# ambiente ``PBI_TOOLS_EXE``. Caso não seja definido, assume que ``pbi-tools``
# está disponível no PATH.
PBI_TOOLS_EXE = os.getenv("PBI_TOOLS_EXE", "./pbix_tools/pbi-tools.1.2.0/pbi-tools.exe")


def desmontar_pbix_com_pbitools(pbix_path):
    """
    Usa o pbi-tools.exe para extrair o conteúdo do .pbix.
    Retorna o caminho da pasta extraída.
    """
    pasta_destino = tempfile.mkdtemp(prefix="pbix_extract_")
    try:
        print(f"🔧 Executando pbi-tools em: {pbix_path}")
        subprocess.run(
            [
                PBI_TOOLS_EXE,
                "extract",
                pbix_path,
                "-extractFolder", pasta_destino,
                "-modelSerialization", "Raw"
            ],
            check=True
        )
        print(f"✅ Extração concluída em: {pasta_destino}")
        return pasta_destino
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar pbi-tools: {e}")
        return None
    except FileNotFoundError:
        print("❌ Caminho do pbi-tools.exe inválido.")
        return None

def localizar_model_bim(pasta_extraida):
    """
    Retorna o caminho do arquivo do modelo extraído (model.json ou Model.bim).
    """
    print("🔍 Verificando arquivos extraídos:")
    for root, dirs, files in os.walk(pasta_extraida):
        for file in files:
            caminho = os.path.join(root, file)
            print(f"🗂️ {caminho}")
            if file.lower() in ["database.bim", "database.json"]:
                print(f"✅ Modelo encontrado: {caminho}")
                return caminho
    print("❌ Arquivo do modelo não encontrado (nem database.bim nem database.json).")
    return None

def localizar_database_json(pasta_extraida):
    """
    Procura por database.json dentro da pasta Report/Model (formato TMDL).
    """
    caminho = os.path.join(pasta_extraida, "Report", "Model", "database.json")
    if os.path.exists(caminho):
        return caminho
    return None

def localizar_database_modelo(pasta_extraida):
    caminho = os.path.join(pasta_extraida, "Model", "database.json")
    if os.path.exists(caminho):
        return caminho
    return None

def carregar_tabelas_modelo(model_file: str, pasta_extraida: str) -> list:
    """
    Retorna as tabelas a partir do arquivo model_file, com fallback para Model/database.json.
    Garante que retorna uma lista, mesmo se estiver vazia. Inclui logs para debug.
    """
    def ler_json(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERRO] Falha ao ler JSON em {path}: {e}")
            return {}

    # Tenta carregar do model_file
    print(f"[INFO] Tentando carregar tabelas de: {model_file}")
    model_json = ler_json(model_file)
    tabelas = model_json.get("model", {}).get("tables", [])

    if tabelas:
        print(f"[OK] {len(tabelas)} tabelas encontradas em model_file")
        return tabelas

    # Fallback para /Model/database.json
    db_path = os.path.join(pasta_extraida, "Model", "database.json")
    if os.path.exists(db_path):
        print(f"[INFO] Tentando fallback para {db_path}")
        model_json = ler_json(db_path)
        tabelas = model_json.get("model", {}).get("tables", [])
        if tabelas:
            print(f"[OK] {len(tabelas)} tabelas encontradas no database.json")
            return tabelas

    print("[WARN] Nenhuma tabela encontrada em nenhuma fonte.")
    return []

def parse_measures(model_file):
    """
    Extrai medidas DAX do arquivo Model.bim (JSON).
    """
    with open(model_file, 'r', encoding='utf-8') as f:
        try:
            model_data = json.load(f)
        except Exception as e:
            print(f"❌ Erro ao carregar JSON: {e}")
            return []

    medidas = []
    if "model" in model_data and "tables" in model_data["model"]:
        for tabela in model_data["model"]["tables"]:
            nome_tabela = tabela.get("name", "Desconhecida")
            for medida in tabela.get("measures", []):
                expressao_raw = medida.get("expression", "")
                if isinstance(expressao_raw, list):
                    expressao = "\n".join(expressao_raw)
                else:
                    expressao = str(expressao_raw)

                medidas.append({
                    "tabela": nome_tabela,
                    "nome": medida.get("name", "Sem nome"),
                    "expressao": expressao
                })
    else:
        print("⚠️ Estrutura inesperada no arquivo Model.bim.")
    return medidas

def extrair_dax_usadas_nos_visuais(report_layout_path):
    """
    Lê o arquivo de layout e extrai todas as expressões DAX utilizadas nos visuais.
    """
    usadas = set()

    try:
        with open(report_layout_path, "r", encoding="utf-8") as f:
            layout = json.load(f)

        for section in layout.get("sections", []):
            for visual in section.get("visualContainers", []):
                config = visual.get("config", {})
                json_config = json.loads(config) if isinstance(config, str) else config

                # Caminhos comuns com DAX dentro de visuais
                for query_key in ["expression", "query", "formula"]:
                    trecho = str(json_config.get("singleVisual", {}).get("prototypeQuery", {}).get(query_key, ""))
                    if trecho:
                        usadas.update(trecho.lower().split())

    except Exception as e:
        print(f"Erro ao analisar o layout: {e}")

    return usadas

def encontrar_dax_usadas_em_visuais(pasta_extraida):
    """
    Varre todos os arquivos JSON em Report/sections/*/visualContainers/
    e extrai nomes de medidas usados nos visuais (via expression, query, formula).
    Compatível com arquivos que são listas ou dicionários.
    """
    usados = set()
    base_path = os.path.join(pasta_extraida, "Report", "sections")

    if not os.path.exists(base_path):
        return usados

    for root, dirs, files in os.walk(base_path):
        if "visualContainers" in root:
            for file in files:
                if not file.endswith(".json"):
                    continue
                caminho = os.path.join(root, file)
                try:
                    with open(caminho, "r", encoding="utf-8") as f:
                        content = json.load(f)

                    visuais = content if isinstance(content, list) else [content]

                    for visual in visuais:
                        proto = visual.get("prototypeQuery", {})
                        if not isinstance(proto, dict):
                            continue

                        for key in ["expression", "query", "formula"]:
                            raw = proto.get(key)
                            if isinstance(raw, str):
                                nomes = raw.lower().replace("[", "").replace("]", "").split()
                                usados.update(nomes)

                except Exception as e:
                    print(f"⚠️ Erro lendo visual {file}: {e}")

    return usados

# ---------------------------------------------------------------------------
# Funções utilitárias usadas pelo módulo principal

def extract_pbix(pbix_path: str) -> str | None:
    """Desmonta o arquivo .pbix utilizando o pbi-tools.

    Retorna o caminho da pasta extraída ou ``None`` em caso de erro.
    """
    return desmontar_pbix_com_pbitools(pbix_path)


def find_model_file(pasta_extraida: str) -> str | None:
    """Tenta localizar o arquivo do modelo dentro da pasta extraída."""
    caminho = localizar_model_bim(pasta_extraida)
    if not caminho:
        caminho = localizar_database_json(pasta_extraida)
    if not caminho:
        caminho = localizar_database_modelo(pasta_extraida)
    return caminho


