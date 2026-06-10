from datetime import datetime
import requests
import tiktoken
from pathlib import Path
from multiprocessing import Pool, cpu_count

from briefing.config import api_info, model_info, model_para, api_model, OUTPUT_DIR
from briefing.config import SUMMARIZER_LIMIT, POOL_NUM
from briefing.db import get_unsummarized, update_entries, entry_to_payload, payload_to_entry

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
        evolve.evolve(session, api_model["summarize_model"])
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

def request_gpt(input, system_content, model):
    '''
    request chatgpt

    response_json = {
        'id': 'chatcmpl-A46En6R7booB25ShmyYf4VT4EEoSG',
        'object': 'chat.completion',
        'created': 1725540653,
        'model': 'gpt-4o-mini-2024-07-18',
        'choices': [{
            'index': 0,
            'message': {
                'role': 'assistant',
                'content': '...'},
                'logprobs': None,
                'finish_reason': 'stop'}],
        'usage': {
            'prompt_tokens': 1324,
            'completion_tokens': 348,
            'total_tokens': 1672},
        'system_fingerprint': 'fp_f33667828e'}
    '''
    if not model:
        raise ValueError("model is required")

    api_key = api_info["api_key"]
    try:
        encoding = tiktoken.encoding_for_model(model_info[model]["model"])
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    payload = {
        "model": model_info[model]["model"],
        "messages": [
            {"role": "system",
             "content": system_content},
            {"role": "user",
             "content": input},
        ],
        "temperature": model_para["temperature"],
        "presence_penalty": model_para["presence_penalty"],
        "max_tokens": model_info[model]["max_output"],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            api_info["url_redirect"], 
            json = payload, 
            headers = headers,
            timeout=(20, 120),  # Connection timeout: 10s, Read timeout 120s
        )
    except Exception as e:
        print(f"[gpt] request failed: {type(e).__name__}")
        raise

    response_json = response.json()
    if response_json.get("error") is not None:
        print("request_gpt error:", response_json)
    cost = (model_info[model]["input_price"]*response_json['usage']['prompt_tokens']+model_info[model]["output_price"]*response_json['usage']['completion_tokens'])/1000

    try:
        _usage["tokens"] += int(response_json['usage']['total_tokens'])
        _usage["cost"] += cost
    except Exception:
        pass

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
    if model not in model_info:
        raise ValueError(f"unknown model: {model}")
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
    from briefing.summarizer_agent import evolve
    system = model_para["system_content"][stage] + model_para["system_content"]["additional"]
    notes = evolve.load_notes(stage)
    if notes:
        system += f"\n\n=== Learned style preferences (follow these) ===\n{notes}"
    resp = request_gpt(input_text, system, model)
    return resp["choices"][0]["message"]["content"]

def _split_headline(raw):
    """Split brief output 'HEADLINE: x\\n---\\n<body>' -> (headline, body)."""
    headline, body = "", raw
    if raw:
        lines = raw.splitlines()
        first = lines[0] if lines else ""
        if first.strip().upper().startswith("HEADLINE:"):
            headline = first.split(":", 1)[1].strip()
            parts = raw.split("---", 1)
            body = parts[1].strip() if len(parts) == 2 else "\n".join(lines[1:]).strip()
    return headline, body

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
        "recommend": WORK_DIR / "recommend.txt",
    }
    summarize_model = api_model["summarize_model"]
    model_name = model_info[summarize_model]["model"]
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
    max_input_tokens = model_info[summarize_model]["max_input"]
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
                summarize_model,
            )
            outlines.append((tag + "\n" if tag else "") + resp)

        outline_text = "\n\n".join(outlines)
        paths["outline"].write_text(outline_text, encoding="utf-8")

    ## brief (+ headline) — subjective
    if paths["brief"].exists() and paths["headline"].exists():
        brief_text = paths["brief"].read_text(encoding="utf-8")
        headline_text = paths["headline"].read_text(encoding="utf-8")
    else:
        raw = _subjective(outline_text, "brief", summarize_model)
        headline_text, brief_text = _split_headline(raw)
        paths["headline"].write_text(headline_text, encoding="utf-8")
        paths["brief"].write_text(brief_text, encoding="utf-8")

    ## recommend — subjective
    if paths["recommend"].exists():
        recommend_text = paths["recommend"].read_text(encoding="utf-8")
    else:
        recommend_text = _subjective(brief_text, "recommend", summarize_model)
        paths["recommend"].write_text(recommend_text, encoding="utf-8")

    return payload