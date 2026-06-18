<p align="center">
  <img src="images/Banner.png" alt="Briefing" width="100%" />
</p>

<p align="center">
  <strong>Automatically turn new videos from across platforms into concise, self-improving briefings.</strong>
</p>

<div class="flex" align="center">
  <img alt="Douyin" src="images/TikTok.svg" width="26">
  <img alt="Youtube" src="images/Youtube.svg" width="26">
  <img alt="TikTok" src="images/TikTok.svg" width="26">
  <img alt="Bilibili" src="images/Bilibili.svg" width="26">
</div>

<p align="center">
  <a href="#3-quick-start-no-configuration-required">Quick Start</a> · <a href="README_CN.md">中文文档</a> · <a href="#11-supported-platforms">Supported Platforms</a>
</p>

![Release](https://img.shields.io/github/v/release/YutaiGu/briefing?style=flat)
![Python](https://img.shields.io/badge/python-3.10-blue?style=flat)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey?style=flat)
![License](https://img.shields.io/github/license/YutaiGu/briefing?style=flat)

## 1. Overview

This is a backend service for **automatically tracking the creators you follow** and **summarizing their newly published videos** (including older content).

The system periodically checks whether specified creators have released new videos, automatically performs **download → transcription → content refinement**, and delivers **structured, concise summary reports** to the configured destination.

This enables you to quickly grasp the **core viewpoints and high-frequency insights** from a large volume of creator content in a very short amount of time.

### 1.1 Supported Platforms

| Platform | Support | Notes |
|--------|--------|------|
| <img src="images/Youtube.svg" width="14"/> **YouTube** | ✅ | Automatic |
| <img src="images/Bilibili.svg" width="14"/> **Bilibili** | ✅ | Automatic |
| <img src="images/TikTok.svg" width="14"/> **TikTok** | ✅ | Automatic |
| <img src="images/TikTok.svg" width="14"/> **Douyin** | ✅ | Automatic (via [f2](https://github.com/Johnserf-Seed/f2)) |
| 📡 **Live Stream Recordings** | ✅ via external tool [DouyinLiveRecorder](https://github.com/ihmily/DouyinLiveRecorder) | [See below for details](#12-external-downloader-compatibility) |
| 📕 **Xiaohongshu** | In development | |
| <img src="images/Instagram.svg" width="14"/> **Instagram** | In development | |
| <img src="images/Reddit.svg" width="14"/> **Reddit** | In development | |
| <img src="images/X.svg" width="14"/> **X** | In development | |

### 1.2 External Downloader Compatibility

This project is compatible with external downloaders.

Put audio files in the `briefing/data/audio` directory, or set the downloader’s output directory to `briefing/data/audio`.  
The system will automatically detect and process them.

### 1.3 Multiple Model Support

| Provider | Support |
|--------|--------|
| <img src="images/chatgpt.svg" width="14"/> **OpenAI** | ✅ |
| <img src="images/deepseek.svg" width="14"/> **DeepSeek** | ✅ |
| <img src="images/gemini.svg" width="14"/> **Gemini** | ✅ |
| 🔀 **OpenRouter** | ✅ |
| ✨ **More** | On the way |

![Multiple Model Support](images/6.png)

### 1.4 Self-Evolving Summaries

Leave a quick note on any report and the summary style **learns from your feedback**, getting closer to how you like it over time.

![Self-Evolving Summaries](images/7.png)

---

## 2. Feature Preview

### 2.1 Run Panel

![panel](images/2.png)

### 2.2 GUI Reading Interface

![panel](images/4.png)

### 2.3 Send Summary to Terminal

![panel](images/1.png)

---

# 3. Quick Start (No Configuration Required)

### 3.1 Download

Go to [Releases](https://github.com/YutaiGu/briefing/releases/) and download the latest `briefing-vX.X.X-windows.zip`.

> Windows 7 / 8 may require installing [Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)

### 3.2 Extract and Run

Extract to any directory and run: `briefing.exe`

### 3.3 API Configuration (Required)

This project relies on external APIs for:

* Content summarization
* Translation
* Text compression

![5](images/5.png)

Official OpenAI documentation:

* [https://platform.openai.com/docs/quickstart](https://platform.openai.com/docs/quickstart)

Beginner-friendly tutorial (third-party, OpenAI-compatible API):

* [https://github.com/chatanywhere/GPT_API_free?tab=readme-ov-file#如何使用](https://github.com/chatanywhere/GPT_API_free?tab=readme-ov-file#如何使用)

These resources provide step-by-step guidance on how to obtain an API key and configure it correctly.

### 3.4 ntfy Notifications (Optional)

This project uses **ntfy** as the message delivery channel.

You only need to choose a **unique string** as your topic, for example: `https://ntfy.sh/example123`

Summary reports can be read by opening this URL in a browser.

### 3.5 Source URL Format

![3](images/3.png)

- **YouTube**: https://www.youtube.com/@example/videos
- **BiliBili**: https://space.bilibili.com/example/upload/video
- **TikTok**: https://www.tiktok.com/@example

### 3.6 Firefox Cookie Support (Recommend)

If Firefox is installed on this machine and you have previously logged into video sites, the downloader will automatically read cookies from the default Firefox profile to handle videos accessible only after login. No additional configuration is required—simply ensure Firefox has downloaded and used content before starting the service.

## 4. Run From Source (Developers)

Environment requirement: Python 3.10 (Python 3.8 and 3.9 are not supported.)

```bash
git clone https://github.com/YutaiGu/briefing.git
cd briefing
conda create -n briefing python=3.10
conda activate briefing
pip install -r requirements.txt
python launcher.py
```

## 5. Feedback & Contributions

The project is under active development.  
Feedback is welcome — feel free to open an Issue for usage feedback, bug reports, or feature requests.

---

*This project is not affiliated with or endorsed by any third-party downloaders or platforms. Users are responsible for complying with the terms of service of the respective platforms.*