import os
import json
from pbix_tools.extractor import (
    extract_pbix,
    find_model_file,
    parse_measures,
    carregar_tabelas_modelo,
)
from dax_analyzer.explain import explicar_medida_dax, explicar_tabela

def processar_pbix(pbix_path, salvar_em_json=True):
    print(f"🔍 Processando arquivo: {pbix_path}")
    
    if not os.path.exists(pbix_path):
        print("❌ Arquivo .pbix não encontrado.")
        return

    pasta_extraida = extract_pbix(pbix_path)
    print(f"📁 Arquivo descompactado em: {pasta_extraida}")

    model_file = find_model_file(pasta_extraida)
    if not model_file:
        print("❌ Arquivo de modelo não encontrado dentro do .pbix.")
        return

    print(f"📄 Modelo encontrado: {model_file}")

    # ---- Tabelas ----
    tabelas_raw = carregar_tabelas_modelo(model_file, pasta_extraida)
    tabelas = []
    if tabelas_raw:
        print(f"📂 {len(tabelas_raw)} tabelas encontradas. Gerando explicações...\n")
        for i, t in enumerate(tabelas_raw, start=1):
            nome_tabela = t.get("name", "Desconhecida")
            colunas = [c.get("name") for c in t.get("columns", [])]
            print(f"🗂️ [{i}/{len(tabelas_raw)}] {nome_tabela}")
            explicacao = explicar_tabela(nome_tabela, colunas)
            tabela_com_explicacao = {
                "nome": nome_tabela,
                "colunas": colunas,
                "explicacao": explicacao,
            }
            tabelas.append(tabela_com_explicacao)
            print(f"   {explicacao}\n{'-'*60}")
    else:
        print("⚠️ Nenhuma tabela encontrada.")

    # ---- Medidas ----
    medidas = parse_measures(model_file)
    if not medidas:
        print("⚠️ Nenhuma medida encontrada.")
        medidas_resultado = []
    else:
        print(f"📊 {len(medidas)} medidas encontradas. Gerando explicações...\n")
        medidas_resultado = []
        for i, medida in enumerate(medidas, start=1):
            print(f"🔹 [{i}/{len(medidas)}] {medida['nome']}")
            explicacao = explicar_medida_dax(medida['nome'], medida['expressao'])
            medida_com_explicacao = {
                **medida,
                "explicacao": explicacao,
            }
            medidas_resultado.append(medida_com_explicacao)
            print(f"✅ Explicação gerada:\n{explicacao}\n{'-'*60}\n")

    if salvar_em_json:
        os.makedirs("outputs", exist_ok=True)
        output_path = os.path.join("outputs", "explicacoes.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"tabelas": tabelas, "medidas": medidas_resultado}, f, indent=4, ensure_ascii=False)
        print(f"💾 Resultado salvo em: {output_path}")

    return {"tabelas": tabelas, "medidas": medidas_resultado}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python main.py <caminho_arquivo.pbix>")
    else:
        caminho_pbix = sys.argv[1]
        processar_pbix(caminho_pbix)
