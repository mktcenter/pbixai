import os
from .pbix_tools.extractor import extract_pbix, find_model_file, parse_measures
from .dax_analyzer.explain import explicar_medida_dax
import json

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

    medidas = parse_measures(model_file)
    if not medidas:
        print("⚠️ Nenhuma medida encontrada.")
        return

    print(f"📊 {len(medidas)} medidas encontradas. Gerando explicações...\n")

    resultados = []
    for i, medida in enumerate(medidas, start=1):
        print(f"🔹 [{i}/{len(medidas)}] {medida['nome']}")
        explicacao = explicar_medida_dax(medida['nome'], medida['expressao'])
        medida_com_explicacao = {
            **medida,
            "explicacao": explicacao
        }
        resultados.append(medida_com_explicacao)
        print(f"✅ Explicação gerada:\n{explicacao}\n{'-'*60}\n")

    if salvar_em_json:
        os.makedirs("outputs", exist_ok=True)
        output_path = os.path.join("outputs", "explicacoes.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=4, ensure_ascii=False)
        print(f"💾 Resultado salvo em: {output_path}")

    return resultados


if __name__ == "__main__":
    caminho_pbix = "samples/exemplo.pbix"  # Altere aqui para o seu arquivo .pbix
    processar_pbix(caminho_pbix)
