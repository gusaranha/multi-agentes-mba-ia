"""
ETAPA 2 -- Extração estruturada do pedido (15 min) e 🆕 A -- votação em paralelo (OPCIONAL, bônus).

ESQUELETO: implemente as etapas na ordem (troque cada raise NotImplementedError pelo código da etapa).
  ETAPA 2.1 -- complete o modelo Pydantic `Pedido` (campos + Field(description=...))
  ETAPA 2.2 -- criar_extrator(): um Agent com output_type=Pedido
  ETAPA 2.3 -- extrair(): roda UM extrator e devolve um Pedido
  --- daqui para baixo é OPCIONAL (item 🆕 A, vale bônus). Pule se estiver sem tempo: o resto do sistema não depende dele.
  🆕 A.1    -- INSTRUCOES_VOTANTES: 3 instruções ligeiramente diferentes
  🆕 A.2    -- extrair_com_votacao(): os 3 extratores AO MESMO TEMPO (asyncio.gather)
  (PRONTO)  -- votar(): maioria por campo; sem maioria em tipo/datas -> divergencia=True
  (PRONTO)  -- no __main__: o tempo em paralelo x em sequência

REFERÊNCIAS NAS AULAS
  aula2/agente_output.py                   output_type com um BaseModel simples
  aula2/agente_output2.py                  Enum + listas + Field(description=...)          <- o mais parecido
  aula7/exemplos/08_paralelismo/main.py    🆕 A: o CONCEITO de paralelismo (lá: tarefas DIFERENTES para ganhar tempo;
                                           aqui: a MESMA tarefa 3 vezes para ganhar confiabilidade)
  aula3/agente_parada3.py                  Runner.run (assíncrono) dentro de asyncio, como em A.2
  aula3/agente_retry.py                    por que a data de hoje entra nas instruções (já feito abaixo, com texto_hoje())

Rodar:
    python etapa02_extracao.py            # extrai C1, C2, C5 e C11
    python etapa02_extracao.py --votacao  # 🆕 A: C1, C2 e C9 com 3 votos e o tempo medido

Pronto quando: C2 sai com dias_vendidos=10, C11 com tipo_destino="exterior", C5 com matricula=None;
               na votação, C1/C2 unânimes e C9 mostrando os votos.
"""
import asyncio
import re
import sys
import time
from collections import Counter
from datetime import date
from enum import Enum

from agents import Agent, ModelSettings, Runner
from pydantic import BaseModel, Field, field_validator, model_validator

from dados.casos import CASOS
from etapa04_ferramentas import texto_hoje
from provedor import configurar

MODELO = configurar()


class TipoPedido(str, Enum):
    FERIAS = "ferias"
    ABONO = "abono"
    DIARIA = "diaria"
    LICENCA_SAUDE = "licenca_saude"
    OUTRO = "outro"


class TipoDestino(str, Enum):
    CAPITAL = "capital"
    INTERIOR = "interior"
    EXTERIOR = "exterior"


class Pedido(BaseModel):
    # ETAPA 2.1 -- complete os campos. O primeiro já está pronto como modelo.
    #   matricula: str | None          (4 dígitos; None se o servidor não informou)
    #   data_inicio: str | None        (AAAA-MM-DD)
    #   data_fim: str | None           (AAAA-MM-DD; no abono, igual à data_inicio)
    #   dias_vendidos: int             (0 a 10; abono pecuniário, regra N2 -- use Field(default=0, ge=0, le=10, ...))
    #   destino: str | None            (só para diária: a cidade)
    #   tipo_destino: TipoDestino | None
    #   justificativa: str             (resumo do motivo, sem dados de saúde)
    #   Escreva a DESCRIPTION de cada um: é a "instrução" que o LLM lê para preencher o campo.
    #   Referência: aula2/agente_output2.py (Ocorrencia, Envolvido, PapelEnvolvido)
    tipo: TipoPedido = Field(description=(
        "Tipo do pedido: 'ferias' (descanso anual, pode incluir venda de dias), 'abono' (folga de 1 dia útil), "
        "'diaria' (viagem a serviço), 'licenca_saude' (afastamento por doença) ou 'outro'."))
    matricula: str | None = Field(default=None, description=(
        "Matrícula do servidor: EXATAMENTE os 4 dígitos que ele escreveu, sem letras nem zeros a mais "
        "(ex.: 'Matrícula 1002' -> '1002'). null se o servidor não informou a matrícula."))
    data_inicio: str | None = Field(default=None, description=(
        "Primeiro dia do pedido, no formato AAAA-MM-DD. null se o servidor não disse o dia exato "
        "(ex.: 'em agosto' ou 'perto da Páscoa' NÃO são datas exatas)."))
    data_fim: str | None = Field(default=None, description=(
        "Último dia do pedido, no formato AAAA-MM-DD. No abono (1 dia), é igual à data_inicio. "
        "null se o servidor não disse o dia exato."))
    dias_vendidos: int = Field(default=0, ge=0, le=10, description=(
        "Dias de férias que o servidor quer VENDER (abono pecuniário, regra N2), de 0 a 10. "
        "Só preencha se ele pedir explicitamente para vender dias; caso contrário, 0."))
    destino: str | None = Field(default=None, description=(
        "Só para diária: a cidade de destino da viagem (ex.: 'Buenos Aires'). null nos outros tipos."))
    tipo_destino: TipoDestino | None = Field(default=None, description=(
        "Só para diária: 'exterior' para QUALQUER cidade fora do Brasil (inclusive capitais de outros países, como "
        "Buenos Aires ou Lisboa); 'capital' só para Brasília e capitais de estados brasileiros; 'interior' para as "
        "demais cidades do Brasil. null nos outros tipos."))
    justificativa: str = Field(default="", description=(
        "Resumo curto do motivo do pedido, em português. NUNCA inclua dados de saúde (CID, diagnóstico) nem CPF."))

    # Rede de segurança para modelos menores (ex.: llama3.1 no Ollama): o que vier fora do formato vira null,
    # e o sistema pede o dado ao servidor em vez de seguir com um valor inventado ou malformado.
    @field_validator("matricula", "data_inicio", "data_fim", "destino", "tipo_destino", mode="before")
    @classmethod
    def _texto_nulo_vira_none(cls, valor):
        # a PALAVRA "null" escrita como texto
        if isinstance(valor, str) and valor.strip().lower() in ("", "null", "none", "n/a"):
            return None
        return valor

    @field_validator("matricula")
    @classmethod
    def _matricula_com_4_digitos(cls, valor):
        # 'F00001002' -> '1002'; o que não der 4 dígitos vira null
        if valor is None:
            return None
        digitos = re.sub(r"\D", "", valor).lstrip("0")
        return digitos if len(digitos) == 4 else None

    @field_validator("data_inicio", "data_fim")
    @classmethod
    def _data_completa(cls, valor):
        # '2027-08-null' ou 'agosto de 2027' não são datas exatas; '2026-11-31' (conta errada do LLM) não existe
        if valor is None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
            return None
        try:
            date.fromisoformat(valor)
        except ValueError:
            return None
        return valor

    @model_validator(mode="after")
    def _coerente_com_o_tipo(self):
        if self.tipo != TipoPedido.DIARIA:  # destino só existe em diária
            self.destino, self.tipo_destino = None, None
        if self.tipo == TipoPedido.ABONO and self.data_fim is None:  # abono é de 1 dia
            self.data_fim = self.data_inicio
        return self


def criar_extrator(instrucoes: str, input_guardrails: list | None = None) -> Agent:
    # ETAPA 2.2 -- devolva Agent(name="Extrator", instructions=instrucoes, output_type=Pedido,
    #   input_guardrails=input_guardrails or [])
    #   (os guardrails só entram na Etapa 3; até lá, a lista fica vazia)
    return Agent(name="Extrator", instructions=instrucoes, output_type=Pedido, input_guardrails=input_guardrails or [],
                 model_settings=ModelSettings(temperature=0))  # extração: o mesmo texto deve dar o mesmo Pedido


# Exemplos fictícios (DIFERENTES dos casos de teste): modelos menores acertam muito mais o formato vendo exemplos.
EXEMPLOS = """
Exemplos:
- "Matrícula 2001. Quero férias de 03/05/2027 a 17/05/2027."
  -> tipo=ferias, matricula="2001", data_inicio="2027-05-03", data_fim="2027-05-17", dias_vendidos=0,
     destino=null, tipo_destino=null
- "Sou a 2002 e quero folgar no dia 14/06/2027 usando um abono."
  -> tipo=abono, matricula="2002", data_inicio="2027-06-14", data_fim="2027-06-14", destino=null, tipo_destino=null
- "Quero tirar umas férias no fim do ano."
  -> tipo=ferias, matricula=null, data_inicio=null, data_fim=null, dias_vendidos=0, destino=null, tipo_destino=null
- "Matrícula 2003. Vou a Lisboa a trabalho de 10/09/2027 a 12/09/2027 para uma reunião."
  -> tipo=diaria, matricula="2003", data_inicio="2027-09-10", data_fim="2027-09-12", destino="Lisboa",
     tipo_destino=exterior
- "Matrícula 2004. Vou a Campinas a serviço em 05/10/2027."
  -> tipo=diaria, matricula="2004", data_inicio="2027-10-05", data_fim="2027-10-05", destino="Campinas",
     tipo_destino=interior
(null significa deixar o campo VAZIO; nunca escreva a palavra "null" como texto.)
"""

INSTRUCOES_EXTRATOR = (
    f"Hoje é {texto_hoje()}. "  # (PRONTO) a data real: o modelo não tem relógio (aula3/agente_retry.py)
    "Você extrai pedidos de servidores para o RH (férias, abono ou diária). "
    "Regras: "
    "1) Datas no formato AAAA-MM-DD, com o dia, o mês e o ANO que o servidor escreveu (DD/MM/AAAA -> AAAA-MM-DD). "
    "2) Não invente o que não foi dito: matrícula, datas, destino ou tipo de destino ausentes ou vagos ficam null "
    "(um mês ou uma época do ano não é data exata). "
    "3) A matrícula são os 4 dígitos que o servidor escreveu, sem nada a mais. "
    "4) Viagem a serviço (congresso, curso, reunião, evento em outra cidade) é 'diaria', nunca 'ferias'. "
    "5) No abono, data_fim é igual à data_inicio. "
    "6) dias_vendidos só é diferente de 0 se o servidor pedir explicitamente para vender dias de férias. "
    "7) Cidade fora do Brasil é tipo_destino 'exterior', mesmo que seja a capital de outro país."
    + EXEMPLOS
)


def extrair(texto: str) -> Pedido:
    # ETAPA 2.3 -- rode criar_extrator(INSTRUCOES_EXTRATOR) com Runner.run_sync e devolva final_output
    #   (é um objeto Pedido, não texto!)
    return Runner.run_sync(criar_extrator(INSTRUCOES_EXTRATOR), texto).final_output


# ------------------------------------------------------------------ 🆕 A: votação (OPCIONAL, bônus)
# Para ligar no grafo depois de pronto: USAR_VOTACAO = True em etapa07_grafo.py.
# 🆕 A.1 -- três instruções LIGEIRAMENTE diferentes para a MESMA tarefa (comece cada uma com f"Hoje é {texto_hoje()}. ")
#   ex.: um extrator literal; um que confere as datas contra o calendário; um que "pensa como o RH".
_REGRAS_COMUNS = (
    "Datas no formato AAAA-MM-DD, com o ano escrito pelo servidor; o que não foi dito (ou é vago, como um mês ou uma "
    "época) fica null. A matrícula são os 4 dígitos escritos. Viagem a serviço é 'diaria'; cidade fora do Brasil é "
    "'exterior'. No abono, data_fim = data_inicio. dias_vendidos só se o servidor pedir explicitamente para vender dias."
    + EXEMPLOS
)
INSTRUCOES_VOTANTES: list[str] = [
    f"Hoje é {texto_hoje()}. Você extrai pedidos de servidores para o RH de forma LITERAL: copie exatamente o que o "
    "servidor escreveu, sem interpretar nem completar nada. " + _REGRAS_COMUNS,
    f"Hoje é {texto_hoje()}. Você extrai pedidos de servidores para o RH e CONFERE AS DATAS contra o calendário: "
    "verifique o dia da semana citado, se o fim não é anterior ao início e se o ano está certo. " + _REGRAS_COMUNS,
    f"Hoje é {texto_hoje()}. Você é um analista experiente do RH: leia o pedido como o RH leria e identifique o tipo "
    "(férias, abono, diária, licença de saúde ou outro) pelo que o servidor realmente quer. " + _REGRAS_COMUNS,
]


async def extrair_com_votacao(texto: str) -> tuple[Pedido, bool, list[Pedido]]:
    # 🆕 A.2 -- crie os 3 extratores e rode-os AO MESMO TEMPO:
    #     resultados = await asyncio.gather(*(Runner.run(e, texto) for e in extratores))
    #   depois chame votar([r.final_output for r in resultados]) e devolva (pedido_final, divergencia, votos).
    #   Conceito: aula7/exemplos/08_paralelismo/main.py (fan-out/fan-in), aqui em asyncio, sem grafo.
    extratores = [criar_extrator(instrucoes) for instrucoes in INSTRUCOES_VOTANTES]
    resultados = await asyncio.gather(*(Runner.run(e, texto) for e in extratores))
    votos = [r.final_output for r in resultados]
    pedido, divergencia = votar(votos)
    return pedido, divergencia, votos


def votar(votos: list[Pedido]) -> tuple[Pedido, bool]:
    """(PRONTO) Maioria por campo. Sem maioria (2 de 3) em `tipo` ou nas datas -> divergencia=True: o sistema vai
    pedir esclarecimento em vez de adivinhar. Os campos não votados vêm do primeiro voto."""
    decidido, divergencia = {}, False
    for campo in ("tipo", "matricula", "data_inicio", "data_fim", "dias_vendidos"):
        valor, quantos = Counter(getattr(voto, campo) for voto in votos).most_common(1)[0]
        decidido[campo] = valor
        if quantos < 2 and campo in ("tipo", "data_inicio", "data_fim"):
            divergencia = True
    return votos[0].model_copy(update=decidido), divergencia


def _demo_extracao() -> None:
    for nome in ("C1_abono_simples", "C2_ferias_com_venda", "C5_sem_matricula", "C11_diaria_exterior"):
        pedido = extrair(CASOS[nome]["pedido"])
        print(f"\n{nome}\n  {pedido.model_dump()}")


def _demo_votacao() -> None:
    for nome in ("C1_abono_simples", "C2_ferias_com_venda", "C9_divergencia"):
        texto = CASOS[nome]["pedido"]
        inicio = time.perf_counter()
        pedido, divergencia, votos = asyncio.run(extrair_com_votacao(texto))
        segundos = time.perf_counter() - inicio
        print(f"\n{nome}  ({segundos:.1f}s, divergencia={divergencia})")
        for i, voto in enumerate(votos, 1):
            print(f"  voto {i}: tipo={voto.tipo.value} {voto.data_inicio}..{voto.data_fim} vende={voto.dias_vendidos}")
        print(f"  decisão: {pedido.model_dump()}")
    # (PRONTO) os mesmos 3 extratores EM SEQUÊNCIA, para comparar: o paralelo fica perto do tempo de UMA chamada?
    texto = CASOS["C2_ferias_com_venda"]["pedido"]
    inicio = time.perf_counter()
    for instrucoes in INSTRUCOES_VOTANTES:
        Runner.run_sync(criar_extrator(instrucoes), texto)
    print(f"\nC2 em sequência: {time.perf_counter() - inicio:.1f}s (compare com o tempo do C2 em paralelo, acima)")


if __name__ == "__main__":
    print(f"[modelo] {MODELO}")
    _demo_votacao() if "--votacao" in sys.argv else _demo_extracao()
