import os
from pathlib import Path
from datetime import datetime
from faster_whisper import WhisperModel
import shutil
import contextlib
import threading
import time
#from moviepy import AudioFileClip
from multiprocessing import Pool, cpu_count

from config import api_model, TRANSCRIBER_LIMIT, POOL_NUM, OUTPUT_DIR, TEMPORARY_DIR
from db import get_untranscribed, update_entries, entry_to_payload, payload_to_entry

_MODEL = None

def one_transcriber(payload):
    try:
        print(f"Transcribing {payload['video_id']}")
        payload = Video_Processing(payload)
        payload['transcribed'] = 1  # Mark only after final success
        return payload
    except Exception as e:
        print(f"Error from one_transcriber: {e}")
        return None

def transcriber(session) -> None:
    todo = get_untranscribed(session, TRANSCRIBER_LIMIT)
    if not todo:
        return

    workers = min(cpu_count(), POOL_NUM)
    with Pool(processes=workers) as pool:
        payloads = [entry_to_payload(v) for v in todo]
        for updated in pool.imap(one_transcriber, payloads):
            if updated is None:
                continue
            update_entries(session, [payload_to_entry(updated)])

def check_whisper_model() -> None:
    # 1) ensure ffmpeg is available
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")
    
    # 2) ensure whisper is available
    model_name = api_model["whisper_model"]
    try:
        _ = WhisperModel(model_name, device="cpu", compute_type="int8")
    except Exception as e:
        print(f"Failed to load model {model_name}: {e}")
        raise

def load_whisper_model(device: str = "cpu", compute_type: str = "int8") -> None:
    global _MODEL
    model_name = api_model["whisper_model"]
    try:
        if _MODEL is None:
            _MODEL = WhisperModel(model_name, device=device, compute_type=compute_type)
    except Exception as e:
        print(f"Failed to load model {model_name}: {e}")
        raise

def Clean_Files(filename, temporary_dir):
    p = Path(temporary_dir) / filename
    if p.exists():
        shutil.rmtree(p)

'''
def Split_Video_File(video_file, temporary_dir, split_duration=1800):
    """
    Split a video file into multiple segments based on the specified duration.

    Args:
        filename (str): The name of the video file to be split.
        split_duration (int, optional): The duration of each split video segment (in seconds). Default is 180 seconds.

    Returns:
        filelist (list): A list containing the file paths of all split video segments.
            ['E:\\Pycharm_Projects\\TryWhisper\\temporary/video_cut/TestVideo_0.mp4', ...]
    """
    filename = os.path.basename(video_file).split('.')[0]
    os.makedirs(f"{temporary_dir}/{filename}_cut", exist_ok=True)

    video = AudioFileClip(video_file)

    # Calculate the total duration of the file and determine the cut points
    total_duration = video.duration
    split_points = list(range(0, int(total_duration), split_duration))
    split_points.append(int(total_duration))
    filelist = []

    # Split video files
    for i in range(len(split_points) - 1):
        start_time = split_points[i]
        end_time = split_points[i + 1]
        try:
            split_video = video.subclipped(start_time, end_time)
            output_filename = f"{temporary_dir}/{filename}_cut/V_{i}.mp3"
            split_video.write_audiofile(  # output only when a error occurs
                output_filename,
                logger=None,
                ffmpeg_params=["-nostats", "-loglevel", "error"],
            )
            # output_filename = f"{temporary_dir}/{filename}_cut/V_{i}.mp4"
            # split_video.write_videofile(output_filename)
            filelist.append(output_filename)
        finally:
            split_video.close()
            
    video.close()
    return filelist
'''

def Whisper_Audio(video_file, language=None):
    load_whisper_model(device="cpu", compute_type="int8")

    def heartbeat():
        while True:
            print(".", end="", flush=True)
            time.sleep(15)

    threading.Thread(target=heartbeat, daemon=True).start()

    try:
        with open(os.devnull, "w") as devnull, contextlib.redirect_stderr(devnull):
            segments, info = _MODEL.transcribe(
                video_file,
                language=language,
            )
            text = "".join(seg.text for seg in segments)
    except Exception as e:
        raise RuntimeError(f"Whisper failed on {video_file}: {e}") from e
    
    return text

def Video_Processing(payload):
    raw = payload['language']
    language = None
    if raw:
        raw = raw.lower()
        if raw.startswith("en"):
            language = "en"
        elif raw.startswith(("zh", "cn")):
            language = "zh"
        # else:
            # language = raw.split("-")[0]
    video_file = payload['file_path']
    filename = os.path.basename(video_file).split('.')[0]
    print(f"[START] {filename}")
    start_time = datetime.now()
    start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")

    # create necessary files
    temporary_dir = (TEMPORARY_DIR / filename).as_posix()
    Path(temporary_dir).mkdir(parents=True, exist_ok=True)

    output_dir = OUTPUT_DIR / filename
    output_dir.mkdir(parents=True, exist_ok=True)

    whisper_path = (output_dir / "whisper.txt").as_posix()

    # Clear the contents
    with open(whisper_path, "w", encoding="utf-8") as whisper_file:
        whisper_file.write(f"{filename} at {start_time}:\n")

    # Split
    # filelist = Split_Video_File(video_file, temporary_dir)
    print(f"[WHISPER] {filename} ")
    
    result = Whisper_Audio(video_file, language=language)
    with open(whisper_path, "a", encoding="utf-8") as whisper_file:
        whisper_file.write(result + "\n")

    print(f"[WHISPER DONE] {filename}")

    Clean_Files(filename, temporary_dir)
    print(f"[CLEAN DONE] {filename}")

    return payload