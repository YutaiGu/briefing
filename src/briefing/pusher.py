import json
import requests
from datetime import datetime

from briefing.config import api_model, READ_LANGUAGE, OUTPUT_DIR, NTFY_SERVER, COMPRESS_LEVEl, REPORT_DIR, PUSH_TO, load_prompt
from briefing.db import get_unpushed, update_entries
from briefing.summarizer_agent import request_gpt

_TRANSLATE_TMPL = load_prompt("translate")
_ENGLISH = ("en", "en-us", "english", "English")

def pushto_ntfy(message: str) -> bool:
    if NTFY_SERVER is None:
        return False

    url = f"https://ntfy.sh/{NTFY_SERVER}"
    headers = {
        "Title": "Briefing Summary"
    }
    try:
        response = requests.post(
            url, 
            data=message.encode("utf-8"), 
            headers = headers,
            timeout=(10, 60),  # Connection timeout: 10s, Read timeout 120s
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Push Error (ntfy): {e}")
        return False

def pushto_localfile(message: str) -> None:
    try:
        now = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        log_file = REPORT_DIR / f"{now}.txt"
        with log_file.open("w", encoding="utf-8") as f:
            f.write(f"{message}\n")
        return True
    except Exception:
        return False

def _no_translate(input: str):
    return {"choices": [{"message": {"content": input}}]}

def _compress_clause() -> str:
    if COMPRESS_LEVEl == 100:
        return ""
    return (f" Then compress to approximately {COMPRESS_LEVEl}% of the original length: "
            "preserve the core thesis, key facts, and reasoning structure; merge related "
            "arguments that support the same conclusion and cut repetition and restatements.")

def translate_text(input: str, language: str) -> str:
    if language in _ENGLISH:
        return _no_translate(input)
    system = _TRANSLATE_TMPL.format(language=language, compress="")
    return request_gpt(input, system, api_model["translate_model"])

def translate_and_compress(input: str, language: str):
    if language in _ENGLISH and COMPRESS_LEVEl == 100:
        return _no_translate(input)
    target = "English" if language in _ENGLISH else language
    system = _TRANSLATE_TMPL.format(language=target, compress=_compress_clause())
    return request_gpt(input, system, api_model["translate_model"])

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

            vid_dir = OUTPUT_DIR / str(v.video_id)
            headline_src = (vid_dir / "headline.txt").read_text(encoding="utf-8").strip() if (vid_dir / "headline.txt").exists() else ""
            short_src = (vid_dir / "short.txt").read_text(encoding="utf-8").strip() if (vid_dir / "short.txt").exists() else ""

            print(f"[Translating] {v.video_id}")
            try:
                content = translate_and_compress(text, READ_LANGUAGE)['choices'][0]['message']['content']
            except Exception:
                content = text

            headline = ""
            if headline_src:
                try:
                    headline = translate_text(headline_src, READ_LANGUAGE)['choices'][0]['message']['content']
                except Exception:
                    headline = headline_src

            short = ""
            if short_src:
                try:
                    short = translate_text(short_src, READ_LANGUAGE)['choices'][0]['message']['content']
                except Exception:
                    short = short_src

            (vid_dir / "report.json").write_text(
                json.dumps({"content": content, "headline": headline, "short": short}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            notification = f"# {upload_date} {source}\n{title}\n"
            if headline or short:
                notification += (f"**{headline}**\n" if headline else "") + (f"> {short}\n" if short else "") + "\n---\n"
            notification += content
            parts.append(notification)

        except Exception:
            continue
    
    if not parts:
        return

    body = "\n\n".join(parts)

    try:
        target = (PUSH_TO or "ntfy").strip()
        if target == "LocalFile":
            ok = pushto_localfile(body)
        else:
            ok = pushto_ntfy(body)

        if ok:
            for v in todo:
                v.pushed = 1
            update_entries(session, todo)
        elif target != "LocalFile":
            pushto_localfile(body)
        print(f"Finished Sending")
    except Exception:
        return
