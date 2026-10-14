# Entrega: Assistente de Gestão de Pessoas

**Aluno(s):**
**Até onde chegou:** ( ) Marco mínimo (Etapa 6)  ( ) Marco completo (Etapa 9)  ( ) Etapas 10–11
**Opcionais e bônus feitos:** ( ) 🆕 A  ( ) 🆕 B  ( ) 🆕 C  ( ) Outro: ______

## Etapa 0: quem verifica cada regra?

| Regra | Tema | Quem verifica (função Python / agente / humano) | Por quê | Onde foi implementada (preencha na Etapa 11) |
|---|---|---|---|---|
| N1 | férias | Função Python | Conta objetiva (dias do período ≥ 5 e ≤ saldo do cadastro): resultado exato e testável, sem depender do LLM | |
| N2 | férias | Função Python (limite e saldo) + agente Financeiro (valor da venda) | Limite de 10 dias e saldo são comparações exatas; o Financeiro só calcula `salario_base / 30` e é o único que vê o salário (privilégio mínimo) | |
| N3 | férias | Função Python (com feriados da BrasilAPI e plano B offline) | Data de início × fins de semana e feriados é cálculo de calendário; um LLM erraria dias da semana e feriados | |
| N4 | prazos | Função Python | Antecedência em dias corridos/úteis a partir de hoje é aritmética de datas, determinística | |
| N5 | escala | Função Python (dados do MCP `consultar_escala`) + agente Escala (sugere outro período) | Contar afastados × limite é objetivo; sugerir nova data em linguagem natural é tarefa do agente | |
| N6 | abono | Função Python | Dia útil e saldo de abonos são verificações exatas no calendário e no cadastro | |
| N7 | diária | Agente Financeiro (tools `tabela_diarias` e `cotacao_dolar`) | Precisa combinar tabela, pernoites, meia diária e câmbio e mostrar a conta; sem cotação escreve "a calcular", nunca inventa | |
| N8 | aprovação | Função Python (`precisa_chefia`) + humano (chefia via `interrupt()`) + MCP Server (autorização) | A decisão de deferir é humana; quem pode aprovar (chefia certa, nunca o próprio servidor) é garantido no servidor, não no prompt | |
| N9 | saúde | Guardrail de entrada (regex de CID + classificador de escopo) | Dado de saúde deve ser barrado ANTES de chegar a qualquer agente ou ser gravado | |
| N10 | dados | Guardrail de entrada (regex de CPF/CID) + guardrail de saída no despacho + instrução do Redator | Proteção de dados não pode depender só do LLM: a checagem por regex na saída garante que o despacho não vaze CPF/CID | |

## Etapa 11: os 12 casos

Compare **caminho e estado**, não o texto do despacho.

| Caso | Caminho percorrido | Resultado (bloqueado / pediu dados / triagem humana / indeferido / pausou na chefia / registrado + protocolo) | Bateu com o esperado? |
|---|---|---|---|
| C1_abono_simples | | | |
| C2_ferias_com_venda | | | |
| C3_dado_de_saude | | | |
| C4_fora_do_escopo | | | |
| C5_sem_matricula | | | |
| C6_conflito_de_escala | | | |
| C7_autoaprovacao | | | |
| C8_idempotencia | | | |
| C9_divergencia | | | |
| C10_zona_cinzenta | | | |
| C11_diaria_exterior | | | |
| C12_inicio_proibido | | | |

## O grafo

```mermaid
%% cole aqui a saída de: python etapa07_grafo.py --mermaid
```

## Etapa 4 (pronta): o que eu entendi

- Diferença entre a saída online e a offline:
- Por que a espera do retry dobra a cada tentativa:
- Por que o protocolo é um hash dos campos (e não um número sequencial):
- O que aconteceria sem o cache de feriados:

## Observabilidade (C2)

- Onde o tempo foi gasto:
- Tokens totais: ___

## Opcionais (preencha só os que fez)

- 🆕 A: votos e decisão do C9: ___ ; tempo dos 3 extratores em paralelo ___ s, em sequência ___ s
- 🆕 B: saída do `python etapa06_linear.py --governanca`:
- 🆕 C: caminho do C10 com a triagem humana (sim e não):

## Reflexão (até 3 linhas cada)

1. Quem decide o caminho no seu sistema: o LLM, o grafo, as regras ou um humano? Dê um exemplo de cada.
2. Se o guardrail de entrada falhar, o que ainda impede uma autoaprovação?
3. Por que o nó da chefia não pode gravar nada antes do `interrupt()`?
4. Qual dado veio do **MCP**, qual de **API externa** e qual de **tool local**? Por que essa divisão?
5. O que você mudaria para colocar este sistema em produção?
6. (Só se fez) 🆕 A: votar triplica o custo da extração. Em que pedidos vale a pena?
7. (Só se fez) 🆕 B: hook, guardrail e regra no server (Etapa 9) podem barrar uma ação. Qual a diferença de **onde** cada um atua?
8. (Só se fez) 🆕 C: o que muda quando o humano decide a **entrada** em vez da **saída**? Quem é consultado em cada pausa?

## De onde veio cada parte

| Arquivo / trecho | Exemplo das aulas em que me baseei | O que precisei adaptar |
|---|---|---|
| | | |


| Regra | Tema | Quem verifica (função Python / agente / humano) | Por quê | Onde foi implementada (preencha na Etapa 11) |
|---|---|---|---|---|
| N1 | férias | função Python | conta: dias corridos >= 5 e <= saldo | |
| N2 | férias | função Python | conta: dias + vendidos <= saldo, vendidos <= 10 | |
| N3 | férias | função Python | consulta de calendário (feriados e fim de semana) | |
| N4 | prazos | função Python | diferença entre datas (dias corridos ou úteis) | |
| N5 | escala | função Python | contagem de afastados da equipe no período x limite de 30% | |
| N6 | abono | função Python | dia útil e saldo de abonos | |
| N7 | diária | função Python | conta (diárias + meia diária, câmbio); o agente Financeiro só explica | |
| N8 | aprovação | humano | é decisão da chefia; o server só confere se o aprovador é a chefia certa | |
| N9 | saúde | função Python (guardrail) | regex de CID/CPF barra antes de qualquer agente ver o texto; o classificador (agente) cobre o que a regex não pega | |
| N10 | dados | função Python (guardrail de saída) | regex no despacho antes de gravar | |