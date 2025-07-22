import ollama

def explicar_medida_dax(nome, expressao_dax, modelo="mistral"):
    """
    Usa o modelo local via Ollama para explicar uma medida DAX.
    """
    prompt = f"""
Você é um especialista em Power BI e DAX. Recebe uma medida DAX e deve explicar de forma clara e simples o que ela faz.

Nome da Medida: {nome}
Expressão DAX:
{expressao_dax}

Explique de forma clara e objetiva, como se estivesse ensinando alguém que já entende de Power BI e lógica de programação, mas sem deixar de falar sobre a lógica base da medida.
Lembre que você tem um limite de 300 caracteres para dizer essa explicação.
"""

    try:
        resposta = ollama.chat(
            model=modelo,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return resposta['message']['content'].strip()

    except Exception as e:
        print(f"Erro ao tentar gerar explicação com o modelo {modelo}: {e}")
        return "Erro ao gerar explicação."

def explicar_tabela(nome_tabela, colunas, modelo="mistral"):
    """Gera uma breve descrição do papel de uma tabela em um modelo."""

    prompt = f"""
Você é um especialista em modelagem de dados. Analise o nome da tabela e a lista
de colunas a seguir e descreva, em até 300 caracteres, qual é o propósito dessa
tabela dentro de um modelo do Power BI.

Nome da Tabela: {nome_tabela}
Colunas: {', '.join(colunas)}
"""

    try:
        resposta = ollama.chat(
            model=modelo,
            messages=[{"role": "user", "content": prompt}]
        )
        return resposta["message"]["content"].strip()
    except Exception as e:
        return f"Erro ao gerar explicação: {e}"
