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
    """
    Usa IA local via Ollama para gerar uma explicação sobre a função de uma tabela,
    com base no nome e nas colunas.
    """
    prompt = f"""
Você é um especialista em modelagem de dados. A seguir, será fornecida uma tabela de um modelo do Power BI. Com base no nome da tabela e nos nomes das colunas, escreva uma frase clara e objetiva que descreva o propósito principal dessa tabela no contexto do negócio.

Contexto:
Os dados são da Beep Saúde, uma startup de saúde com sede no Rio de Janeiro e atuação nacional por meio de hubs de atendimento.

Importante: Considere os seguintes significados para termos frequentes nos nomes das colunas ou tabelas:

HC: Refere-se ao Headcount (contagem de colaboradores), voltado para o RH.

Beep: Refere-se a um chamado de atendimento domiciliar.

Slot: Significa um espaço disponível para ser preenchido por um atendimento.

BU: Unidade de negócio, como Imunizações, Laboratório ou Híbrido.

HUB: Unidade operacional de onde saem os atendimentos.

Campos com técnica se referem ao nome da técnica de enfermagem associada à informação.

Seu objetivo é gerar uma explicação simples, clara e que comunique para que serve a tabela no modelo de dados.
Tabela: {nome_tabela}
Colunas: {', '.join(colunas)}

Explique de forma clara e objetiva.
"""
    try:
        resposta = ollama.chat(
            model=modelo,
            messages=[{"role": "user", "content": prompt}]
        )
        return resposta["message"]["content"].strip()
    except Exception as e:
        return f"Erro ao gerar explicação: {e}"