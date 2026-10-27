"""
Relógio Processual — teste de viabilidade

Uso:
  python main.py --ano 2022 --n 3000
  python main.py --ano 2022 --so-processar   # reaproveita a coleta salva
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from relogio.curvas import gerar_curvas
from relogio.dados import carregar, cobertura_marcos, contar_codigos
from relogio.datajud import ErroDataJud, coletar_coorte
from relogio.marcos import tabela_por_processo


def carregar_env() -> None:
    """Carrega variáveis do .env sem depender do pacote python-dotenv."""
    arquivo_env = Path(".env")
    if not arquivo_env.is_file():
        return

    for linha in arquivo_env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if linha.startswith("export "):
            linha = linha[7:].lstrip()
        chave, separador, valor = linha.partition("=")
        if not separador or not chave.strip():
            continue
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "'\"":
            valor = valor[1:-1]
        os.environ[chave.strip()] = valor


def ler_argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Relógio Processual — teste de viabilidade")
    p.add_argument("--tribunal", default="trt1")
    p.add_argument("--ano", type=int, default=2022, help="ano de ajuizamento da coorte")
    p.add_argument("--assunto", default="Horas Extras")
    p.add_argument("--n", type=int, default=3000, help="tamanho da amostra (máx. 10.000)")
    p.add_argument("--semente", type=int, default=42)
    p.add_argument("--so-processar", action="store_true", help="não coleta; usa o arquivo já salvo")
    return p.parse_args()


def titulo(texto: str) -> None:
    print(f"\n{texto}\n{'-' * len(texto)}")


def main() -> None:
    args = ler_argumentos()
    nome = f"{args.tribunal}_{args.assunto.lower().replace(' ', '_')}_{args.ano}"
    arquivo_bruto = Path("data/raw") / f"{nome}.jsonl"
    pasta = Path("resultados") / nome
    pasta.mkdir(parents=True, exist_ok=True)

    # 1. Coleta
    if not args.so_processar:
        # override=True: o .env tem prioridade sobre variáveis já definidas no sistema
        carregar_env()
        api_key = (os.getenv("DATAJUD_API_KEY") or "").strip().strip('"').strip("'")
        if api_key.lower().startswith("apikey "):
            api_key = api_key[7:].strip()
        if not api_key or "cole_aqui" in api_key:
            sys.exit("Defina DATAJUD_API_KEY no arquivo .env (ainda está vazio ou com o texto de exemplo).")
        print(f"Chave lida: {api_key[:6]}...{api_key[-4:]}")
        try:
            coletar_coorte(
                api_key, args.tribunal, args.ano, args.assunto, args.n, args.semente, arquivo_bruto
            )
        except ErroDataJud as erro:
            sys.exit(f"Erro na coleta: {erro}")
    elif not arquivo_bruto.exists():
        sys.exit(f"{arquivo_bruto} não existe. Rode sem --so-processar primeiro.")

    # 2. Viabilidade: quais códigos aparecem?
    registros, movimentos = carregar(arquivo_bruto)
    n_proc = registros.loc[registros["grau"] == "G1", "numeroProcesso"].nunique()
    print(f"\n{n_proc} processos | {len(registros)} registros | {len(movimentos)} movimentos")

    codigos = contar_codigos(movimentos, n_proc)
    codigos.to_csv(pasta / "02_codigos_movimento.csv")
    titulo("Códigos de movimento mais comuns")
    print(codigos.head(30).to_string())

    cobertura = cobertura_marcos(movimentos, n_proc)
    cobertura.to_csv(pasta / "02_cobertura_marcos.csv", index=False)
    titulo("Cobertura dos marcos (resposta do teste de viabilidade)")
    print(cobertura.to_string(index=False))

    # 3. Marcos e curvas
    proc = tabela_por_processo(registros, movimentos)
    proc.to_csv(pasta / "03_processos_marcos.csv")
    titulo("Resultado da primeira solução (%)")
    print(proc["resultado"].value_counts(normalize=True).mul(100).round(1).to_string())

    rotulo = f"{args.tribunal.upper()} — '{args.assunto}', ajuizados em {args.ano} (n={n_proc})"
    resumo = gerar_curvas(proc, pasta / "04_curvas_marcos.png", rotulo)
    resumo.to_csv(pasta / "04_resumo_tempos.csv", index=False)
    titulo("Tempos em meses desde o ajuizamento (Kaplan-Meier)")
    print(resumo.to_string(index=False))

    print(f"\nArquivos em: {pasta.resolve()}")


if __name__ == "__main__":
    main()