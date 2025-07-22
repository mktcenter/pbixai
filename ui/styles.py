import streamlit as st

def carregar_css_externo():
    with open("styles.css") as f:
        css = f"<style>{f.read()}</style>"
        st.markdown(css, unsafe_allow_html=True)

def apply_custom_styles(modo_escuro: bool = False):
    primary = "#00afa0" if not modo_escuro else "#2a2a2a"
    background = "#ffffff" if not modo_escuro else "#1e1e1e"
    text = "#333333" if not modo_escuro else "#ffffff"
    secondary = "#f9f9f9" if not modo_escuro else "#1e1e1e"
    border_color = "#e0e0e0" if not modo_escuro else "#444"

    style = f"""
    <style>
        html, body {{
            font-family: 'Inter', sans-serif;
            background-color: {background};
            color: {text};
            transition: background-color 0.3s ease, color 0.3s ease;
        }}

        .big-title {{
            font-size: 2.4em;
            font-weight: 700;
            color: {primary};
            margin-bottom: 0.5em;
        }}

        .subtitle {{
            font-size: 1.2em;
            color: #999;
        }}

        .card {{
            background-color: {secondary};
            padding: 1.25rem;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            border: 1px solid {border_color};
            margin-bottom: 1rem;
            transition: all 0.3s ease;
        }}

        .card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        }}

        .topbar {{
            background-color: {secondary};
            padding: 1rem 1.5rem;
            border-bottom: 1px solid {border_color};
            margin-bottom: 1rem;
            border-radius: 12px 12px 0 0;
        }}

        .tag {{
            font-size: 0.75em;
            background-color: {primary};
            color: white;
            padding: 4px 10px;
            border-radius: 6px;
            margin-left: 8px;
            display: inline-block;
        }}

        .stButton > button {{
            background-color: {primary};
            color: white;
            padding: 0.5rem 1.2rem;
            border: none;
            border-radius: 6px;
            font-weight: bold;
            transition: background-color 0.3s ease, transform 0.2s ease;
        }}

        .stButton > button:hover {{
            background-color: #00796b;
            transform: scale(1.02);
            font-color: #000000;
        }}

        @media (max-width: 768px) {{
            .big-title {{
                font-size: 1.8em;
            }}
            .card {{
                padding: 1rem;
            }}
        }}

        /* Sidebar geral */
        section[data-testid="stSidebar"] {{
            background-color: {secondary};
            border-right: 1px solid {border_color};
            transition: background-color 0.3s ease;
        }}

        /* Título da sidebar */
        section[data-testid="stSidebar"] .css-1v3fvcr {{
            color: {primary};
            font-weight: bold;
            font-size: 1.2em;
            padding-bottom: 0.5rem;
        }}

        /* Inputs e selects na sidebar */
        section[data-testid="stSidebar"] .stSelectbox, 
        section[data-testid="stSidebar"] .stTextInput, 
        section[data-testid="stSidebar"] .stRadio {{
            background-color: {background};
            color: {text};
            border-radius: 6px;
            padding: 0.25rem 0.5rem;
        }}

        /* Botões de toggle e radio */
        section[data-testid="stSidebar"] label {{
            color: {text};
        }}

        /* Toggle switch */
        section[data-testid="stSidebar"] .stToggleSwitch span {{
            background-color: {primary};
        }}
    </style>
    """
    st.markdown(style, unsafe_allow_html=True)
