import streamlit as st
import tempfile
import os
import json
import hashlib
import time
from collections import defaultdict, Counter
import pandas as pd
import plotly.express as px
import sys
from io import BytesIO
import streamlit.components.v1 as components
import shutil

# Corrige o caminho dos módulos internos (mantido como no original)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- Constantes ---
IGNORAR_TABELAS_PREFIXOS = ["DateTableTemplate", "LocalDateTable", "_", "~"]
CACHE_PATH = ".cache/explicacoes.json"

# Importações dos Módulos do Projeto
try:
    from pbix_tools.extractor import (
        desmontar_pbix_com_pbitools,
        localizar_model_bim,
        parse_measures, # Assumindo que parse_measures só pega medidas
        encontrar_dax_usadas_em_visuais,
        localizar_database_modelo,
        carregar_tabelas_modelo
    )

    from dax_analyzer.explain import explicar_medida_dax, explicar_tabela
    from utils import gerar_hash_medida, classificar_complexidade, carregar_cache, salvar_cache, gerar_html_relatorio
    from ui.styles import apply_custom_styles
except ImportError as e:
    st.error(f"Erro ao importar módulos necessários: {e}. Verifique a estrutura do projeto e as dependências.")
    st.stop() # Impede a execução do resto do script se módulos essenciais faltarem

# Configuração da Página
st.set_page_config(page_title="Power BI Analyzer com IA", layout="wide")

# Cache e Estado
os.makedirs(".cache", exist_ok=True)
cache_persistente_explicacoes = carregar_cache(CACHE_PATH)

# Funções Auxiliares com Cache
# Cache para explicações de Medidas (cache em arquivo JSON)
def explicar_medida_com_cache(nome, expressao, cache_dict):
    """Verifica cache ou gera explicação para medida, atualizando o dict."""
    chave = gerar_hash_medida(nome, expressao)
    if chave not in cache_dict:
        # Só chama a IA se não estiver no cache
        # Adicionar tratamento de erro para a chamada da IA
        try:
            explicacao = explicar_medida_dax(nome, expressao)
            cache_dict[chave] = explicacao # Atualiza o dicionário em memória
        except Exception as e:
            st.warning(f"⚠️ Erro ao gerar explicação para '{nome}': {e}. Usando placeholder.")
            cache_dict[chave] = f"Erro ao gerar explicação: {e}" # Salva erro no cache para não tentar de novo
    return cache_dict[chave]

# Cache para explicações de Tabelas (usando cache do Streamlit)
# @st.cache_data(show_spinner="Analisando estrutura da tabela com IA...")
def explicar_tabela_com_cache(_nome_tabela, _colunas_tupla):
    """Gera explicação para tabela usando cache do Streamlit."""
    colunas_list = list(_colunas_tupla)

    # Adicionar tratamento de erro para a chamada da IA
    try:
        return explicar_tabela(_nome_tabela, colunas_list)
    except Exception as e:
        st.warning(f"⚠️ Erro ao gerar explicação para tabela '{_nome_tabela}': {e}. Retornando mensagem de erro.")
        return f"Erro ao gerar explicação para a tabela: {e}"


# --- Interface do Usuário (Sidebar) ---
st.sidebar.title("🔍 Navegação")
abas_disponiveis = ["📊 Overview", "🧩 Mapa de Medidas", "🔎 Pesquisa", "🛠️ Auditoria", "📂 Tabelas", "ℹ️ Como usar"]
# Desabilitar abas que dependem do PBIX até que um seja carregado
abas_habilitadas = ["ℹ️ Como usar"]
if 'medidas' in st.session_state:
    abas_habilitadas = abas_disponiveis

# Usar estado da sessão para manter a aba selecionada após o re-run do upload
if 'selected_tab' not in st.session_state:
    st.session_state.selected_tab = "ℹ️ Como usar"

# Garantir que a aba selecionada seja válida
if st.session_state.selected_tab not in abas_habilitadas:
     st.session_state.selected_tab = "📊 Overview" if 'medidas' in st.session_state else "ℹ️ Como usar"

# Obter índice da aba selecionada para o radio
try:
    indice_aba_selecionada = abas_habilitadas.index(st.session_state.selected_tab)
except ValueError:
    indice_aba_selecionada = 0 # Padrão para a primeira aba habilitada

aba = st.sidebar.radio(
    "Escolha uma seção:",
    abas_habilitadas,
    index=indice_aba_selecionada,
    key="navigation_radio" # Adicionar uma chave para estabilidade
)
# Atualizar estado da sessão quando o rádio mudar
st.session_state.selected_tab = aba

modo_escuro = st.sidebar.toggle("🌙 Modo escuro", value=st.session_state.get('dark_mode', False))
st.session_state.dark_mode = modo_escuro # Salvar estado do modo escuro
apply_custom_styles(modo_escuro)


# Título 
st.markdown("<div class='big-title'>🧠 Power BI Analyzer com IA (Ollama + Mistral)</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Envie um arquivo <code>.pbix</code> para extrair e explicar medidas DAX com IA local.</div>", unsafe_allow_html=True)


# Upload
uploaded_file = st.file_uploader("Escolha um arquivo .pbix", type=["pbix"], key="pbix_uploader")

# Processamento 
# Usar st.session_state para armazenar dados processados e evitar reprocessamento desnecessário
if uploaded_file is not None and 'medidas' not in st.session_state:
    pbix_path = None # Inicializar
    pasta_extraida = None
    # Limpar cache de explicações de tabelas do Streamlit em novo upload
    # explicar_tabela_com_cache.clear()
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pbix") as tmp:
            tmp.write(uploaded_file.read())
            pbix_path = tmp.name

        with st.spinner("Desmontando o .pbix com pbi-tools..."):
            start_time = time.time()
            pasta_extraida = desmontar_pbix_com_pbitools(pbix_path)
            end_time = time.time()
            st.info(f"PBIX desmontado em {end_time - start_time:.2f} segundos.")

        if not pasta_extraida or not os.path.exists(pasta_extraida):
            st.error("❌ Erro: Não foi possível extrair o .pbix com o pbi-tools. Verifique a instalação e o caminho.")
            st.stop()

        model_file = localizar_model_bim(pasta_extraida)
        if not model_file:
            model_file = localizar_database_modelo(pasta_extraida)
            st.error("❌ Arquivo de modelo (model.bim ou DataModelSchema) não encontrado na pasta extraída.")
            st.stop()

        with st.spinner("Analisando o modelo (medidas, tabelas, colunas)..."):
            start_time = time.time()

            # 1. Carregar Medidas
            medidas_raw = parse_measures(model_file)

            # 2. Carregar Tabelas (lendo o mesmo arquivo de modelo)
            try:
                 with open(model_file, "r", encoding="utf-8") as f:
                     model_json = json.load(f)

                 model_content = model_json.get("model", model_json)
                 tabelas_raw = carregar_tabelas_modelo(model_file, pasta_extraida)
                
                 st.code(tabelas_raw[:2], language="json")

                 st.session_state.tabelas = [
                    t for t in tabelas_raw
                    if not any(t.get("name", "").startswith(prefixo) for prefixo in IGNORAR_TABELAS_PREFIXOS)
                 ]
            except Exception as e:
                st.error(f"❌ Erro ao carregar tabelas do modelo: {e}")
                st.session_state.tabelas = []

            # 3. Processar Medidas carregadas
            st.session_state.medidas = []
            if not medidas_raw:
                st.warning("⚠️ Nenhuma medida DAX foi encontrada no modelo.")
            else:
                 for medida in medidas_raw:
                    expressao = medida.get("expression", medida.get("expressao", "")) # Trata os dois nomes comuns
                    nome_medida = medida.get("name", medida.get("nome", "Sem Nome")) # Padroniza chave nome
                    tabela_medida = medida.get("table", medida.get("tabela", "Desconhecida")) # Padroniza chave tabela

                    if isinstance(expressao, str): # Garante que é string
                        medida_processada = {
                            "nome": nome_medida,
                            "tabela": tabela_medida,
                            "expressao": expressao,
                            "complexidade": classificar_complexidade(expressao)
                        }
                        st.session_state.medidas.append(medida_processada)
                    else:
                        st.warning(f"⚠️ Medida '{nome_medida}' (Tabela: {tabela_medida}) possui expressão inválida ou ausente e foi ignorada.")

            end_time = time.time()
            st.success(f"Modelo analisado em {end_time - start_time:.2f} segundos. {len(st.session_state.medidas)} medidas e {len(st.session_state.tabelas)} tabelas encontradas.")

            # 4. Encontrar DAX usadas em visuais (após extração bem sucedida)
            with st.spinner("Verificando uso de medidas em visuais..."):
                 start_time = time.time()
                 st.session_state.nomes_usados_em_visuais = encontrar_dax_usadas_em_visuais(pasta_extraida)
                 end_time = time.time()
                 st.info(f"Verificação de uso em visuais concluída em {end_time - start_time:.2f} segundos.")


            # 5. Agrupar medidas por tabela para resumos
            st.session_state.resumo_medidas = defaultdict(list)
            for m in st.session_state.medidas:
                st.session_state.resumo_medidas[m['tabela']].append(m)

            # Forçar re-run para atualizar a UI com os dados carregados e habilitar as abas
            st.rerun()

    except FileNotFoundError as e:
         st.error(f"❌ Erro: Arquivo ou diretório não encontrado. O `pbi-tools` está instalado e no PATH? Detalhes: {e}")
    except Exception as e:
         st.error(f"❌ Ocorreu um erro inesperado durante o processamento inicial: {e}")
         # Limpar estado se o processamento falhar
         keys_to_clear = ['medidas', 'tabelas', 'resumo_medidas', 'nomes_usados_em_visuais', 'selected_tab']
         for key in keys_to_clear:
             if key in st.session_state:
                 del st.session_state[key]
    finally:
        # --- CORREÇÃO: Limpeza do arquivo temporário ---
        if pbix_path and os.path.exists(pbix_path):
            try:
                os.remove(pbix_path)
                # st.info("Arquivo temporário .pbix removido.") # Opcional: Mensagem de log
            except OSError as e:
                st.warning(f"Não foi possível remover o arquivo temporário {pbix_path}. Erro: {e}")
        # Limpeza da pasta extraída
        if pasta_extraida and os.path.exists(pasta_extraida):
            try:
                shutil.rmtree(pasta_extraida)
                st.info("Pasta extraída removida.") # Opcional
            except OSError as e:
                st.warning(f"Não foi possível remover a pasta extraída {pasta_extraida}. Erro: {e}")


# --- Exibição das Abas (apenas se os dados foram carregados) ---
if 'medidas' in st.session_state:
    # Recupera os dados do estado da sessão para usar nas abas
    medidas = st.session_state.medidas
    resumo = st.session_state.get('resumo_medidas', defaultdict(list)) # Usa get com default
    nomes_usados_em_visuais = st.session_state.get('nomes_usados_em_visuais', set()) # Usa get com default
    cache_modificado = False # Flag para salvar o cache JSON apenas se necessário

    # --- ABA: Overview ---
    if aba == "📊 Overview":
        st.markdown("### 📊 Visão Geral do Modelo")
        tabelas = st.session_state.get('tabelas', [])
        if resumo:
            # Contar tabelas e medidas
            num_tabelas = len(tabelas)
            num_medidas = len(medidas)
            st.metric("Total de Tabelas (Modelo)", num_tabelas)
            st.metric("Total de Medidas", num_medidas)

            df_resumo = pd.DataFrame([{ "Tabela": t, "Qtd. Medidas": len(meds) } for t, meds in resumo.items()])
            df_resumo = df_resumo.sort_values(by="Qtd. Medidas", ascending=False).reset_index(drop=True)
            st.dataframe(df_resumo, use_container_width=True)

            # Gráfico apenas se houver dados
            if not df_resumo.empty:
                fig = px.bar(df_resumo, x="Tabela", y="Qtd. Medidas", color="Tabela",
                             title="Distribuição de Medidas por Tabela", height=400)
                fig.update_layout(xaxis={'categoryorder':'total descending'}) # Ordena barras
                st.plotly_chart(fig, use_container_width=True)
            else:
                 st.info("Gráfico não gerado pois não há medidas nas tabelas encontradas.")

        else:
            st.info("Nenhuma medida encontrada para gerar o overview.")

    # --- ABA: Mapa de Medidas ---
    elif aba == "🧩 Mapa de Medidas":
        st.markdown("### 🗺️ Mapa de Medidas por Tabela")
        if resumo:
            tabelas_ordenadas = sorted(resumo.keys())
            for tabela in tabelas_ordenadas:
                lista = resumo[tabela]
                with st.expander(f"🗂️ **{tabela}** — {len(lista)} medida(s)", expanded=False):
                    medidas_ordenadas = sorted(lista, key=lambda m: m['nome'])
                    for m in medidas_ordenadas:
                        cor_complexidade = {"Simples": "green", "Intermediária": "orange", "Avançada": "red", "Desconhecida": "grey"}
                        # Usando HTML para cor (alternativa ao CSS se `apply_custom_styles` não cobrir isso)
                        cor = cor_complexidade.get(m['complexidade'], "grey")
                        st.markdown(f"- **{m['nome']}** <span style='color:{cor}; font-weight:bold;'>[{m['complexidade']}]</span>", unsafe_allow_html=True)
                        # Opcional: Popover para ver DAX
                        with st.popover("👁️ Ver DAX"):
                             st.code(m['expressao'], language='dax')
        else:
            st.info("Nenhuma medida encontrada para exibir no mapa.")

    # --- ABA: Pesquisa ---
    elif aba == "🔎 Pesquisa":
        st.markdown("### 🔍 Pesquisa e Explicação de Medidas DAX")

        # Filtros na Sidebar
        nomes_tabelas_filtro = sorted(resumo.keys())
        if not nomes_tabelas_filtro: # Se não houver tabelas com medidas
             st.warning("Nenhuma tabela com medidas encontrada para filtro.")
             filtro_tabela = "Todas"
             nomes_tabelas_filtro = [] # Evita erro no selectbox
        else:
            filtro_tabela = st.sidebar.selectbox("Filtrar por tabela", ["Todas"] + nomes_tabelas_filtro, key="filtro_tabela_pesquisa")

        filtro_nome = st.sidebar.text_input("Filtrar por nome da medida (contém)", key="filtro_nome_pesquisa")
        busca_texto = st.sidebar.text_input("Buscar trecho no código DAX (contém)", key="busca_texto_pesquisa")
        # Filtro de complexidade (Opcional)
        complexidades_disponiveis = ["Todas", "Simples", "Intermediária", "Avançada", "Desconhecida"]
        filtro_complexidade = st.sidebar.select_slider(
             "Filtrar por Complexidade (igual ou maior que):",
             options=complexidades_disponiveis,
             value="Todas", # Padrão
             key="filtro_complexidade_pesquisa"
        )


        # Aplicar filtros ANTES de iterar
        medidas_filtradas = medidas
        if filtro_tabela != "Todas":
            medidas_filtradas = [m for m in medidas_filtradas if m['tabela'] == filtro_tabela]
        if filtro_nome:
            medidas_filtradas = [m for m in medidas_filtradas if filtro_nome.lower() in m['nome'].lower()]
        if busca_texto:
            medidas_filtradas = [m for m in medidas_filtradas if busca_texto.lower() in m['expressao'].lower()]

        # Aplicar filtro de complexidade
        if filtro_complexidade != "Todas":
             niveis_complexidade = {"Simples": 1, "Intermediária": 2, "Avançada": 3, "Desconhecida": 0}
             nivel_minimo = niveis_complexidade.get(filtro_complexidade, 0)
             medidas_filtradas = [
                  m for m in medidas_filtradas
                  if niveis_complexidade.get(m['complexidade'], 0) >= nivel_minimo
             ]


        st.info(f"Exibindo {len(medidas_filtradas)} de {len(medidas)} medidas após filtros.")

        if not medidas_filtradas:
            st.warning("Nenhuma medida corresponde aos filtros selecionados.")
        else:
            resultados_explicacao = []
            total_filtradas = len(medidas_filtradas)
            # Opcional: Botão para gerar todas as explicações de uma vez
            if st.button(f"Gerar Explicações para {total_filtradas} medidas filtradas"):
                gerar_explicacoes = True
            else:
                gerar_explicacoes = False # Ou gerar sob demanda no expander

            barra_progresso = st.progress(0, text=f"🔄 Preparando para gerar explicações ({total_filtradas} medidas)...")
            start_expl_time = time.time()

            # Ordenar medidas filtradas para exibição
            medidas_filtradas.sort(key=lambda m: (m['tabela'], m['nome']))

            for i, medida in enumerate(medidas_filtradas, start=1):
                nome = medida["nome"]
                expressao = medida["expressao"]
                tabela = medida["tabela"]
                complexidade = medida["complexidade"]

                # Atualiza barra ANTES da chamada potencialmente longa
                barra_progresso.progress(i / total_filtradas, text=f"🔄 Processando {i}/{total_filtradas}: '{nome}' ({tabela})")

                # Usar um expander para cada medida
                with st.expander(f"📌 {nome} ({tabela}) - Complexidade: {complexidade}", expanded=False):
                    st.code(expressao, language='dax')

                    # Gerar explicação ao expandir
                    chave_cache = gerar_hash_medida(nome, expressao)
                    if chave_cache in cache_persistente_explicacoes:
                        explicacao = cache_persistente_explicacoes[chave_cache]
                        st.markdown(f"🧠 **Explicação (do cache):**\n\n{explicacao}")
                    else:
                        # Botão para gerar explicação sob demanda dentro do expander
                        if st.button(f"🧠 Gerar explicação para '{nome}'", key=f"explain_{chave_cache}"):
                            with st.spinner(f"Gerando explicação com IA..."):
                                explicacao = explicar_medida_com_cache(nome, expressao, cache_persistente_explicacoes)
                                if "Erro ao gerar explicação" not in explicacao:
                                     cache_modificado = True # Marcar que o cache foi alterado
                                st.markdown(f"🧠 **Explicação gerada:**\n\n{explicacao}")
                                # Adiciona à lista para download APENAS se gerada com sucesso?
                                if "Erro ao gerar explicação" not in explicacao:
                                    medida["explicacao"] = explicacao
                                    resultados_explicacao.append(medida)
                        else:
                             st.caption("Clique no botão acima para gerar a explicação com IA.")


            barra_progresso.progress(1.0, text=f"✅ Processamento concluído para {total_filtradas} medidas em {time.time() - start_expl_time:.2f}s.")

            # Download: Coletar todas as explicações do cache para o download,
            if st.button("Preparar Download Excel (com explicações geradas/cacheadas)"):
                 with st.spinner("Coletando dados para o Excel..."):
                    resultados_completos = []
                    for medida_orig in medidas: # Iterar sobre TODAS as medidas originais
                        chave = gerar_hash_medida(medida_orig['nome'], medida_orig['expressao'])
                        if chave in cache_persistente_explicacoes:
                            medida_com_expl = medida_orig.copy() # Copiar para não alterar original
                            medida_com_expl['explicacao'] = cache_persistente_explicacoes[chave]
                            resultados_completos.append(medida_com_expl)

                    if resultados_completos:
                        df_resultados = pd.DataFrame(resultados_completos)
                        colunas_excel = ['tabela', 'nome', 'expressao', 'complexidade', 'explicacao']
                        for col in colunas_excel:
                            if col not in df_resultados.columns:
                                df_resultados[col] = None # Adiciona coluna se faltar
                        df_resultados = df_resultados[colunas_excel] # Ordena e seleciona

                        from io import BytesIO
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_resultados.to_excel(writer, index=False, sheet_name='Explicacoes_DAX')
                        excel_bytes = output.getvalue()

                        st.download_button(
                            label=f"📅 Baixar {len(resultados_completos)} Medidas com Explicação",
                            data=excel_bytes,
                            file_name=f"explicacoes_dax_{uploaded_file.name.replace('.pbix','')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="download_excel_button"
                        )
                    else:
                        st.warning("Nenhuma explicação encontrada no cache ou gerada para incluir no download.")


    # --- ABA: Auditoria ---
    elif aba == "🛠️ Auditoria":
        st.markdown("### 🛠️ Auditoria de Medidas")

        if not medidas:
             st.info("Nenhuma medida carregada para auditoria.")
        else:
            col1, col2 = st.columns(2)

            with col1:
                # Código de Medidas Duplicadas (sem alteração)
                st.subheader("🔁 Medidas Duplicadas")
                expressoes_contadas = Counter(m["expressao"] for m in medidas)
                expressoes_duplicadas = {expr for expr, count in expressoes_contadas.items() if count > 1}
                medidas_duplicadas = [m for m in medidas if m["expressao"] in expressoes_duplicadas]
                if medidas_duplicadas:
                    medidas_duplicadas.sort(key=lambda m: (m['tabela'], m['nome']))
                    st.warning(f"**{len(medidas_duplicadas)}** instâncias de medidas com código DAX duplicado.")
                    with st.expander("Ver detalhes das duplicadas"):
                        for m in medidas_duplicadas:
                            st.markdown(f"- **{m['nome']}** (Tabela: *{m['tabela']}*)")
                            st.code(m['expressao'], language='dax')
                else:
                    st.success("✅ Nenhuma medida duplicada encontrada.")


            with col2:
                # Medidas Genéricas
                st.subheader("📝 Medidas com Nome Genérico")
                medidas_genericas = [
                    m for m in medidas
                    if m["nome"].lower().startswith("measure") or "sem nome" in m["nome"].lower() or m["nome"].lower() == "medida"
                ]
                if medidas_genericas:
                     medidas_genericas.sort(key=lambda m: (m['tabela'], m['nome']))
                     st.warning(f"**{len(medidas_genericas)}** medidas com nomes genéricos.")
                     with st.expander("Ver detalhes das genéricas"):
                        for m in medidas_genericas:
                            st.markdown(f"- **{m['nome']}** (Tabela: *{m['tabela']}*)")
                else:
                     st.success("✅ Nenhuma medida com nome genérico encontrada.")


            st.divider()
            # Medidas Ociosas
            st.subheader("🧹 Medidas Ociosas (não usadas diretamente em visuais)")
            st.caption("Nota: Esta análise verifica apenas o uso direto em visuais do Power BI. Medidas podem ser usadas por outras medidas.")
            nomes_usados_lower = {name.lower() for name in nomes_usados_em_visuais}
            medidas_ociosas = [
                m for m in medidas
                if m["nome"].lower() not in nomes_usados_lower
            ]

            if medidas_ociosas:
                agrupadas_ociosas = defaultdict(list)
                for m in medidas_ociosas:
                    agrupadas_ociosas[m["tabela"]].append(m)

                st.warning(f"**{len(medidas_ociosas)}** medidas potencialmente ociosas encontradas.")

                # Mostra resumo com quantidade por tabela
                resumo_ociosas_df = pd.DataFrame([
                    {"Tabela": tabela, "Qtd. Ociosas": len(lista)}
                    for tabela, lista in agrupadas_ociosas.items()
                ]).sort_values(by="Qtd. Ociosas", ascending=False).reset_index(drop=True)
                st.dataframe(resumo_ociosas_df, use_container_width=True, hide_index=True)


                # Filtro por tabela para detalhe
                opcoes_tabela_ociosas = ["Todas"] + sorted(agrupadas_ociosas.keys())
                filtro_tabela_ociosas = st.selectbox(
                    "Ver detalhes das ociosas por tabela:",
                    opcoes_tabela_ociosas,
                    key="filtro_tabela_ociosas"
                )

                # Mostra detalhes filtrados
                if filtro_tabela_ociosas != "Todas":
                    if filtro_tabela_ociosas in agrupadas_ociosas:
                        st.markdown(f"**🔎 Medidas ociosas na tabela '{filtro_tabela_ociosas}':**")
                        medidas_filtradas_ociosas = sorted(agrupadas_ociosas[filtro_tabela_ociosas], key=lambda m: m['nome'])
                        for m in medidas_filtradas_ociosas:
                            st.markdown(f"- **{m['nome']}**")
                else:
                    # Detalhe de todas em expanders
                    st.markdown("**🔎 Detalhe de todas as medidas ociosas:**")
                    for tabela, lista in sorted(agrupadas_ociosas.items()):
                         with st.expander(f"🗂️ {tabela} ({len(lista)} ociosas)"):
                             medidas_ordenadas = sorted(lista, key=lambda m: m['nome'])
                             for m in medidas_ordenadas:
                                 st.markdown(f"- **{m['nome']}**")

            else:
                st.success("✅ Nenhuma medida aparentemente ociosa detectada (com base no uso direto em visuais).")

    # --- ABA: Tabelas ---
  
    elif aba == "📂 Tabelas":
        tabelas = st.session_state.get('tabelas', [])
        st.markdown("### 📂 Análise das Tabelas do Modelo")

        if not tabelas:
             st.warning("Nenhuma tabela encontrada ou carregada para análise.")
             st.code(st.session_state.get("tabelas", []), language="json")
        else:
             st.info(f"{len(tabelas)} tabelas encontradas (excluindo tabelas internas/ocultas e calculadas).")
             # Adicionar filtro para tabelas ocultas/visíveis
             filtro_visibilidade = st.radio("Mostrar Tabelas:", ["Todas", "Visíveis", "Ocultas"], horizontal=True, key="filtro_visibilidade_tabela")

             tabelas_filtradas = tabelas # Começa com todas
             if filtro_visibilidade == "Visíveis":
                 tabelas_filtradas = [t for t in tabelas if not t.get("isHidden", False)]
             elif filtro_visibilidade == "Ocultas":
                 tabelas_filtradas = [t for t in tabelas if t.get("isHidden", False)]


             for tabela in sorted(tabelas_filtradas, key=lambda t: t.get("name", "")): # Ordenar tabelas
                nome_tabela = tabela.get("name", "Desconhecida")
                colunas_raw = tabela.get("columns", [])
                # Filtrar colunas: ignorar RowNumber, Variation e talvez ocultas?
                colunas = sorted([
                    c.get("name") for c in colunas_raw
                    if c.get("type") != "rowNumber"
                    and not c.get("isNameInferred", False) # Ignora colunas de variação
                    and not c.get("isHidden", False) # Mostra apenas colunas visíveis por padrão? Ajustável.
                ])
                n_colunas_visiveis = len(colunas)
                n_colunas_total = len(colunas_raw)

                descricao = tabela.get("description", None)
                is_hidden = tabela.get("isHidden", False)

                expander_title = f"🗂️ {nome_tabela} ({n_colunas_visiveis} colunas visíveis / {n_colunas_total} total)"
                if is_hidden:
                    expander_title += " (Tabela Oculta)"

                with st.expander(expander_title):
                    if descricao:
                        st.markdown(f"**Descrição da Tabela:** {descricao}")
                    st.markdown(f"**Colunas Visíveis ({n_colunas_visiveis}):**")
                    if colunas:
                         st.markdown(f"`{', '.join(colunas)}`")
                    else:
                         st.caption("Nenhuma coluna visível encontrada nesta tabela (podem existir colunas ocultas ou de sistema).")

                    # Gerar explicação da IA sob demanda
                    if colunas: # Só tenta explicar se tiver colunas visíveis
                        tupla_colunas = tuple(colunas) # Cria a tupla para o cache
                        chave_botao_tabela = f"explain_table_{hashlib.md5(nome_tabela.encode()).hexdigest()}"
                        if st.button("🧠 Analisar Tabela com IA", key=chave_botao_tabela):
                            # Chama a função cacheada com os argumentos corretos
                            explicacao_tabela = explicar_tabela_com_cache(nome_tabela, tupla_colunas)
                            st.markdown(f"**Análise IA da tabela:**\n\n{explicacao_tabela}")
                        else:
                             st.caption("Clique no botão para gerar uma análise da estrutura e possível propósito da tabela com IA.")

                    else:
                        st.markdown("_Análise IA não disponível (sem colunas visíveis)._")

    # --- ABA: Como Usar ---
    elif aba == "ℹ️ Como usar":
        # Código da aba "Como usar" (mantido como no original)
        st.markdown("## ℹ️ Guia Rápido")
        st.markdown("""
        ### 📁 1. Faça o upload de um arquivo `.pbix`
        - Clique no botão "Browse files" ou arraste um arquivo `.pbix` para a área indicada.
        - O arquivo precisa ser desprotegido (sem senha de abertura).
        - O processamento pode levar alguns segundos ou minutos dependendo do tamanho do arquivo e da complexidade do modelo.

        ### 🧠 2. Entenda o que será analisado
        - **Medidas DAX:** Código, complexidade (Simples, Intermediária, Avançada) e explicação gerada por IA (sob demanda na aba Pesquisa).
        - **Tabelas:** Nomes, colunas (visíveis) e análise geral pela IA (sob demanda na aba Tabelas).
        - **Auditoria:** Verificação de medidas duplicadas, com nomes genéricos ou potencialmente não utilizadas em visuais.

        ### 🔍 3. Use as Abas de Navegação (Sidebar à Esquerda)
        - **📊 Overview**: Quantidade de medidas por tabela e gráfico de distribuição. Métricas totais.
        - **🧩 Mapa de Medidas**: Lista de medidas agrupadas por tabela com indicador de complexidade. Popover para ver DAX.
        - **🔎 Pesquisa**: Visualize medidas filtradas (tabela, nome, DAX, complexidade). Gere explicações da IA sob demanda clicando nos botões. Prepare e baixe um Excel com as explicações disponíveis.
        - **🛠️ Auditoria**: Encontre possíveis problemas como duplicação, nomes ruins ou medidas ociosas. Detalhes em expanders.
        - **📂 Tabelas**: Veja a lista de tabelas, suas colunas visíveis e gere explicações da IA sob demanda.
        - **ℹ️ Como usar**: Este guia.

        ### ✨ 4. Recursos Adicionais
        - **Modo Escuro:** Alterne no sidebar para melhor visualização.
        - **Cache:** Explicações geradas pela IA são salvas localmente (`.cache/explicacoes.json`) para acelerar análises futuras do mesmo arquivo ou de medidas idênticas. O cache de tabelas usa a memória do Streamlit.
        - **Download:** Na aba "Pesquisa", após gerar/carregar explicações, clique em "Preparar Download Excel" para baixar um arquivo `.xlsx`.

        ### ⚠️ Limitações
        - A análise de "Medidas Ociosas" verifica apenas o uso *direto* em visuais do Power BI. Uma medida pode ser considerada "ociosa" aqui, mas ser usada como dependência por *outra* medida.
        - A qualidade da explicação da IA depende do modelo configurado (Ollama + Mistral, neste caso) e da clareza do código DAX/estrutura da tabela.
        - A geração de explicações da IA pode levar tempo, especialmente para muitas medidas ou tabelas complexas. Por isso, agora é feita sob demanda.
        - Requer que o `pbi-tools` esteja instalado e acessível no ambiente onde o script é executado.
        """)

    # --- Salvar Cache JSON ---
    # Salvar o cache JSON uma única vez no final, se modificado
    if cache_modificado:
        try:
            salvar_cache(CACHE_PATH, cache_persistente_explicacoes)
            # Usar st.toast para feedback não intrusivo
            st.toast("💾 Cache de explicações de medidas atualizado!", icon="✅")
        except Exception as e:
            st.sidebar.error(f"Erro ao salvar o cache: {e}")


elif uploaded_file is None:
    # Mensagem inicial ou quando nenhum arquivo é carregado
    st.info("⬅️ Por favor, faça o upload de um arquivo `.pbix` para começar a análise.")
    # Limpar estado se o usuário remover o arquivo ou ocorrer erro grave antes do processamento
    keys_to_clear = ['medidas', 'tabelas', 'resumo_medidas', 'nomes_usados_em_visuais', 'selected_tab']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


# Footer ou informações adicionais (opcional)
st.sidebar.markdown("---")
st.sidebar.info("Power BI Analyzer v0.4 (IA sob Demanda)")

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