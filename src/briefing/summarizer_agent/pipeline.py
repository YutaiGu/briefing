import tiktoken
from pathlib import Path
from multiprocessing import Pool, cpu_count

from briefing.config import model_para, api_model, OUTPUT_DIR, resolve_model
from briefing.config import SUMMARIZER_LIMIT, POOL_NUM
from briefing.db import get_unsummarized, update_entries, entry_to_payload, payload_to_entry
from briefing.llm import completion, completion_cost, model_limits

# per-process LLM usage accumulator, reset per video in one_summarizer
_usage = {"tokens": 0, "cost": 0.0}

def one_summarizer(payload):
    try:
        _usage["tokens"] = 0
        _usage["cost"] = 0.0
        payload = Text_Processing(payload)
        payload['tokens'] = (payload.get('tokens') or 0) + _usage["tokens"]
        payload['cost'] = round((payload.get('cost') or 0.0) + _usage["cost"], 6)
        payload['summarized'] = 1  # Mark only after final success
        return payload
    except Exception:
        return None

def summarizer(session) -> None:
    # fold any new user feedback into the per-domain style preferences first
    try:
        from briefing.summarizer_agent import evolve
        evolve.evolve(session, api_model["evolve_model"])
    except Exception as e:
        print(f"[evolve pass skipped: {e}]")

    todo = get_unsummarized(session, SUMMARIZER_LIMIT)
    if not todo:
        return

    workers = min(cpu_count(), POOL_NUM)
    with Pool(processes=workers) as pool:
        payloads = [entry_to_payload(v) for v in todo]
        for updated in pool.imap(one_summarizer, payloads):
            if updated is None:
                continue
            update_entries(session, [payload_to_entry(updated)])

def request_gpt(input, system_content, model, check=None, retries=2):
    """One LLM call via the router; accumulates tokens/cost into _usage.
    With `check(text) -> (ok, error)`, retries up to `retries` times on rejection."""
    if not model:
        raise ValueError("model is required")

    name, key, base = resolve_model(model)
    note = ""
    response_json = None
    for _ in range(retries + 1):
        try:
            response_json = completion(
                model=name,
                messages=[
                    {"role": "system", "content": system_content + note},
                    {"role": "user", "content": input},
                ],
                api_key=key,
                api_base=base,
                temperature=model_para["temperature"],
                presence_penalty=model_para["presence_penalty"],
                max_tokens=model_limits(name)["max_output"],
            )
        except Exception as e:
            print(f"[gpt] request failed: {type(e).__name__}")
            raise

        if response_json.get("error") is not None:
            print("request_gpt error:", response_json)

        try:
            _usage["tokens"] += int(response_json["usage"]["total_tokens"])
            _usage["cost"] += completion_cost(response_json)
        except Exception:
            pass

        if check is None:
            return response_json
        ok, err = check(response_json["choices"][0]["message"]["content"])
        if ok:
            return response_json
        note = f"\n\nYour previous answer was rejected: {err}. Output again, follow the format exactly. Output only the result."
        print(f"[LLM Retry] {err}")

    return response_json

def summarizer_request_gpt(input, which_system, model):
    '''
    Args:
        input (str)
        which_system (str): prompt
        model (str)

    Returns:
        response_txt (str)
        history (list)
    '''
    if not model:
        raise ValueError("model is required")
    if not which_system:
        raise ValueError("which_system is required")
    if which_system not in model_para["system_content"]:
        raise ValueError(f"unknown system prompt: {which_system}")

    system_content = model_para["system_content"][which_system] + model_para["system_content"]['additional']

    response_json = request_gpt(input, system_content, model)
    response_txt =response_json['choices'][0]['message']['content']
    history = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": input},
        {"role": "assistant", "content": response_txt}
    ]

    return response_txt, history

def _subjective(input_text, stage, model):
    """Generate a subjective stage, injecting that stage's learned preferences."""
    from briefing.summarizer_agent import evolve, validators
    system = model_para["system_content"][stage] + model_para["system_content"]["additional"]
    notes = evolve.load_notes(stage)
    if notes:
        system += f"\n\n=== Learned style preferences (follow these) ===\n{notes}"
    check = {"brief": validators.check_brief, "short": validators.check_short}.get(stage)
    resp = request_gpt(input_text, system, model, check=check)
    return resp["choices"][0]["message"]["content"]

def _split_headline(raw):
    """Pull (headline, body) from the brief output, tolerant of format drift.

    The model is asked for 'HEADLINE: x\\n---\\nbody' but sometimes writes the
    headline as '# x' or drops the markers. Recover when a '---' separator or a
    HEADLINE: label is present; otherwise treat the whole text as the body.
    """
    text = (raw or "").strip()
    if not text:
        return "", ""

    head, sep, rest = text.partition("---")
    if sep and rest.strip():
        line = next((l for l in head.splitlines() if l.strip()), "")
        body = rest.strip()
    else:
        first = text.splitlines()[0]
        if not first.strip().lstrip("#*> ").upper().startswith("HEADLINE:"):
            return "", text  # no headline structure — keep the body whole
        line = first
        body = "\n".join(text.splitlines()[1:]).strip()

    line = line.strip().lstrip("#*> ").strip()
    if line.upper().startswith("HEADLINE:"):
        line = line.split(":", 1)[1]
    return line.strip(" *`"), body

def Text_Processing(payload):
    file_name = Path(payload['file_path']).stem
    if not file_name:
        raise ValueError("file_name is required")
    
    WORK_DIR = OUTPUT_DIR / file_name
    if not WORK_DIR.exists():
        raise ValueError("{file_name} Not Found.")
    paths = {
        "whisper": WORK_DIR / "whisper.txt",
        "history": WORK_DIR / "history.txt",
        "outline": WORK_DIR / "outline.txt",
        "brief": WORK_DIR / "brief.txt",
        "headline": WORK_DIR / "headline.txt",
        "short": WORK_DIR / "short.txt",
    }
    outline_model = api_model["outline_model"]
    brief_model = api_model["brief_model"]
    model_name, _, _ = resolve_model(outline_model)  # bare name for tiktoken/limits (chunking on outline stage)
    if not paths["whisper"].exists():
        raise FileNotFoundError(f"{paths['whisper']} Not Found.")
    with open(paths["whisper"], 'r', encoding='utf-8') as file:
        whisper_text = file.read()

    # split text by tokens
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    outline_content = model_para["system_content"]["outline"] + model_para["system_content"]["additional"]
    outline_content_tokens = len(encoding.encode(outline_content))
    max_input_tokens = model_limits(model_name)["max_input"]
    token_budget = max_input_tokens - outline_content_tokens - 64  # Leave margin
    if token_budget <= 0:
        raise ValueError("token_budget is non-positive.")

    def chunk_by_tokens(text, budget):
        tokens = encoding.encode(text)
        return [encoding.decode(tokens[i:i + budget]) for i in range(0, len(tokens), budget)] or [""]

    chunks = chunk_by_tokens(whisper_text, token_budget)
    total_parts = len(chunks)

    ## step2: Outline Trace
    if paths["outline"].exists():
        with open(paths["outline"], "r", encoding="utf-8") as f:
            outline_text = f.read()
    else:
        outlines = []
        for idx, chunk in enumerate(chunks):
            if total_parts == 1:
                temp_prompt = chunk
                tag = ""
            else:
                tag = f"[Part {idx + 1}/{total_parts}]"
                temp_prompt = tag + " segmented input; keep context.\n" + chunk
            resp, _ = summarizer_request_gpt(
                temp_prompt,
                "outline",
                outline_model,
            )
            outlines.append((tag + "\n" if tag else "") + resp)

        outline_text = "\n\n".join(outlines)
        paths["outline"].write_text(outline_text, encoding="utf-8")

    ## brief (+ headline) — subjective
    if paths["brief"].exists() and paths["headline"].exists():
        brief_text = paths["brief"].read_text(encoding="utf-8")
        headline_text = paths["headline"].read_text(encoding="utf-8")
    else:
        raw = _subjective(outline_text, "brief", brief_model)
        headline_text, brief_text = _split_headline(raw)
        paths["headline"].write_text(headline_text, encoding="utf-8")
        paths["brief"].write_text(brief_text, encoding="utf-8")

    ## short — subjective
    if paths["short"].exists():
        short_text = paths["short"].read_text(encoding="utf-8")
    else:
        short_text = _subjective(brief_text, "short", brief_model)
        paths["short"].write_text(short_text, encoding="utf-8")

    return payload