"""
Configurações: endereço da API e os marcos processuais.

Os marcos usam códigos da Tabela Processual Unificada (TPU/CNJ).
ATENÇÃO: confira estes códigos com o arquivo 02_codigos_movimento.csv
antes de confiar nas curvas. Os tribunais registram movimentos de forma
inconsistente. Se algo não bater, ajuste aqui e rode com --so-processar.
"""

URL_BASE = "https://api-publica.datajud.cnj.jus.br/api_publica_{tribunal}/_search"

# Cada marco = conjunto de códigos de movimento que indicam que ele aconteceu.
MARCOS = {
    # Primeira solução: sentença de mérito OU acordo homologado.
    # Na Justiça do Trabalho o acordo é muito comum; ignorá-lo distorce o tempo.
    "solucao": {219, 220, 221, 466},
    "transito_julgado": {848},
    # Aproximação do "fim real" (execução encerrada / arquivado de vez).
    "arquivamento_definitivo": {246, 22},
}

ROTULOS_MARCOS = {
    "solucao": "Solução (sentença ou acordo)",
    "transito_julgado": "Trânsito em julgado",
    "arquivamento_definitivo": "Arquivamento / baixa definitiva",
}

# Como classificar o resultado da primeira solução.
RESULTADOS = {
    219: "Procedência",
    220: "Improcedência",
    221: "Procedência em parte",
    466: "Acordo homologado",
}
