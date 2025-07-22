import hashlib
import os
import json
import datetime

def gerar_hash_medida(nome, expressao):
    nome = str(nome).strip()
    if isinstance(expressao, list):
        expressao = "\n".join(map(str, expressao))
    expressao = str(expressao).strip()
    texto = nome + "|" + expressao
    return hashlib.md5(texto.encode("utf-8")).hexdigest()

def classificar_complexidade(expressao):
    expressao = expressao.lower()
    if any(x in expressao for x in ["var", "switch", "if("]):
        return "Avançada"
    elif any(x in expressao for x in ["calculate", "filter", "all", "related", "distinct"]):
        return "Intermediária"
    else:
        return "Simples"

def carregar_cache(caminho_arquivo):
    if not os.path.exists(caminho_arquivo):
        return {}
    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def salvar_cache(caminho_arquivo, cache):
    try:
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar cache: {e}")

def gerar_html_relatorio(medidas, tabelas, resumo_medidas, data_geracao=None):
    data_geracao = data_geracao or datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1, h2 {{ color: #00afa0; }}
            .secao {{ margin-bottom: 50px; }}
            .tabela, .medida {{ margin-bottom: 15px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
            th {{ background-color: #00afa0; color: white; }}
        </style>
    </head>
    <body>
        <h1>📊 Power BI Analyzer com IA</h1>
        <p><strong>Data de geração:</strong> {data_geracao}</p>
        
        <div class="secao">
            <h2>📌 Overview</h2>
            <p>Este relatório traz uma análise detalhada de medidas DAX e tabelas contidas no modelo .pbix enviado.</p>
            <p><strong>Total de Tabelas:</strong> {len(tabelas)} | <strong>Total de Medidas:</strong> {len(medidas)}</p>
            <table>
                <tr><th>Tabela</th><th>Qtd. Medidas</th></tr>
                {''.join([f"<tr><td>{t}</td><td>{len(resumo_medidas[t])}</td></tr>" for t in resumo_medidas])}
            </table>
        </div>

        <div class="secao">
            <h2>🧩 Mapa de Medidas</h2>
            {''.join([
                f"<div class='medida'><h3>{t}</h3><ul>" +
                ''.join([f"<li><strong>{m['nome']}</strong> [{m['complexidade']}]</li>" for m in resumo_medidas[t]]) +
                "</ul></div>"
                for t in resumo_medidas
            ])}
        </div>

        <div class="secao">
            <h2>📂 Tabelas</h2>
            {''.join([
                f"<div class='tabela'><h3>{t.get('name')}</h3>" +
                f"<p>Colunas Visíveis: {', '.join([c['name'] for c in t.get('columns', []) if not c.get('isHidden', False)])}</p></div>"
                for t in tabelas
            ])}
        </div>

        <div class="secao">
            <h2>ℹ️ Conclusão</h2>
            <p>Este relatório foi gerado automaticamente com base no modelo extraído do Power BI e enriquecido com explicações de IA (Mistral via Ollama).</p>
        </div>
    </body>
    </html>
    """
    return html


def gerar_html_com_explicacoes(medidas, tabelas, resumo_medidas):
    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            h1, h2, h3 {{ color: #00afa0; }}
            .section {{ margin-bottom: 40px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
            th {{ background-color: #f4f4f4; }}
            pre {{ background: #f6f6f6; padding: 10px; border: 1px solid #ddd; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>Relatório Power BI Analyzer com IA</h1>

        <div class="section">
            <h2>📊 Overview</h2>
            <p>Panorama geral com total de tabelas e medidas:</p>
            <ul>
                <li><strong>Total de Tabelas:</strong> {len(tabelas)}</li>
                <li><strong>Total de Medidas:</strong> {len(medidas)}</li>
            </ul>
            <h3>Resumo por Tabela:</h3>
            <table>
                <tr><th>Tabela</th><th>Qtd. Medidas</th></tr>
                {''.join([f"<tr><td>{t}</td><td>{len(meds)}</td></tr>" for t, meds in resumo_medidas.items()])}
            </table>
        </div>

        <div class="section">
            <h2>📂 Tabelas do Modelo</h2>
            {''.join([
                f"<h3>🗂️ {t['name']}</h3><ul>" +
                (f"<li><strong>Descrição:</strong> {t.get('description', 'Sem descrição.')}</li>" if t.get("description") else "") +
                f"<li><strong>Colunas Visíveis:</strong> {', '.join([c['name'] for c in t.get('columns', []) if not c.get('isHidden', False)])}</li>" +
                "</ul><br>"
                for t in tabelas
            ])}
        </div>

        <div class="section">
            <h2>🧩 Medidas DAX</h2>
            {''.join([
                f"<h3>{m['nome']} ({m['tabela']})</h3>" +
                f"<p><strong>Complexidade:</strong> {m['complexidade']}</p>" +
                f"<pre>{m['expressao']}</pre>" +
                f"<p><strong>Explicação:</strong> {m.get('explicacao', 'Explicação não gerada.')}</p><br>"
                for m in medidas
            ])}
        </div>
    </body>
    </html>
    """
    return html
