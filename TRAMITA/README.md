# Relógio Processual

Mede quanto tempo os processos trabalhistas levam para atingir cada marco (solução, trânsito em julgado, arquivamento definitivo), usando **apenas dados públicos** da API do DataJud/CNJ. Nenhum dado de cliente ou do escritório entra aqui.

Esta primeira versão é um **teste de viabilidade**: ela responde se os códigos de movimento do TRT1 são registrados bem o suficiente para o projeto valer a pena.

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # e cole a chave pública do DataJud

python main.py --ano 2022 --n 3000
```

Opções: `--tribunal trt1`, `--ano 2022`, `--assunto "Horas Extras"`, `--n 3000` (máx. 10.000), `--semente 42`.
Para reprocessar sem baixar de novo: `--so-processar`.

## Estrutura

```text
relogio-processual/
├── main.py              # ponto de entrada: roda as etapas em ordem
└── relogio/
    ├── config.py        # marcos e códigos TPU (o único arquivo que você deve precisar ajustar)
    ├── datajud.py       # conversa com a API: consulta, amostra aleatória, outros graus
    ├── dados.py         # lê a coleta e conta os códigos de movimento
    ├── marcos.py        # uma linha por processo, com a data de cada marco
    └── curvas.py        # Kaplan-Meier, tabela-resumo e gráfico
```

## O que ele faz

1. **Coleta uma coorte**: amostra aleatória (semente fixa, reprodutível) dos processos de 1º grau com o assunto escolhido, ajuizados no ano escolhido. Depois busca os registros dos outros graus dos mesmos processos, onde o trânsito em julgado costuma aparecer.
2. **Conta os códigos de movimento** (TPU/CNJ) e mostra a cobertura de cada marco.
3. **Calcula as curvas de Kaplan-Meier** de cada marco, tratando como censurados os processos que ainda não chegaram lá.

## Saídas (`resultados/<tribunal>_<assunto>_<ano>/`)

| Arquivo | Conteúdo |
|---|---|
| `02_codigos_movimento.csv` | Todos os códigos encontrados, com nome e % de processos em que aparecem |
| `02_cobertura_marcos.csv` | **Resposta do teste**: % de processos com cada marco registrado |
| `03_processos_marcos.csv` | Uma linha por processo: datas dos marcos, dias até cada um, resultado |
| `04_resumo_tempos.csv` | Mediana, quartis e % que atingiu o marco em 12/24/36 meses |
| `04_curvas_marcos.png` | Curvas acumuladas por marco |

## Como ler o teste de viabilidade

- **Cobertura alta** (ex.: solução em 80%+ dos processos de 2022): os códigos estão sendo registrados e o projeto anda.
- **Cobertura baixa**: abra `02_codigos_movimento.csv` e procure, pelo nome, qual código o TRT1 usa de fato para sentença, acordo, trânsito e arquivamento. Ajuste o dicionário `MARCOS` em `relogio/config.py` e rode com `--so-processar`.

Os códigos em `MARCOS` (`relogio/config.py`) (219, 220, 221, 466, 848, 246, 22) são o ponto de partida e **devem ser conferidos** com essa contagem.

## Cuidados

- **Ponto mais frágil:** o filtro por `dataAjuizamento` usa `format: yyyyMMddHHmmss`. Se a contagem inicial vier zerada, o campo pode estar indexado de outro jeito neste tribunal. Teste a consulta manualmente.
- **Censura**: quem não atingiu o marco é censurado na última atualização do processo no DataJud. O DataJud tem atraso, então tempos muito recentes ficam levemente subestimados.
- **Arquivamento definitivo** é só uma aproximação de "fim da execução". Pode haver desarquivamentos depois.
- **Acordo × sentença**: o marco "solução" junta os dois. Medir só "tempo até a sentença" tratando acordos como censura seria errado, porque o acordo impede a sentença (é um *risco competitivo*). O caminho certo é a incidência cumulativa de Aalen-Johansen (`lifelines.AalenJohansenFitter`).
- Resultados são descritivos e não constituem previsão sobre um processo específico.

## Próximos passos possíveis

- Comparar coortes (2019 × 2022) e assuntos.
- Curvas por vara (`orgaoJulgador`) e modelo de Cox para controlar por classe e assunto.
- Riscos competitivos (sentença × acordo).
- Consulta avulsa: colar um número CNJ e ver em que percentil da curva ele está, sem armazenar nada.
