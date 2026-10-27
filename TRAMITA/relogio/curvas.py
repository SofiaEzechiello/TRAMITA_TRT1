"""
Curvas de Kaplan-Meier por marco: resumo em tabela e gráfico.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from lifelines import KaplanMeierFitter
from lifelines.exceptions import ApproximationWarning

from relogio.config import MARCOS, ROTULOS_MARCOS

# Aviso inofensivo: a curva KM é uma escada, e consultá-la num ponto é exato o bastante.
warnings.filterwarnings("ignore", category=ApproximationWarning)

DIAS_POR_MES = 30.44
MINIMO_EVENTOS = 10


def ajustar(proc: pd.DataFrame, marco: str) -> KaplanMeierFitter | None:
    """Ajusta o Kaplan-Meier de um marco, com o tempo em meses."""
    dados = proc[[f"dias_{marco}", f"evento_{marco}"]].dropna()
    dados = dados.loc[dados[f"dias_{marco}"] >= 0]
    if dados[f"evento_{marco}"].sum() < MINIMO_EVENTOS:
        return None
    km = KaplanMeierFitter(label=ROTULOS_MARCOS[marco])
    return km.fit(dados[f"dias_{marco}"] / DIAS_POR_MES, dados[f"evento_{marco}"])


def meses_ate(km: KaplanMeierFitter, fracao: float):
    """Meses até que `fracao` dos processos tenha atingido o marco."""
    t = km.percentile(1 - fracao)  # lifelines trabalha com a sobrevivência S(t)
    return round(float(t), 1) if pd.notna(t) and t != float("inf") else "não atingido"


def pct_ate(km: KaplanMeierFitter, meses: float) -> float:
    """% dos processos que já atingiram o marco em `meses`."""
    return round(100 * float(km.cumulative_density_at_times(meses).iloc[0]), 1)


def resumir(km: KaplanMeierFitter, marco: str) -> dict:
    eventos = int(km.event_observed.sum())
    return {
        "marco": ROTULOS_MARCOS[marco],
        "processos": len(km.durations),
        "eventos": eventos,
        "censurados": len(km.durations) - eventos,
        "meses_25pct": meses_ate(km, 0.25),
        "meses_mediana": meses_ate(km, 0.50),
        "meses_75pct": meses_ate(km, 0.75),
        "pct_em_12m": pct_ate(km, 12),
        "pct_em_24m": pct_ate(km, 24),
        "pct_em_36m": pct_ate(km, 36),
    }


def gerar_curvas(proc: pd.DataFrame, arquivo_grafico: Path, titulo: str) -> pd.DataFrame:
    """Ajusta todos os marcos, salva o gráfico e devolve a tabela-resumo."""
    fig, ax = plt.subplots(figsize=(10, 6))
    resumo = []
    for marco in MARCOS:
        km = ajustar(proc, marco)
        if km is None:
            print(f"  {marco}: menos de {MINIMO_EVENTOS} eventos, curva omitida")
            continue
        km.plot_cumulative_density(ax=ax)
        resumo.append(resumir(km, marco))

    ax.set_title(titulo)
    ax.set_xlabel("Meses desde o ajuizamento")
    ax.set_ylabel("Proporção que já atingiu o marco")
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(arquivo_grafico, dpi=150)
    plt.close(fig)
    return pd.DataFrame(resumo)
