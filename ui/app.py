import streamlit as st
import tempfile
import os
import json
import hashlib
import time
from collections import defaultdict, Counter
import pandas as pd
import plotly.express as px
from io import BytesIO, StringIO
import streamlit.components.v1 as components

# 🔧 Corrige o caminho dos módulos internos
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

IGNORAR_TABELAS_PREFIXOS = ["DateTableTemplate", "LocalDateTable", "_", "~"]

from pbix_tools.extractor import (
    desmontar_pbix_com_pbitools,
    localizar_model_bim,
    parse_measures,
)
from dax_analyzer.explain import explicar_medida_dax, explicar_tabela
from pbix_tools.extractor import encontrar_dax_usadas_em_visuais
from utils import gerar_hash_medida, classificar_complexidade, carregar_cache, salvar_cache, gerar_html_relatorio

st.set_page_config(page_title="Power BI Analyzer com IA", layout="wide")

# === ESTILOS ===
st.markdown("""
<style>
    .big-title {
        font-size: 2.2em;
        font-weight: bold;
    }
    .subtitle {
        font-size: 1.2em;
        color: #6c757d;
    }
    .result-box {
        background-color: #f9f9f9;
        border-left: 5px solid #00afa0;
        padding: 10px;
        margin-bottom: 1rem;
    }
    .metric-line {
        font-size: 0.9em;
        color: #888;
    }
</style>
""", unsafe_allow_html=True)

# === SIDEBAR ===
st.sidebar.title("🔍 Navegação")
aba = st.sidebar.radio("Escolha uma seção:", ["📊 Overview", "🧩 Mapa de Medidas", "🔎 Pesquisa", "🛠️ Auditoria", "📂 Tabelas", "ℹ️ Como usar"])
modo_escuro = st.sidebar.toggle("🌙 Modo escuro", value=False)

# === TÍTULO ===
st.markdown("<div class='big-title'>🧠 Power BI Analyzer com IA (Ollama + Mistral)</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Envie um arquivo <code>.pbix</code> para extrair e explicar medidas DAX com IA local.</div>", unsafe_allow_html=True)

# === CACHE PERSISTENTE EM ARQUIVO ===
CACHE_PATH = ".cache/explicacoes.json"
os.makedirs(".cache", exist_ok=True)
cache_persistente = carregar_cache(CACHE_PATH)

def explicar_com_cache(nome, expressao):
    chave = gerar_hash_medida(nome, expressao)
    if chave in cache_persistente:
        return cache_persistente[chave]
    explicacao = explicar_medida_dax(nome, expressao)
    cache_persistente[chave] = explicacao
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache_persistente, f, indent=2, ensure_ascii=False)
    return explicacao

salvar_cache(CACHE_PATH, cache_persistente)

@st.cache_data(show_spinner=False)
def explicar_tabela_com_cache(nome, colunas):
    return explicar_tabela(nome, colunas)

# === UPLOAD ===
uploaded_file = st.file_uploader("Escolha um arquivo .pbix", type=["pbix"])

# === PROCESSAMENTO ===
if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pbix") as tmp:
        tmp.write(uploaded_file.read())
        pbix_path = tmp.name

    with st.spinner("Desmontando o .pbix com pbi-tools..."):
        pasta_extraida = desmontar_pbix_com_pbitools(pbix_path)

        if not pasta_extraida or not os.path.exists(pasta_extraida):
            st.error("❌ Erro: Não foi possível extrair o .pbix com o pbi-tools. Verifique o caminho do executável.")
        else:
            model_file = localizar_model_bim(pasta_extraida)
            nomes_usados_em_visuais = encontrar_dax_usadas_em_visuais(pasta_extraida)
            
            if not model_file:
                st.error("❌ Arquivo de modelo (model.bim ou model.json) não encontrado.")
            else:
                medidas = parse_measures(model_file)

                if not medidas:
                    st.warning("⚠️ Nenhuma medida DAX foi encontrada.")
                else:
                    for medida in medidas:
                        medida["complexidade"] = classificar_complexidade(medida.get("expressao", ""))

                    resumo = defaultdict(list)
                    for m in medidas:
                        resumo[m['tabela']].append(m)

                    if aba == "📊 Overview":
                        st.markdown("### 📊 Visão Geral do Modelo")
                        df_resumo = pd.DataFrame([{ "Tabela": t, "Qtd. Medidas": len(meds) } for t, meds in resumo.items()])
                        st.dataframe(df_resumo, use_container_width=True)

                        fig = px.bar(df_resumo, x="Tabela", y="Qtd. Medidas", color="Tabela",
                                     title="Distribuição de Medidas por Tabela", height=400)
                        st.plotly_chart(fig, use_container_width=True)

                    elif aba == "🧩 Mapa de Medidas":
                        st.markdown("### 🗺️ Mapa de Medidas por Tabela")
                        for tabela, lista in resumo.items():
                            st.markdown(f"**🗂️ {tabela}** — {len(lista)} medidas")

                    elif aba == "🔎 Pesquisa":
                        st.markdown("### 🔍 Pesquisa de Medidas DAX")

                        nomes_tabelas = sorted(resumo.keys())
                        filtro_tabela = st.sidebar.selectbox("Filtrar por tabela", ["Todas"] + nomes_tabelas)
                        filtro_nome = st.sidebar.text_input("Filtrar por nome da medida")
                        busca_texto = st.sidebar.text_input("Buscar trecho DAX (qualquer parte do código)")

                        resultados = []
                        barra_progresso = st.progress(0, text="🔄 Gerando explicações...")

                        total = len(medidas)
                        for i, medida in enumerate(medidas, start=1):
                            nome = medida.get("nome", "Sem nome")
                            expressao = medida.get("expressao", "")
                            tabela = medida.get("tabela", "Desconhecida")

                            if not isinstance(expressao, str):
                                st.warning(f"⚠️ Medida '{nome}' possui expressão malformada e foi ignorada.")
                                continue

                            hash_id = gerar_hash_medida(nome, expressao)

                            with st.expander(f"📌 {nome} ({medida['tabela']})", expanded=False):
                                st.code(expressao, language='dax')
                                explicacao = explicar_com_cache(nome, expressao)
                                medida["explicacao"] = explicacao
                                st.markdown(f"🧠 **Explicação gerada:**\n\n{explicacao}")
                                resultados.append(medida)

                            barra_progresso.progress(i / total, text=f"🔄 Processando {i}/{total} medidas...")

                            hash_id = gerar_hash_medida(nome, expressao)

                            with st.expander(f"📌 {nome} ({tabela})", expanded=False):
                                st.code(expressao, language='dax')
                                inicio = time.time()
                                explicacao = explicar_com_cache(nome, expressao)
                                fim = time.time()

                                medida["explicacao"] = explicacao
                                st.markdown(f"<div class='result-box'>🧠 <strong>Explicação gerada:</strong><br><br>{explicacao}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div class='metric-line'>🕒 Tempo: {fim - inicio:.2f}s | 🔍 Complexidade: {medida['complexidade']}</div>", unsafe_allow_html=True)
                                resultados.append(medida)

                        if resultados:
                            st.markdown("---")
                            st.markdown("### 📀 Baixar resultado em Excel")
                            df_resultados = pd.DataFrame(resultados)
                            excel_bytes = df_resultados.to_excel(index=False, engine="openpyxl")
                            st.download_button(
                                "📅 Baixar como Excel",
                                data=excel_bytes,
                                file_name="explicacoes_dax.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )

                    elif aba == "🛠️ Auditoria":
                        st.markdown("### 🛠️ Modo Auditoria")

                        nomes_duplicados = [item for item, count in Counter(m["expressao"] for m in medidas).items() if count > 1]
                        medidas_duplicadas = [m for m in medidas if m["expressao"] in nomes_duplicados]
                        medidas_genericas = [m for m in medidas if m["nome"].lower().startswith("measure") or "sem nome" in m["nome"].lower()]

                        st.subheader("🔁 Medidas Duplicadas")
                        for m in medidas_duplicadas:
                            st.markdown(f"- **{m['nome']}** na tabela *{m['tabela']}*")

                        st.subheader("⚠️ Medidas com Nome Genérico")
                        for m in medidas_genericas:
                            st.markdown(f"- **{m['nome']}** na tabela *{m['tabela']}*")
                        
                        st.subheader("🧹 Medidas Ociosas (não utilizadas em visuais)")

                        medidas_ociosas = [
                            m for m in medidas
                            if m["nome"].lower() not in nomes_usados_em_visuais
                        ]

                        if medidas_ociosas:
                            # Agrupa por tabela
                            agrupadas = defaultdict(list)
                            for m in medidas_ociosas:
                                agrupadas[m["tabela"]].append(m)

                            # Mostra resumo com quantidade por tabela
                            st.markdown("**Resumo por Tabela:**")
                            for tabela, lista in agrupadas.items():
                                st.markdown(f"- 🗂️ **{tabela}**: {len(lista)} medida(s) ociosa(s)")

                            st.divider()

                            # Filtro por tabela
                            opcoes_tabela = ["Todas"] + sorted(agrupadas.keys())
                            filtro_tabela_ociosas = st.selectbox("Filtrar por tabela (ociosas)", opcoes_tabela)

                            st.markdown("**🔎 Medidas ociosas detectadas:**")
                            for tabela, lista in agrupadas.items():
                                if filtro_tabela_ociosas != "Todas" and tabela != filtro_tabela_ociosas:
                                    continue
                                for m in lista:
                                    st.markdown(f"- **{m['nome']}** na tabela *{m['tabela']}*")

                        else:
                            st.success("✅ Nenhuma medida ociosa detectada com base nos visuais.")


                    elif aba == "📂 Tabelas":
                        st.markdown("### 📂 Tabelas do Modelo")

                        try:
                            with open(model_file, "r", encoding="utf-8") as f:
                                model_data = json.load(f)
                            tables = [t for t in model_data.get("model", {}).get("tables", [])
                                        if not any(t.get("name", "").startswith(prefixo) for prefixo in IGNORAR_TABELAS_PREFIXOS)]
                        except Exception as e:
                            st.error(f"❌ Erro ao carregar colunas do modelo: {e}")
                            tables = []

                        for tabela in tables:
                            nome = tabela.get("name", "Desconhecida")
                            colunas = [c.get("name") for c in tabela.get("columns", [])]

                            with st.expander(f"🗂️ {nome} ({len(colunas)} colunas)"):
                                st.markdown(f"**Colunas:** {', '.join(colunas)}")
                                explicacao = explicar_tabela_com_cache(nome, colunas)
                                st.markdown(f"🧠 **Explicação da tabela:** {explicacao}")
                    elif aba == "ℹ️ Como usar":
                            st.markdown("## ℹ️ Guia Rápido")
                            st.markdown("""
                        ### 📁 1. Faça o upload de um arquivo `.pbix`
                        - O arquivo precisa ser exportável e não protegido por senha.
                        - O tamanho máximo é de 200MB.

                        ### 🧠 2. Entenda o que será analisado
                        - Medidas DAX extraídas do modelo
                        - Complexidade de cada medida
                        - Uso ou não em visuais
                        - Sugestões automáticas via IA (local)

                        ### 🔍 3. Use as Abas:
                        - **Overview**: visão geral por tabela
                        - **Mapa de Medidas**: agrupamento por tabela
                        - **Pesquisa**: busca avançada por nome ou expressão
                        - **Auditoria**: medidas duplicadas, genéricas, ociosas
                        - **Tabelas**: explicações das tabelas via IA
                        - **Como usar**: (você está aqui)

                        ### 💾 4. Exportações
                        - Resultados podem ser baixados em Excel ou JSON.
                        """)    
if 'medidas' in st.session_state and 'tabelas' in st.session_state:
    st.divider()
    st.subheader("📄 Relatório Consolidado")

    if st.button("👀 Visualizar Relatório em HTML"):
        html_relatorio = gerar_html_relatorio(
            medidas=st.session_state.medidas,
            tabelas=st.session_state.tabelas,
            resumo_medidas=st.session_state.resumo_medidas
        )
        components.html(html_relatorio, height=1000, scrolling=True)

    # Gerar botão de download do HTML
    html_file = gerar_html_relatorio(
        medidas=st.session_state.medidas,
        tabelas=st.session_state.tabelas,
        resumo_medidas=st.session_state.resumo_medidas
    )
    html_bytes = BytesIO(html_file.encode("utf-8"))
    st.download_button(
        label="💾 Baixar Relatório HTML",
        data=html_bytes,
        file_name="relatorio_powerbi_analyzer.html",
        mime="text/html"
    )
