"""
ETAPA 6 -- Os especialistas, cada um com UMA responsabilidade e SÓ as tools de que precisa.

ESQUELETO:
  ETAPA 6.1 -- criar_normas(), criar_escala(), criar_financeiro(), criar_redator()
  ETAPA 6.2 -- criar_coordenador(): usa Normas, Escala e Financeiro como TOOLS (as_tool)

As tools abaixo (PRONTAS) só repassam a chamada ao MCP Server do RH (cliente_mcp.chamar_mcp_async). Dar a cada agente
só as tools dele é o PRIVILÉGIO MÍNIMO (Etapa 9.1); o hook do 🆕 B (etapa10_governanca.py) confere isso em tempo de execução.

REFERÊNCIAS NAS AULAS
  aula4/ex03_agente_as_tool.py                         Coordenador que chama especialistas como tools    <- o mais parecido
  aula2/agente_handoff2.py                             as_tool com tool_name e tool_description
  aula4/ex02_handoff_roteamento.py                     handoff: compare (quem responde no fim?)
  aula7/exemplos/02_agentes_especializados/main.py     uma responsabilidade por agente
  aula7/agentes.py                                     ModelSettings(temperature=0) para respostas mais estáveis
  aula8/exemplos/06_excessive_agency/1_codigo_pronto/main.py   o problema de dar tools DEMAIS a um agente
"""
import json

from agents import Agent, ModelSettings, RunContextWrapper, RunHooks, function_tool

from etapa05_cliente_mcp import chamar_mcp_async
from etapa04_ferramentas import cotacao_usd_brl

CONFIG = ModelSettings(temperature=0)


# ------------------------------------------------------------------ tools (PRONTAS)
@function_tool
async def consultar_normas(tema: str) -> str:
    """Regras da norma interna sobre um tema: férias, prazos, escala, abono, diária, aprovação, saúde ou dados."""
    return json.dumps(await chamar_mcp_async("consultar_normas", {"tema": tema}), ensure_ascii=False)


@function_tool
async def consultar_escala(equipe: str, inicio: str, fim: str) -> str:
    """Afastamentos da equipe que se sobrepõem ao período (AAAA-MM-DD) e o limite de afastados da regra N5."""
    return json.dumps(await chamar_mcp_async("consultar_escala", {"equipe": equipe, "inicio": inicio, "fim": fim}),
                      ensure_ascii=False)


@function_tool
async def tabela_diarias(tipo_destino: str) -> str:
    """Moeda e valor da diária para o tipo de destino: capital, interior ou exterior."""
    return json.dumps(await chamar_mcp_async("tabela_diarias", {"tipo_destino": tipo_destino}), ensure_ascii=False)


@function_tool
async def consultar_remuneracao(matricula: str) -> str:
    """[RESTRITA] Salário-base de um servidor. Só para calcular a venda de férias (N2)."""
    print(f"[tool] consultar_remuneracao({matricula}) EXECUTOU")  # o 🆕 B prova que, barrada, ela NÃO executa
    return json.dumps(await chamar_mcp_async("consultar_remuneracao", {"matricula": matricula}), ensure_ascii=False)


@function_tool
def cotacao_dolar() -> str:
    """Cotação atual do dólar em reais (USD->BRL). Devolve 'indisponível' se a API falhar: nunca invente o câmbio."""
    cotacao = cotacao_usd_brl()
    return f"{cotacao:.4f}" if cotacao else "indisponível"


# ------------------------------------------------------------------ ETAPA 6.1: especialistas
def criar_normas() -> Agent:
    # ETAPA 6.1 -- Agent(name="Normas", instructions=..., tools=[consultar_normas], model_settings=CONFIG)
    #   Responsabilidade: dizer QUAIS regras se aplicam ao pedido e explicá-las em linguagem simples.
    #   NÃO calcula valores, NÃO consulta a escala. Recebe também as violações objetivas (etapa06_regras.py) para explicá-las.
    return Agent(
        name="Normas",
        instructions=_instrucoes_normas,
        tools=[consultar_normas],
        model_settings=CONFIG,
    )


INSTRUCOES_NORMAS = (
    "Você é o especialista em NORMAS do RH. Sua única responsabilidade é dizer quais regras da norma interna "
    "(N1 a N10) se aplicam ao pedido recebido e explicá-las em linguagem simples, em português e de forma breve. "
    "Use a tool consultar_normas com o tema do pedido (férias, abono ou diária) e também 'prazos' e 'aprovação'. "
    "Liste as regras CUMPRIDAS e as VIOLADAS. As violações objetivas já foram calculadas pelo sistema e são a "
    "LISTA COMPLETA: só as regras dessa lista estão violadas. Se ela disser 'nenhuma', NENHUMA "
    "regra foi violada e você não aponta violação nenhuma. NÃO recalcule datas, saldos nem prazos; só explique. "
    "Lembre: a N3 (início proibido) vale só para FÉRIAS; abono sem violação é deferido SEM a chefia (N8). "
    "Não consulte a escala nem calcule valores: isso é de outros especialistas."
)


def _instrucoes_normas(ctx: RunContextWrapper, agente: Agent) -> str:
    """Acrescenta a data de hoje e as violações objetivas que vêm no context do Runner (o as_tool repassa o context
    ao especialista). Assim os fatos chegam ao Normas pelo código, sem depender do Coordenador repassá-los no texto."""
    fatos = ctx.context if isinstance(ctx.context, dict) else {}
    if "violacoes" not in fatos:
        return INSTRUCOES_NORMAS
    return (f"{INSTRUCOES_NORMAS}\n\nFATOS DO SISTEMA (definitivos, prevalecem sobre a entrada):\n"
            f"- HOJE (data do pedido): {fatos['hoje']}\n"
            f"- REGRAS CUMPRIDAS (já conferidas, não recalcule): {', '.join(fatos.get('cumpridas', [])) or 'nenhuma'}\n"
            f"- VIOLAÇÕES OBJETIVAS: {fatos['violacoes'] or 'nenhuma'}")


def criar_escala() -> Agent:
    # ETAPA 6.1 -- tools=[consultar_escala]. Confere a N5 e, se houver conflito, SUGERE outro período
    #   (com o mesmo número de dias, começando num dia permitido).
    return Agent(
        name="Escala",
        instructions=(
            "Você é o especialista em ESCALA do RH. Sua única responsabilidade é conferir a regra N5: na mesma equipe, "
            "no máximo `limite_afastados` servidores afastados no mesmo dia. Use a tool consultar_escala com a equipe do "
            "servidor e o período do pedido (datas AAAA-MM-DD). Não conte o próprio servidor entre os afastados. "
            "Responda em português e de forma breve: quem já está afastado no período e se há conflito. "
            "Se houver conflito, SUGIRA outro período com o mesmo número de dias, começando depois do fim do afastamento "
            "que conflita, numa segunda-feira (para respeitar a N3), e confira a sugestão com consultar_escala. Se a "
            "entrada trouxer um PERÍODO SUGERIDO calculado pelo sistema, use exatamente esse. "
            "Não fale de valores nem de outras regras."
        ),
        tools=[consultar_escala],
        model_settings=CONFIG,
    )


def criar_financeiro() -> Agent:
    # ETAPA 6.1 -- tools=[tabela_diarias, consultar_remuneracao, cotacao_dolar].
    #   Venda de férias (N2): dias_vendidos x salario_base / 30. Diárias (N7): uma por pernoite + meia no retorno;
    #   no exterior, em USD convertido pela cotação. Mostre a conta. Câmbio indisponível -> "a calcular".
    #   É o ÚNICO agente que vê o salário.
    return Agent(
        name="Financeiro",
        instructions=(
            "Você é o especialista FINANCEIRO do RH e o ÚNICO que pode consultar o salário. Responda em português, de "
            "forma breve, e MOSTRE A CONTA.\n"
            "- Férias com venda de dias (N2): valor = dias_vendidos x salario_base / 30. Use consultar_remuneracao com a "
            "matrícula do servidor. Sem dias vendidos, diga que não há valor a pagar.\n"
            "- Diária (N7): uma diária por dia com pernoite e MEIA diária no dia do retorno (de 08 a 11 = 3 pernoites "
            "+ meia = 3,5 diárias). Use tabela_diarias com o tipo de destino. No exterior o valor é em USD: converta "
            "com cotacao_dolar; se a cotação vier 'indisponível', escreva o valor em USD e 'valor em reais: a calcular'. "
            "Nunca invente câmbio.\n"
            "- Abono: não há valor a calcular.\n"
            "Não repita o salário na resposta: informe só o valor calculado."
        ),
        tools=[tabela_diarias, consultar_remuneracao, cotacao_dolar],
        model_settings=CONFIG,
    )


def criar_redator() -> Agent:
    # ETAPA 6.1 -- sem tools. Escreve o DESPACHO (deferimento ou indeferimento) usando SÓ os fatos recebidos:
    #   matrícula, período, decisão, regras citadas, valores e, no indeferimento, a sugestão de datas.
    #   Nunca escreve CPF nem dado de saúde (N10). Se receber um feedback (da validação ou da chefia), corrige.
    return Agent(
        name="Redator",
        instructions=(
            "Você é o REDATOR do RH e escreve o DESPACHO da decisão de um pedido, em português formal e conciso "
            "(um parágrafo). Use SÓ os fatos recebidos: não invente datas, valores nem regras.\n"
            "A DECISÃO, as REGRAS CUMPRIDAS e as VIOLAÇÕES vêm prontas do sistema e são FINAIS: escreva exatamente essa "
            "decisão. No DEFERIMENTO, fundamente nas REGRAS CUMPRIDAS e não fale em violação nem em novo período. No "
            "INDEFERIMENTO, cite como violadas só as regras da lista VIOLAÇÕES. Os PARECERES servem só para os valores "
            "calculados e para a sugestão de novo período.\n"
            "O despacho deve conter: a matrícula do servidor; o tipo de pedido; o período com a data de início "
            "(DD/MM/AAAA); a decisão com a palavra 'DEFERIDO' ou 'INDEFERIDO'; as regras que a fundamentam; os valores "
            "calculados, se houver; e, no indeferimento, a sugestão de novo período, se houver.\n"
            "Se a decisão depender da chefia, escreva que o deferimento está sujeito à aprovação da chefia imediata.\n"
            "NUNCA escreva CPF, CID, diagnóstico, salário ou qualquer informação de saúde (N10).\n"
            "Se receber um FEEDBACK (da validação ou da chefia), reescreva o despacho corrigindo exatamente o que foi "
            "pedido. Devolva só o texto do despacho."
        ),
        model_settings=CONFIG,
    )


# ------------------------------------------------------------------ ETAPA 6.2: coordenador
def criar_coordenador(hooks: RunHooks | None = None, tools_extras: list | None = None) -> Agent:
    # ETAPA 6.2 -- Agent(name="Coordenador", instructions=..., tools=[
    #       criar_normas().as_tool(tool_name="parecer_normas", tool_description=..., hooks=hooks,
    #                              failure_error_function=None),
    #       criar_escala().as_tool(tool_name="parecer_escala", ..., hooks=hooks, failure_error_function=None),
    #       criar_financeiro().as_tool(tool_name="parecer_financeiro", ..., hooks=hooks, failure_error_function=None),
    #       *(tools_extras or [])])
    #   O Coordenador decide QUAIS especialistas consultar (abono não precisa do Financeiro) e junta os pareceres.
    #   hooks=hooks nas as_tool faz o hook do 🆕 B enxergar também as tools DENTRO de cada especialista.
    #   failure_error_function=None: sem isso, um erro dentro do especialista (inclusive o bloqueio do 🆕 B) vira só
    #   um texto de erro para o Coordenador, que segue em frente. Com None, o erro interrompe a execução.
    #   tools_extras serve só para o teste do 🆕 B (dar de propósito consultar_remuneracao ao Coordenador).
    #   Referência: aula4/ex03_agente_as_tool.py
    return Agent(
        name="Coordenador",
        instructions=(
            "Você é o COORDENADOR da análise de pedidos do RH. Você não consulta dados direto: pede pareceres aos "
            "especialistas, que são as suas tools, repassando a cada um os fatos do pedido.\n"
            "- parecer_normas: sempre.\n"
            "- parecer_escala: férias e abono (regra N5). Diária não precisa.\n"
            "- parecer_financeiro: férias com dias vendidos e diárias. Abono não precisa.\n"
            "Depois junte os pareceres num PARECER ÚNICO, em português e breve, com uma seção por especialista e a "
            "conclusão. As violações objetivas da entrada são a lista COMPLETA e definitiva: se houver alguma, a "
            "conclusão é pelo indeferimento; se for 'nenhuma', a conclusão é pelo deferimento. Não aponte outras "
            "violações além dessas."
        ),
        tools=[
            criar_normas().as_tool(
                tool_name="parecer_normas",
                tool_description="Especialista em normas: quais regras (N1-N10) se aplicam ao pedido, cumpridas e violadas.",
                hooks=hooks, failure_error_function=None),
            criar_escala().as_tool(
                tool_name="parecer_escala",
                tool_description="Especialista em escala: confere a N5 na equipe e sugere outro período se houver conflito.",
                hooks=hooks, failure_error_function=None),
            criar_financeiro().as_tool(
                tool_name="parecer_financeiro",
                tool_description="Especialista financeiro: valor da venda de férias (N2) ou das diárias (N7), com a conta.",
                hooks=hooks, failure_error_function=None),
            *(tools_extras or []),
        ],
        model_settings=CONFIG,
    )
