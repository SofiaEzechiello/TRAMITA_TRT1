"""
Monta uma linha por processo com a data de cada marco e o tempo até ele.

Processos que ainda não atingiram um marco não são descartados: entram como
"censurados" na data da última atualização, que é o que o Kaplan-Meier precisa.
"""

from __future__ import annotations

import pandas as pd

from relogio.config import MARCOS, RESULTADOS


def tabela_por_processo(registros: pd.DataFrame, movimentos: pd.DataFrame) -> pd.DataFrame:
    g1 = (
        registros.loc[registros["grau"] == "G1"]
        .drop_duplicates("numeroProcesso")
        .set_index("numeroProcesso")
    )
    proc = g1[["classe", "orgaoJulgador", "assunto_principal", "dataAjuizamento"]].copy()

    # Data de censura: última atualização conhecida do processo, em qualquer grau.
    # Na falta dela, usa a data da coleta.
    atualizacao = registros.groupby("numeroProcesso")["ultimaAtualizacao"].max()
    coleta = registros.groupby("numeroProcesso")["dataColeta"].max()
    proc["dataCensura"] = atualizacao.reindex(proc.index).fillna(coleta.reindex(proc.index))

    # Movimentos anteriores ao ajuizamento são erro de registro e ficam de fora.
    mov = movimentos.merge(proc[["dataAjuizamento"]], left_on="numeroProcesso", right_index=True)
    mov = mov.loc[mov["dataHora"] >= mov["dataAjuizamento"]]

    for marco, codigos in MARCOS.items():
        primeira = mov.loc[mov["codigo"].isin(codigos)].groupby("numeroProcesso")["dataHora"].min()
        proc[f"data_{marco}"] = primeira.reindex(proc.index)
        proc[f"evento_{marco}"] = proc[f"data_{marco}"].notna()
        fim = proc[f"data_{marco}"].fillna(proc["dataCensura"])
        proc[f"dias_{marco}"] = (fim - proc["dataAjuizamento"]).dt.days

    proc["resultado"] = _resultado_primeira_solucao(mov).reindex(proc.index)
    proc["resultado"] = proc["resultado"].fillna("Sem solução registrada")
    return proc


def _resultado_primeira_solucao(mov: pd.DataFrame) -> pd.Series:
    """Procedência, improcedência, parcial ou acordo, conforme a primeira solução."""
    solucoes = mov.loc[mov["codigo"].isin(RESULTADOS.keys())].sort_values("dataHora")
    primeira = solucoes.drop_duplicates("numeroProcesso").set_index("numeroProcesso")["codigo"]
    return primeira.map(RESULTADOS)
