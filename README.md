# Show de drones — simulação multiagente

## Para o professor (avaliação rápida)

| | |
|--|--|
| **Disciplina** | Agentes Inteligentes — Pós-graduação IA / iCEV |
| **Repositório** | https://github.com/robsonpaulista/posicevagentes (público) |
| **Requisito** | Python **3.10+** apenas — **sem** `pip install` obrigatório |
| **Rodar** | Na raiz: `python main.py` (texto) ou `python main.py --visual` (Tkinter). *Linux:* se faltar janela, instalar pacote `python3-tk` do sistema. |
| **LLM (Groq)** | Opcional: copiar `.env.example` → `.env` e preencher `GROQ_API_KEY`. Sem chave ou com erro de API → **modo demonstração** (mesmo fluxo, sem rede). |
| **O que ler** | `main.py` (entrada), `simulation.py` (passo), `environment.py` (ambiente), `llm_client.py` (Groq/stub), `agents/` (coreógrafo + piloto), `gui.py` (visual) |

Projeto para a disciplina **Agentes Inteligentes** (Pós IA / iCEV): ambiente em **Python puro** (sem dependências `pip`), com dois agentes — coreógrafo (**LLM** ou modo demonstração) e piloto **baseado em modelo** (BFS na grade).

## Requisitos

- **Python 3.10+** (stdlib apenas).

## Como executar

No diretório deste projeto:

```bash
python main.py
```

**Modo visual (Tkinter, sem `pip`):** abre uma janela com a grade, alvos da formação (anel amarelo) e os quatro drones em cores. Útil para demonstração e relatório.

```bash
python main.py --visual --steps 80
python main.py --visual --cell 40 --pause-ms 350 --phase-ms 250
```

O coreógrafo **só redefine a formação** quando os quatro drones **acabam de alcançar** os alvos da formação atual (detecção de transição, não a cada beat parado). Opcional: `--stuck-replan-after N` ou `--replan-every N` força um novo coreógrafo após N beats **sem** completar a formação.

No Linux, se faltar Tkinter: `sudo apt install python3-tk` (Debian/Ubuntu).

Opções úteis (terminal):

```bash
python main.py --steps 50
python main.py --steps 50 --quiet
python main.py --steps 100 --stuck-replan-after 40
```

## Modo LLM (Groq, gratuito)

1. Crie uma chave em [Groq Console](https://console.groq.com/) (tier gratuito).
2. Defina a variável de ambiente **`GROQ_API_KEY`**, ou copie `.env.example` para `.env` e preencha:

```env
GROQ_API_KEY=sua_chave_aqui
```

Opcional: `GROQ_MODEL=llama-3.1-8b-instant` (padrão).

**Windows:** se você já tinha `GROQ_API_KEY` nas variáveis de ambiente do sistema/usuário (mesmo vazia ou antiga), o programa **passa a priorizar o `.env`** na pasta do projeto. Se ainda der HTTP 401, confira no PowerShell `echo $env:GROQ_API_KEY` e remova a variável global se estiver errada.

**HTTP 403 com chave válida:** o `urllib` do Python não envia `User-Agent` por padrão; o Cloudflare da Groq pode bloquear. Este projeto já envia um `User-Agent` explícito. Se ainda falhar, toute outra rede/VPN ou política da conta.

**Sem chave, limite de taxa (429), timeout, erro de rede ou JSON inválido do modelo:** o simulador **continua** usando o **modo demonstração** (stub), com o mesmo formato de formação — o terminal indica o motivo do fallback quando aplicável.

## Estrutura do código

| Arquivo / pasta | Função |
|-----------------|--------|
| `main.py` | Loop da simulação e CLI (`--visual` para janela gráfica) |
| `gui.py` | Janela Tkinter: grade, alvos e drones animados |
| `simulation.py` | `plan_step` / `apply_planned_moves` (compartilhado entre CLI e GUI) |
| `environment.py` | Grade, obstáculos, drones, formações; alvos da formação são **reposicionados** para a célula livre mais próxima se caíssem em obstáculo (evita anéis de alvo sobre `#`) |
| `llm_client.py` | Chamada HTTPS à API Groq (`urllib`) + carregamento opcional de `.env` + stub |
| `agents/choreographer.py` | Agente coreógrafo (percepção → JSON → formação) |
| `agents/pilot.py` | Agente piloto (modelo do mundo + BFS + anti-colisão por ordem) |

## Agentes (resumo para o relatório)

1. **Coreógrafo:** arquitetura **deliberativa** com **LLM** (prompt + JSON); traduz estado textual em `formation`, `center_row`, `center_col`, `scale`.
2. **Piloto:** **baseado em modelo** (Russell & Norvig): mantém representação da grade, obstáculos e posições alvo; calcula movimento com **BFS** e regras de precedência entre drones.

## PEAS (rascunho)

- **Performance:** formar padrões sem colisão nem saída da grade; minimizar tempo para aproximar alvos; obedecer decisões criativas do coreógrafo.
- **Environment:** grade discreta 10×14, obstáculos estáticos, quatro drones, “compasso” discreto (beat).
- **Actuators:** movimento `N/S/E/W` ou `HOLD` por drone; coreógrafo altera parâmetros globais de formação.
- **Sensors:** estado completo exposto ao coreógrafo (simulação **totalmente observável** para ele); piloto usa o mesmo modelo no código.

## Dimensões do ambiente (Russell & Norvig)

| Dimensão | Classificação sugerida |
|----------|-------------------------|
| Observável | Totalmente observável (para os agentes, no código) |
| Agentes | Multiagente (4 drones + coreógrafo + piloto como decisores) |
| Determinístico | Determinístico (movimento e stub); estocástico se o LLM variar |
| Episódico / Sequencial | Sequencial (formação e caminho dependem do histórico) |
| Estático / Dinâmico | Dinâmico (posições mudam a cada beat) |
| Discreto / Contínuo | Discreto (grade e ações finitas) |

Ajuste a redação no relatório conforme a modelagem exata que o grupo adotar.

## Licença

Uso acadêmico pelo grupo do trabalho.
