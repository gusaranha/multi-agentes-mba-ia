"""
ETAPA 1 -- Primeiro agente com tool local (15 min).

ESQUELETO: implemente as etapas na ordem. Cada uma está marcada com um comentário e um
raise NotImplementedError: troque esse raise pelo código da etapa e rode o arquivo.
  ETAPA 1.1 -- a tool consultar_servidor (SEM o salário)
  ETAPA 1.2 -- o agente AtendenteRH com a tool
  ETAPA 1.3 -- duas perguntas: uma que precisa da tool e uma que não precisa

REFERÊNCIAS NAS AULAS
  aula1/segundo_agente.py                            Agent + @function_tool + Runner.run_sync (o básico)
  exercicios_resolvidos/aula4/ex10_function_tool.py  tool que consulta uma TABELA e devolve JSON  <- o mais parecido
  aula8/exemplos/02_agente_tool/main.py              o agente decide quando chamar a tool (e quando não)

Rodar (a partir de aula10/):
    python etapa01_agente.py

Pronto quando: a tool é chamada só na primeira pergunta (o print dentro dela prova).
"""
import json

from agents import Agent, Runner, function_tool

from dados_rh import servidor_publico
from provedor import configurar

MODELO = configurar()  # LLM REAL: PROVEDOR no .env (openai ou ollama)


# ETAPA 1.1 -- a tool
#   - ponha um print("[tool] consultar_servidor", matricula) no começo, para provar quando ela roda;
#   - devolva json.dumps(servidor_publico(matricula), ensure_ascii=False). A consulta servidor_publico() (dados_rh.py)
#     já vem pronta: tira o salário (dado restrito, ver Etapas 5 e 9) e trata matrícula inexistente;
#   - capriche na DOCSTRING (com Args:): é o que o LLM lê para decidir chamar a tool. Esse é o ponto da etapa.
#   Referência: exercicios_resolvidos/aula4/ex10_function_tool.py (consultar_protocolo)
@function_tool
def consultar_servidor(matricula: str) -> str:
    """Consulta o cadastro de UM servidor pela matrícula: nome, cargo, equipe, saldo de férias (em dias),
    abonos restantes no ano e a matrícula da chefia imediata. Não devolve o salário.

    Use quando a pergunta for sobre os dados de um servidor específico (ex.: "quantos dias de férias a
    matrícula 1002 ainda tem?"). Não use para dúvidas gerais sobre normas ou conceitos.

    Args:
        matricula: matrícula do servidor, só os dígitos (ex.: "1002").

    Returns:
        JSON com os dados do servidor, ou {"erro": "matrícula não encontrada"} se ela não existir.
    """
    print("[tool] consultar_servidor", matricula)
    return json.dumps(servidor_publico(matricula), ensure_ascii=False)


def criar_atendente() -> Agent:
    # ETAPA 1.2 -- o agente
    #   Agent(name="AtendenteRH", instructions=..., tools=[consultar_servidor])
    #   Instruções: atende servidores, responde em português e de forma breve, usa a tool quando a pergunta
    #   for sobre os dados de UM servidor, e não inventa saldo de cabeça.
    #   Referência: aula1/segundo_agente.py
    return Agent(
        name="AtendenteRH",
        instructions=(
            "Você é o atendente do RH e tira dúvidas dos servidores. Responda sempre em português e de forma breve. "
            "Quando a pergunta for sobre os dados de UM servidor (saldo de férias, abonos, equipe, chefia), use a tool "
            "consultar_servidor com a matrícula informada; nunca invente saldos ou dados de cabeça. "
            "Para dúvidas gerais (conceitos, o que é algo), responda direto, sem chamar a tool. "
            "Se a matrícula não for encontrada, diga isso ao servidor."
        ),
        tools=[consultar_servidor],
    )


def main() -> None:
    # ETAPA 1.3 -- rode as duas perguntas com Runner.run_sync e imprima resultado.final_output
    #   1) "Quantos dias de férias a matrícula 1002 ainda tem?"   (precisa da tool)
    #   2) "O que é abono pecuniário?"                            (não precisa)
    #   Referência: aula8/exemplos/02_agente_tool/main.py

    atendente = criar_atendente()
    resultado = Runner.run_sync(atendente, "Quantos dias de férias a matrícula 50000 ainda tem?")
    print(resultado.final_output)

    for pergunta in ("Quantos dias de férias a matrícula 1002 ainda tem?", "O que é abono pecuniário?"):
        resultado = Runner.run_sync(atendente, pergunta)
        print(resultado.final_output)


if __name__ == "__main__":
    print(f"[modelo] {MODELO}")
    main()
