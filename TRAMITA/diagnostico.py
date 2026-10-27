"""
Diagnóstico da consulta: testa cada filtro separadamente para descobrir
qual deles está zerando o resultado, e mostra o formato real dos campos.

Uso:
  python diagnostico.py
  python diagnostico.py --ano 2022 --assunto "Horas Extras"
"""

from __future__ import annotations

import argparse
import json
import os
import sys



def load_dotenv(override: bool = False) -> None:
    """Load simple KEY=VALUE entries from a local .env file."""
    try:
        with open(".env", encoding="utf-8") as arquivo:
            for linha in arquivo:
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                chave, valor = linha.split("=", 1)
                chave = chave.strip()
                valor = valor.strip().strip('"').strip("'")
                if chave and (override or chave not in os.environ):
                    os.environ[chave] = valor
    except FileNotFoundError:
        pass

from relogio.datajud import ClienteDataJud, ErroDataJud


def testar(cliente: ClienteDataJud, nome: str, consulta: dict) -> None:
    try:
        total = cliente.contar(consulta)
        print(f"  {total:>10,}  {nome}")
    except ErroDataJud as erro:
        print(f"  {'ERRO':>10}  {nome}: {str(erro)[:150]}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tribunal", default="trt1")
    p.add_argument("--ano", type=int, default=2022)
    p.add_argument("--assunto", default="Horas Extras")
    args = p.parse_args()

    load_dotenv(override=True)
    api_key = (os.getenv("DATAJUD_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        sys.exit("Defina DATAJUD_API_KEY no arquivo .env")
    cliente = ClienteDataJud(api_key, args.tribunal)
    ano = args.ano

    # 1. Um registro de exemplo, para ver como os campos vêm de verdade
    print("\n1. Exemplo de registro (formato real dos campos)")
    exemplo = cliente.consultar(
        {"size": 1, "query": {"match_phrase": {"assuntos.nome": args.assunto}}}
    )["hits"]["hits"]
    if exemplo:
        r = exemplo[0]["_source"]
        print(f"  dataAjuizamento = {r.get('dataAjuizamento')!r}")
        print(f"  grau            = {r.get('grau')!r}")
        print(f"  assuntos        = {json.dumps(r.get('assuntos'), ensure_ascii=False)[:200]}")
        print(f"  numeroProcesso  = {r.get('numeroProcesso')!r}")
    else:
        print("  nenhum registro com esse assunto (match_phrase)")

    # 2. Cada filtro isolado
    print("\n2. Contagem com cada filtro isolado")
    testar(cliente, "sem filtro (tribunal inteiro)", {"match_all": {}})
    testar(cliente, f"assunto match_phrase '{args.assunto}'", {"match_phrase": {"assuntos.nome": args.assunto}})
    testar(cliente, f"assunto match '{args.assunto}'", {"match": {"assuntos.nome": args.assunto}})
    testar(cliente, "grau = G1 (match)", {"match": {"grau": "G1"}})
    testar(cliente, "grau = G1 (term)", {"term": {"grau": "G1"}})

    # 3. Variações do filtro de data
    print(f"\n3. Variações do filtro de data ({ano})")
    variacoes = {
        "format yyyyMMddHHmmss": {
            "gte": f"{ano}0101000000", "lte": f"{ano}1231235959", "format": "yyyyMMddHHmmss"
        },
        "data ISO (yyyy-MM-dd)": {"gte": f"{ano}-01-01", "lte": f"{ano}-12-31"},
        "data ISO com hora": {"gte": f"{ano}-01-01T00:00:00", "lte": f"{ano}-12-31T23:59:59"},
        "texto 14 dígitos (sem format)": {"gte": f"{ano}0101000000", "lte": f"{ano}1231235959"},
        "número 14 dígitos": {"gte": int(f"{ano}0101000000"), "lte": int(f"{ano}1231235959")},
    }
    for nome, intervalo in variacoes.items():
        testar(cliente, nome, {"range": {"dataAjuizamento": intervalo}})

    print("\nMande este resultado inteiro de volta.")


if __name__ == "__main__":
    main()