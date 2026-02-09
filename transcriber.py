import os
from pathlib import Path
from datetime import datetime
import torch
import whisper
import shutil
from moviepy import AudioFileClip
from multiprocessing import Pool, cpu_count

from config import DATA_DIR, api_model, TRANSCRIBER_LIMIT, POOL_NUM
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
        _ = whisper.load_model(model_name)
    except Exception as e:
        print(f"Failed to load model {model_name}: {e}")
        raise

def load_whisper_model() -> None:
    global _MODEL
    model_name = api_model["whisper_model"]
    try:
        if _MODEL is None:
            _MODEL = whisper.load_model(model_name)
    except Exception as e:
        print(f"Failed to load model {model_name}: {e}")
        raise

def Clean_Files(filename, temporary_dir):
    import shutil
    shutil.rmtree(f"{temporary_dir}/{filename}_cut")

def Split_Video_File(video_file, temporary_dir, split_duration=1800):
    """
    根据给定的切割时长将视频文件切割成多个片段

    Args:
        filename (str): 需要被切割的视频文件名。
        split_duration (int, optional): 每个切割视频片段的时长（以秒为单位）。默认值为180秒。

    Returns:
        filelist (list): 一个包含所有切割视频片段文件路径的列表。
            ['E:\\Pycharm_Projects\\TryWhisper\\temporary/video_cut/TestVideo_0.mp4', ...]
    """
    filename = os.path.basename(video_file).split('.')[0]
    os.makedirs(f"{temporary_dir}/{filename}_cut", exist_ok=True)

    video = AudioFileClip(video_file)

    # 计算文件总时长和切割点。
    total_duration = video.duration
    split_points = list(range(0, int(total_duration), split_duration))
    split_points.append(int(total_duration))
    filelist = []

    # 切割视频文件
    for i in range(len(split_points) - 1):
        start_time = split_points[i]
        end_time = split_points[i + 1]
        split_video = video.subclipped(start_time, end_time)
        output_filename = f"{temporary_dir}/{filename}_cut/V_{i}.mp3"
        split_video.write_audiofile(  # 不打印帧进度, 只在真正错误时输出
            output_filename,
            logger=None,
            ffmpeg_params=["-nostats", "-loglevel", "error"],
        )
        # output_filename = f"{temporary_dir}/{filename}_cut/V_{i}.mp4"
        # split_video.write_videofile(output_filename)
        filelist.append(output_filename)

    video.close()
    return filelist


def Whisper_Audio(video_file, language=None):
    load_whisper_model()
    use_fp16 = torch.cuda.is_available()

    result = _MODEL.transcribe(
        video_file,
        verbose=False,
        language=language,
        fp16=use_fp16,
    )
    return result["text"]


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
    cut_line = "\n- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n"

    # 初始化，创建必要文件
    temporary_dir = (DATA_DIR / "temporary" / filename).as_posix()
    Path(temporary_dir).mkdir(parents=True, exist_ok=True)

    output_dir = DATA_DIR / "output" / filename
    output_dir.mkdir(parents=True, exist_ok=True)

    whisper_path = (output_dir / "whisper.txt").as_posix()
    history_path = (output_dir / "history.txt").as_posix()

    # 清空txt文档内容
    with open(whisper_path, "w", encoding="utf-8") as whisper_file:
        whisper_file.write(f"{filename} at {start_time}:{cut_line}")

    with open(history_path, "w", encoding="utf-8") as history_file:
        history_file.write(f"{filename} at {start_time}:{cut_line}")

    # 切割Video
    filelist = Split_Video_File(video_file, temporary_dir)
    print(f"[SPLIT DONE] {filename}")

    # 写入txt
    # progress_bar = tqdm(total=len(filelist), desc="Processing Video") # 进度条
    for fp in filelist:
        result = Whisper_Audio(fp, language=language)  # 获取音频识别的结果
        # progress_bar.update(1)

        with open(whisper_path, "a", encoding="utf-8") as whisper_file:
            whisper_file.write(result + "\n")
    print(f"[WHISPER DONE] {filename}")

    Clean_Files(filename, temporary_dir)  # 清除视频文件
    print(f"[CLEAN DONE] {filename}")

    return payload