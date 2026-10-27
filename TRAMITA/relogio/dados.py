"""
Leitura do JSONL coletado e diagnóstico dos códigos de movimento.

A contagem de códigos é o teste de viabilidade: mostra se os marcos
estão sendo registrados pelo tribunal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from relogio.config import MARCOS, ROTULOS_MARCOS


def ler_data(valor) -> pd.Timestamp:
    """Aceita '20220315103000', 20220315103000 e '2022-03-15T10:30:00.000Z'."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return pd.NaT
    texto = str(valor).strip()
    if texto.isdigit() and len(texto) == 14:
        return pd.to_datetime(texto, format="%Y%m%d%H%M%S", errors="coerce")
    data = pd.to_datetime(texto, errors="coerce", utc=True)
    return pd.NaT if pd.isna(data) else data.tz_localize(None)


def carregar(arquivo: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê o JSONL e devolve duas tabelas: (registros, movimentos)."""
    registros, movimentos = [], []
    with arquivo.open(encoding="utf-8") as f:
        for linha in f:
            r = json.loads(linha)
            numero = str(r.get("numeroProcesso", "")).zfill(20)
            grau = r.get("grau")
            assuntos = r.get("assuntos") or [{}]
            registros.append(
                {
                    "numeroProcesso": numero,
                    "grau": grau,
                    "classe": (r.get("classe") or {}).get("nome"),
                    "orgaoJulgador": (r.get("orgaoJulgador") or {}).get("nome"),
                    "assunto_principal": (assuntos[0] or {}).get("nome"),
                    "dataAjuizamento": ler_data(r.get("dataAjuizamento")),
                    "ultimaAtualizacao": ler_data(r.get("dataHoraUltimaAtualizacao")),
                    "dataColeta": ler_data(r.get("_data_coleta")),
                }
            )
            movimentos.extend(
                {
                    "numeroProcesso": numero,
                    "grau": grau,
                    "codigo": m.get("codigo"),
                    "nome": m.get("nome"),
                    "dataHora": ler_data(m.get("dataHora")),
                }
                for m in r.get("movimentos") or []
            )

    registros = pd.DataFrame(registros)
    movimentos = pd.DataFrame(movimentos)
    movimentos["codigo"] = pd.to_numeric(movimentos["codigo"], errors="coerce").astype("Int64")
    return registros, movimentos


def contar_codigos(movimentos: pd.DataFrame, n_processos: int) -> pd.DataFrame:
    """Todos os códigos encontrados, com nome e % de processos em que aparecem."""

    def nome_mais_comum(nomes: pd.Series):
        moda = nomes.mode()
        return moda.iat[0] if not moda.empty else None

    tabela = (
        movimentos.groupby("codigo")
        .agg(
            nome=("nome", nome_mais_comum),
            ocorrencias=("nome", "size"),
            processos=("numeroProcesso", "nunique"),
        )
        .assign(pct_processos=lambda t: (100 * t["processos"] / n_processos).round(1))
        .sort_values("processos", ascending=False)
    )
    tabela["usado_em_marco"] = tabela.index.isin(set().union(*MARCOS.values()))
    return tabela


def cobertura_marcos(movimentos: pd.DataFrame, n_processos: int) -> pd.DataFrame:
    """% de processos em que cada marco aparece. É a resposta do teste."""
    linhas = []
    for marco, codigos in MARCOS.items():
        com_marco = movimentos.loc[movimentos["codigo"].isin(codigos), "numeroProcesso"].nunique()
        linhas.append(
            {
                "marco": ROTULOS_MARCOS[marco],
                "codigos": ", ".join(map(str, sorted(codigos))),
                "processos_com_marco": com_marco,
                "pct_processos": round(100 * com_marco / n_processos, 1),
            }
        )
    return pd.DataFrame(linhas)
