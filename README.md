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

## 🎬 See it in action

<p align="center">
  <img alt="Briefing demo" src="images/briefing01.gif" width="80%" />
</p>

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

<p align="center">
  <img src="https://img.shields.io/badge/OpenAI-000?logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/DeepSeek-4D6BFE?logo=deepseek&logoColor=white" />
  <img src="https://img.shields.io/badge/Gemini-886FBF?logo=googlegemini&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenRouter-6566F1?logo=openrouter&logoColor=white" />
  <img src="https://img.shields.io/badge/+%20more-on%20the%20way-lightgrey" />
</p>

<p align="center">
  <img alt="Multiple Model Support" src="images/6.png" width="80%" />
</p>

### 1.4 Self-Evolving Summaries

Leave a quick note on any report and the summary agent **learns from your feedback**, getting closer to how you like it over time.

![Self-Evolving Summaries](images/7.png)

---

## 2. Feature Preview

### 2.1 GUI Reading Interface

<p align="center">
  <img alt="Briefing demo" src="images/briefing02.gif" width="80%" />
</p>

### 2.2 Send Summary to Terminal

<p align="center">
  <img alt="Send Summary to Terminal" src="images/1.png" width="80%" />
</p>

---

## 3. Quick Start (No Configuration Required)

### 3.1 Download

Go to [Releases](https://github.com/YutaiGu/briefing/releases/) and download the latest build for your OS:

- **Windows** — `briefing-vX.X.X-windows.zip`
- **macOS** — `briefing-vX.X.X-macos.dmg`

> Windows 7 / 8 may require installing [Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)

### 3.2 Install and Run

- **Windows** — extract to any directory and run `briefing.exe`.
- **macOS** — open the `.dmg` and drag **Briefing** into Applications. On first launch (the app isn't notarized): double-click it, then go to **System Settings ▸ Privacy & Security** and click **Open Anyway**. After that, just double-click normally.

### 3.3 LLM API Configuration (Required)

![5](images/5.png)

### 3.4 Source URL Format

- **YouTube**: `https://www.youtube.com/@example/videos`
- **BiliBili**: `https://space.bilibili.com/example/upload/video`
- **TikTok**: `https://www.tiktok.com/@example`
- **Douyin**: `https://v.douyin.com/example/`

### 3.5 Browser Cookies (Recommended)

For content that requires login (e.g. Bilibili / Douyin homepages), just **log into the site in any installed browser** (Safari / Edge / Firefox / Chrome). On each run the downloader automatically reads and merges cookies from all of them into `cookies.txt` — no manual export needed.

### 3.6 ntfy Notifications (Optional)

This project uses **ntfy** as the message delivery channel.

You only need to choose a **unique string** as your topic, for example: `https://ntfy.sh/example123`

Summary reports can be read by opening this URL in a browser.

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