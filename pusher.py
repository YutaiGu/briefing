from serverchan_sdk import sc_send
import requests
from datetime import datetime

from config import api_model, READ_LANGUAGE, OUTPUT_DIR, SERVER3_KEY, NTFY_SERVER, REPORT_DIR, COMPRESS_LEVEl
from db import get_unpushed, update_entries
from summarizer import request_gpt


def pushto_Server3(message: str) -> None:
    options = {"tags": "Briefing Summary"}
    response = sc_send(SERVER3_KEY, "Briefing Summary", message, options)

    if response["code"] != 0:
        print(f"Push Error: {response}")

def pushto_ntfy(message: str) -> None:
    if NTFY_SERVER is None:
        return 

    url = f"https://ntfy.sh/{NTFY_SERVER}"
    headers = {
        "Title": "Briefing Summary",
    }
    try:
        response = requests.post(
            url, 
            data=message.encode("utf-8"), 
            headers = headers,
            timeout=(10, 60),  # Connection timeout: 10s, Read timeout 120s
        )
        response.raise_for_status()
    except Exception as e:
        print(f"Push Error (ntfy): {e}")

def pushto_localfile(message: str) -> None:
    try:
        now = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        log_file = REPORT_DIR / f"{now}.txt"
        with log_file.open("w", encoding="utf-8") as f:
            f.write(f"{message}\n")
    except Exception:
        pass

def translate_and_compress(input: str, language: str):
    if language not in ("en", "en-us", "english", "English") and COMPRESS_LEVEl != 100:  # translate + compress
        response_json = request_gpt(
            input,
            f"Translate the user input into {language}. Translate the user input into {language}. Compress the content to approximately {COMPRESS_LEVEl}% of the original length. Preserve the core thesis, key financial facts, and the overall reasoning structure. Merge related arguments that support the same conclusion. Eliminate repeated arguments, illustrative restatements, and secondary justifications. Maintain logical coherence and emphasis, but do not preserve one-to-one paragraph mapping. Output only the translation.",
            api_model["translate_model"],
        )
    elif language not in ("en", "en-us", "english", "English") and COMPRESS_LEVEl == 100:  # translate
        response_json = request_gpt(
            input,
            f"You are a translation engine. Your task is to translate the user input into {language}. Output only the translation. Do not add any commentary, prefixes, suffixes, or explanations. Preserve the original formatting exactly.",
            api_model["translate_model"],
        )
    elif COMPRESS_LEVEl != 100:  # compress
        response_json = request_gpt(
            input,
            f"Compress the content to approximately {COMPRESS_LEVEl}% of the original length. Preserve the core thesis, key financial facts, and the overall reasoning structure. Merge related arguments that support the same conclusion. Eliminate repeated arguments, illustrative restatements, and secondary justifications. Maintain logical coherence and emphasis, but do not preserve one-to-one paragraph mapping. Output only the translation.",
            api_model["translate_model"],
        )
    else:  # origin
        return {
            "choices": [
                {
                    "message": {
                        "content": input
                    }
                }
            ]
        }
    return response_json

def pusher(session, limit: int) -> None:
    todo = get_unpushed(session, limit)
    if not todo:
        return
    print("Sending...")

    parts = []
    for v in todo:
        try:
            if not v.video_id:
                continue
            brief_path = OUTPUT_DIR / str(v.video_id) / "brief.txt"
            if not brief_path.exists():
                continue
            
            print(f"[Packing] {v.video_id}")
            upload_date = v.upload_date or v.downloaded_at or v.inserted_at or ""
            extractor = v.extractor or ""
            source = (v.source or "").replace("https://www.", "").replace("http://www.", "")
            title = v.title or ""

            text = brief_path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            
            try:
                print(f"[Translating & Compressing] {v.video_id}")
                text = translate_and_compress(text, READ_LANGUAGE)['choices'][0]['message']['content']
            except Exception:
                pass
            
            # translate if needed
            parts.append(
                f"# {upload_date} {source}\n"
                f"{title}\n"
                f"{text}"
            )

        except Exception:
            continue
    
    if not parts:
        return

    body = "\n\n".join(parts)

    try:
        #pushto_Server3(body)
        pushto_ntfy(body)
        #pushto_localfile(body)
        for v in todo:
            v.pushed = 1
        update_entries(session, todo)
        print(f"Finished Sending")
    except Exception:
        return