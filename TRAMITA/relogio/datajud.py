"""
Comunicação com a API Pública do DataJud.

Coleta uma amostra aleatória de uma coorte de ajuizamento (1º grau) e depois
os registros dos outros graus desses mesmos processos. Salva tudo em JSONL.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from relogio.config import URL_BASE

PAUSA_ENTRE_CHAMADAS = 0.5  # segundos, para não sobrecarregar a API
LIMITE_AMOSTRA = 10_000  # o Elasticsearch limita from + size a 10.000


class ErroDataJud(RuntimeError):
    pass


class ClienteDataJud:
    def __init__(self, api_key: str, tribunal: str):
        self.url = URL_BASE.format(tribunal=tribunal)
        self.headers = {
            "Authorization": f"APIKey {api_key}",
            "Content-Type": "application/json",
        }

    def consultar(self, corpo: dict, tentativas: int = 5) -> dict:
        """POST com novas tentativas para erros temporários (429, 5xx, rede)."""
        for tentativa in range(1, tentativas + 1):
            espera = 2**tentativa
            requisicao = Request(
                self.url,
                data=json.dumps(corpo).encode("utf-8"),
                headers=self.headers,
                method="POST",
            )
            try:
                with urlopen(requisicao, timeout=60) as resposta:
                    status = resposta.status
                    texto = resposta.read().decode("utf-8")
            except HTTPError as erro:
                status = erro.code
                texto = erro.read().decode("utf-8", errors="replace")
            except (URLError, TimeoutError, OSError) as erro:
                print(f"  falha de rede ({erro}); nova tentativa em {espera}s")
                time.sleep(espera)
                continue

            if status == 200:
                return json.loads(texto)
            if status in (429, 500, 502, 503, 504):
                print(f"  HTTP {status}; nova tentativa em {espera}s")
                time.sleep(espera)
                continue
            # 400, 401, 403...: erro na consulta ou na chave; repetir não resolve
            raise ErroDataJud(f"HTTP {status}: {texto[:500]}")
        raise ErroDataJud("Número máximo de tentativas atingido.")

    def contar(self, consulta: dict) -> int:
        corpo = {"size": 0, "track_total_hits": True, "query": consulta}
        return self.consultar(corpo)["hits"]["total"]["value"]

    def amostrar(self, consulta: dict, n: int, semente: int) -> list[dict]:
        """Amostra aleatória reprodutível: a mesma semente devolve a mesma amostra."""
        n = min(n, LIMITE_AMOSTRA)

        def com_aleatoriedade(random_score: dict) -> dict:
            return {
                "function_score": {
                    "query": consulta,
                    "random_score": random_score,
                    "boost_mode": "replace",
                }
            }

        # Tenta a forma recomendada; se a API recusar, usa a forma simples.
        aleatoria = com_aleatoriedade({"seed": semente, "field": "_seq_no"})
        try:
            self.consultar({"size": 1, "query": aleatoria})
        except ErroDataJud:
            print("  random_score com _seq_no recusado; usando a forma simples")
            aleatoria = com_aleatoriedade({"seed": semente})

        registros, pagina = [], 500
        for inicio in range(0, n, pagina):
            corpo = {"from": inicio, "size": min(pagina, n - inicio), "query": aleatoria}
            hits = self.consultar(corpo)["hits"]["hits"]
            if not hits:
                break
            registros.extend(h["_source"] for h in hits)
            print(f"  amostra: {len(registros)}/{n}")
            time.sleep(PAUSA_ENTRE_CHAMADAS)
        return registros

    def outros_graus(self, numeros: list[str], grau_excluido: str = "G1") -> list[dict]:
        """Registros de G2, TST etc. dos mesmos processos (o trânsito costuma estar lá)."""
        registros, lote = [], 200
        for i in range(0, len(numeros), lote):
            corpo = {
                "size": 1000,
                "query": {
                    "bool": {
                        "must": [{"terms": {"numeroProcesso": numeros[i : i + lote]}}],
                        "must_not": [{"match": {"grau": grau_excluido}}],
                    }
                },
            }
            hits = self.consultar(corpo)["hits"]["hits"]
            registros.extend(h["_source"] for h in hits)
            print(f"  outros graus: lote {i // lote + 1} ({len(registros)} registros)")
            time.sleep(PAUSA_ENTRE_CHAMADAS)
        return registros


def consulta_coorte(ano: int, assunto: str, grau: str = "G1") -> dict:
    """Processos do assunto, ajuizados no ano, em um grau."""
    return {
        "bool": {
            "must": [
                {"match_phrase": {"assuntos.nome": assunto}},
                {"match": {"grau": grau}},
                {
                    # No TRT1 a data é gravada como 14 dígitos (AAAAMMDDHHMMSS),
                    # não como campo de data. Confirmado com diagnostico.py.
                    "range": {
                        "dataAjuizamento": {
                            "gte": f"{ano}0101000000",
                            "lte": f"{ano}1231235959",
                        }
                    }
                },
            ]
        }
    }


def coletar_coorte(
    api_key: str,
    tribunal: str,
    ano: int,
    assunto: str,
    n: int,
    semente: int,
    destino: Path,
) -> None:
    """Coleta a coorte completa (G1 + outros graus) e salva em JSONL."""
    cliente = ClienteDataJud(api_key, tribunal)
    consulta = consulta_coorte(ano, assunto)

    total = cliente.contar(consulta)
    print(f"Coorte: '{assunto}', ajuizados em {ano}, {tribunal.upper()} G1 -> {total} processos")
    if total == 0:
        raise ErroDataJud(
            "Nenhum processo encontrado. Verifique o nome do assunto e se o filtro "
            "de dataAjuizamento funciona neste tribunal (ver README)."
        )

    registros_g1 = cliente.amostrar(consulta, min(n, total), semente)
    numeros = sorted({r["numeroProcesso"] for r in registros_g1})
    registros_outros = cliente.outros_graus(numeros)

    data_coleta = datetime.now().isoformat(timespec="seconds")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as f:
        for r in registros_g1 + registros_outros:
            r["_data_coleta"] = data_coleta
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Salvo: {destino} ({len(registros_g1)} G1 + {len(registros_outros)} outros graus)")