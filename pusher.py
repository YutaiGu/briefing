from serverchan_sdk import sc_send
import requests
from datetime import datetime

from config import api_model, READ_LANGUAGE, OUTPUT_DIR, SERVER3_KEY, NTFY_SERVER, REPORT_DIR
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

def translate(input: str, language: str):
    response_json = request_gpt(
        input,
        f"You are a translation engine. Your task is to translate the user input into {language}. Output only the translation. Do not add any commentary, prefixes, suffixes, or explanations. Preserve the original formatting exactly.",
        api_model["translate_model"],
    )
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
            upload_date = v.upload_date or ""
            extractor = v.extractor or ""
            source = v.source or ""
            title = v.title or ""

            text = brief_path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            
            language = READ_LANGUAGE
            if language and language not in ("en", "en-us", "english", "English"):
                try:
                    print(f"[Translating] {v.video_id}")
                    text = translate(text, language)['choices'][0]['message']['content']
                except Exception:
                    pass
            
            # translate if needed
            parts.append(
                f"# {upload_date} {extractor}\n"
                f"{source}\n"
                f"{title}\n"
                f"{text}"
            )
            v.pushed = 1

        except Exception:
            continue
    
    if not parts:
        return

    body = "\n\n".join(parts)

    try:
        #pushto_Server3(body)
        pushto_ntfy(body)
        pushto_localfile(body)
        update_entries(session, todo)
        print(f"Finished Sending")
    except Exception:
        return