# summarizer.py
from datetime import datetime
import requests
import tiktoken
from pathlib import Path
from multiprocessing import Pool, cpu_count

from .config import api_info, model_info, model_para, api_model, OUTPUT_DIR
from .config import SUMMARIZER_LIMIT
from .db import get_unsummarized, update_entries

def one_summarizer(entry):
    try:
        print(f"Summarizing {entry.video_id}")
        entry = Text_Processing(entry)
        entry.summarized = 1  # Mark only after final success
        return entry
    except Exception:
        return None

def summarizer(session) -> None:
    todo = get_unsummarized(session, SUMMARIZER_LIMIT)
    if not todo:
        return

    workers = min(cpu_count(), 2)
    with Pool(processes=workers) as pool:
        for updated in pool.imap(one_summarizer, todo):
            if updated is None:
                continue
            update_entries(session, [updated])

def request_gpt(input, system_content, which_api, model):
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
    if not which_api:
        raise ValueError("which_api is required")
    if not model:
        raise ValueError("model is required")
    if which_api not in api_info:
        raise ValueError(f"unknown api slot: {which_api}")
    if model not in model_info:
        raise ValueError(f"unknown model: {model}")

    api_key = api_info[which_api]["api_key"]
    try:
        encoding = tiktoken.encoding_for_model(model_info[model]["model"])
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    # 请求体
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

    # 请求头
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 发送请求
    try:
        response = requests.post(api_info[which_api]["url_redirect"], json = payload, headers = headers)
    except Exception as e:
        print(f"An error occurred:", str(e))
        print(f"Text token: {len(encoding.encode(input))}")
        print(response.json())

    # 输出信息
    response_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response_json = response.json()
    cost = (model_info[model]["input_price"]*response_json['usage']['prompt_tokens']+model_info[model]["output_price"]*response_json['usage']['completion_tokens'])/1000
    print(response_time + ":   ",
          "Tokens: input:", f"{response_json['usage']['prompt_tokens']:<6}",
          "output:", f"{response_json['usage']['completion_tokens']:<6}",
          "total:", f"{response_json['usage']['total_tokens']:<6}",
          "   Cost:", round(cost, 5))

    return response_json

def summarizer_request_gpt(input, which_system, which_api, model):
    '''
    Args:
        input (str): 发送的user内容
        which_system (str): 请求提示词
        which_api (str): 使用的api
        model (str): 使用的模型

    Returns:
        response_txt (str):
        history (list):
    '''
    if not which_api:
        raise ValueError("which_api is required")
    if not model:
        raise ValueError("model is required")
    if not which_system:
        raise ValueError("which_system is required")
    if which_api not in api_info:
        raise ValueError(f"unknown api slot: {which_api}")
    if model not in model_info:
        raise ValueError(f"unknown model: {model}")
    if which_system not in model_para["system_content"]:
        raise ValueError(f"unknown system prompt: {which_system}")

    system_content = model_para["system_content"][which_system] + model_para["system_content"]['additional']

    response_json = request_gpt(input, system_content, which_api, model)
    response_txt =response_json['choices'][0]['message']['content']
    history = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": input},
        {"role": "assistant", "content": response_txt}
    ]

    return response_txt, history

def Text_Processing(entry):
    file_name = Path(entry.file_path).stem
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
    outline_content = model_para["system_content"]["outline_trace"] + model_para["system_content"]["additional"]
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
    print(f"[Outline] {file_name}:")
    if paths["outline"].exists():
        with open(paths["outline"], "r", encoding="utf-8") as f:
            outline_text = f.read()
            print("outline.txt already exists.")
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
                "outline_trace",
                api_model["summarize_api"],
                summarize_model,
            )
            outlines.append((tag + "\n" if tag else "") + resp)

        outline_text = "\n\n".join(outlines)
        paths["outline"].write_text(outline_text, encoding="utf-8")

    ## step3: Brief
    print(f"[Brief] {file_name}:")
    brief_text, brief_history = summarizer_request_gpt(
        outline_text,
        "brief",
        api_model["summarize_api"],
        api_model["summarize_model"],
    )
    paths["brief"].write_text(brief_text, encoding="utf-8")

    return entry