"""Cliente LLM: Groq (HTTPS, só stdlib) ou modo demonstração (fallback automático)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from environment import FORMATION_OFFSETS

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"
# Cloudflare costuma bloquear urllib sem User-Agent (HTTP 403). Identificação explícita do cliente.
GROQ_USER_AGENT = "Mozilla/5.0 (compatible; DroneShow/1.0; +python-urllib)"

_VALID_FORMATIONS = frozenset(FORMATION_OFFSETS.keys())

SYSTEM_PROMPT = """Você é o coreógrafo de um show de drones em grade discreta.
Responda APENAS com um objeto JSON válido (sem markdown, sem texto extra) com as chaves:
- "formation": uma de "line", "v", "diamond", "circle", "scatter"
- "center_row": inteiro
- "center_col": inteiro
- "scale": inteiro de 1 a 3
- "note": string curta (opcional) explicando a escolha criativa para este beat

Escolha formações que sejam seguras (evite empilhar drones em obstáculos visíveis no estado)."""


def _load_dotenv() -> None:
    """Carrega .env ao lado deste arquivo; valores do arquivo sobrescrevem o ambiente."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(path):
        return
    try:
        # utf-8-sig remove BOM (comum no Windows) que quebraria a primeira linha
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k:
                        os.environ[k] = v
    except OSError:
        pass


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def _split_err(tag: str | None) -> tuple[str, str]:
    if not tag:
        return "", ""
    if "|" in tag:
        a, _, b = tag.partition("|")
        return a.strip(), b.strip()
    return tag.strip(), ""


def _humanize_groq_error(code: str | None) -> str:
    """Mensagem curta para o operador quando cai no modo demonstração."""
    base, detail = _split_err(code)
    suffix = f" — {detail}" if detail else ""

    if not base or base == "no_key":
        return "sem chave GROQ_API_KEY"
    if base == "http_429":
        return f"limite de taxa ou cota Groq (429){suffix}"
    if base in ("http_503", "http_502", "http_504"):
        return f"Groq temporariamente indisponível{suffix}"
    if base == "http_401" or base == "http_403":
        num = base.replace("http_", "")
        return f"chave Groq inválida ou sem permissão (HTTP {num}){suffix}"
    if base == "http_400":
        return f"requisição rejeitada pela API (modelo ou formato){suffix}"
    if base and base.startswith("http_") and len(base) > 5 and base[5] == "5":
        return f"erro no servidor Groq{suffix}"
    if base == "timeout":
        return "tempo esgotado ao contatar Groq"
    if base == "network":
        return "falha de rede ao contatar Groq"
    if base == "bad_json_response":
        return "resposta HTTP não é JSON válido"
    if base == "bad_response_shape":
        return "resposta Groq em formato inesperado"
    if base == "empty_content":
        return "Groq retornou conteúdo vazio"
    if base == "invalid_llm_json":
        return "JSON do modelo ilegível"
    if base == "invalid_llm_schema":
        return "JSON do modelo fora do esperado (formation/center/scale)"
    return f"fallback para modo demonstração{suffix}"


def groq_complete(user_content: str, timeout: float = 45.0) -> tuple[str | None, str | None]:
    """
    Chama a API Groq. Retorna (texto_do_assistente, código_erro).
    Se ok, código_erro é None. Qualquer falha deixa texto None e preenche o código.
    """
    _load_dotenv()
    key = os.environ.get("GROQ_API_KEY", "").strip().strip('"').strip("'")
    if not key:
        return None, "no_key"

    payload = {
        "model": os.environ.get("GROQ_MODEL", DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.4,
        "max_tokens": 256,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        GROQ_URL,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": os.environ.get("GROQ_USER_AGENT", GROQ_USER_AGENT),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_bytes = resp.read()
            body = json.loads(raw_bytes.decode("utf-8"))
    except urllib.error.HTTPError as e:
        code = int(getattr(e, "code", 0) or 0)
        detail = ""
        try:
            raw_err = e.read().decode("utf-8", errors="replace")
            ej = json.loads(raw_err)
            err_obj = ej.get("error")
            if isinstance(err_obj, dict):
                detail = str(err_obj.get("message", "")).strip()
            elif isinstance(err_obj, str):
                detail = err_obj.strip()
        except (OSError, json.JSONDecodeError, TypeError, AttributeError, ValueError):
            pass
        if detail and len(detail) > 220:
            detail = detail[:217] + "..."
        tag = f"http_{code}" + (f"|{detail}" if detail else "")
        return None, tag
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        r = str(reason).lower()
        if isinstance(reason, TimeoutError) or "timed out" in r:
            return None, "timeout"
        return None, "network"
    except TimeoutError:
        return None, "timeout"
    except json.JSONDecodeError:
        return None, "bad_json_response"
    except OSError:
        return None, "network"

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None, "bad_response_shape"

    if content is None or not str(content).strip():
        return None, "empty_content"

    return str(content).strip(), None


def _intish(v: object, default: int) -> int:
    if isinstance(v, bool):
        return default
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v == int(v):
        return int(v)
    if isinstance(v, str) and v.strip().lstrip("-").isdigit():
        return int(v.strip())
    return default


def _validate_choreography(obj: dict) -> bool:
    """Garante JSON utilizável: formation válida; scale, se vier, entre 1 e 3. Centro é limitado depois no ambiente."""
    if not isinstance(obj, dict):
        return False
    name = str(obj.get("formation", "")).lower().strip()
    if name not in _VALID_FORMATIONS:
        return False
    if "scale" in obj:
        sc = _intish(obj.get("scale"), 0)
        if not (1 <= sc <= 3):
            return False
    return True


def stub_choreography(perception: str, beat: int, *, api_issue: str | None = None) -> str:
    """Coreógrafo heurístico: mesmo formato JSON do LLM; sempre disponível."""
    formations = ["line", "v", "diamond", "circle", "scatter"]
    idx = (beat // 6) % len(formations)
    name = formations[idx]
    cr = 3 + (beat // 4) % (10 - 6)
    cc = 3 + (beat // 5) % (14 - 8)
    scale = 1 + (beat % 3)
    hint = _humanize_groq_error(api_issue) if api_issue else "sem necessidade de API"
    note = (
        f"Modo demonstração ativo ({hint}). "
        f"Formação alterna por beat. Estado: {perception.splitlines()[0]}."
    )
    return json.dumps(
        {
            "formation": name,
            "center_row": cr,
            "center_col": cc,
            "scale": scale,
            "note": note,
        },
        ensure_ascii=False,
    )


def choreographer_json(perception: str, beat: int) -> tuple[dict, str, str | None]:
    """
    Retorna (dict parseado, fonte, motivo_stub).

    fonte: 'groq' ou 'stub'.
    motivo_stub: None se veio do Groq; senão texto humano explicando o fallback.
    """
    user = (
        "Estado do simulador:\n"
        f"{perception}\n"
        "Defina a próxima formação para os 4 drones."
    )
    raw, err = groq_complete(user)
    stub_reason: str | None = None

    if raw is None:
        stub_reason = _humanize_groq_error(err)
        raw = stub_choreography(perception, beat, api_issue=err)
        try:
            obj = json.loads(_strip_json_fence(raw))
        except json.JSONDecodeError:
            raw = stub_choreography(perception, beat, api_issue="invalid_llm_json")
            obj = json.loads(_strip_json_fence(raw))
        return obj, "stub", stub_reason

    try:
        obj = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError:
        stub_reason = _humanize_groq_error("invalid_llm_json")
        obj = json.loads(stub_choreography(perception, beat, api_issue="invalid_llm_json"))
        return obj, "stub", stub_reason

    if not _validate_choreography(obj):
        stub_reason = _humanize_groq_error("invalid_llm_schema")
        obj = json.loads(stub_choreography(perception, beat, api_issue="invalid_llm_schema"))
        return obj, "stub", stub_reason

    return obj, "groq", None
