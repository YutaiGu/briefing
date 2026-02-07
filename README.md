# Video Monitoring & Summarization Service

[中文](README_CN.md)

## 1. Overview

This project is a backend service designed for **automatically tracking and summarizing long-form video content**.

The system periodically monitors specified creators, retrieves newly published videos, and automatically performs **video downloading, speech transcription, and content refinement**.
It then generates a **structured and concise summary report**, which is pushed to a designated receiver, allowing users to efficiently obtain **high-frequency, high-value information** without watching the full video.

Currently supported platforms:

* **YouTube**
* **BiliBili**

---

## 2. Feature Preview

![panel](images/1.png)

---

## 3. Configuration and Usage

### 3.1 Python Environment Requirements

* **Python 3.10 is required**
* Python 3.8 and 3.9 are not supported

An isolated Python environment is strongly recommended to avoid dependency conflicts.

```bash
conda create -n briefing python=3.10
conda activate briefing
pip install -r requirements.txt
```

---

### 3.2 API Configuration (Required)

This project relies on external APIs for:

* Content summarization
* Translation
* Text compression

Official OpenAI documentation:

* [https://platform.openai.com/docs/quickstart](https://platform.openai.com/docs/quickstart)

Beginner-friendly tutorial (third-party, OpenAI-compatible API):

* [https://github.com/chatanywhere/GPT_API_free?tab=readme-ov-file#如何使用](https://github.com/chatanywhere/GPT_API_free?tab=readme-ov-file#如何使用)

These resources provide step-by-step guidance on how to obtain an API key and configure it correctly.

---

### 3.3 Notification Configuration (ntfy)

This project uses **ntfy** as the message delivery channel.

You only need to choose a **unique string** as your topic, for example: `https://ntfy.sh/your_special_str`

Summary reports can be read by opening this URL in a browser.

---

### 3.4 Configuration File

API keys and ntfy settings should be filled in the following file:

* `data/config.txt`

This file should not be committed to the repository.

---

### 3.5 Running the Service

After configuring the environment and required settings, start the backend service from the project root directory.

```bash
python -m uvicorn backend.app.main:app --port 8000
```

## 4. Development Status

This project is currently under **active development**.  
APIs, features, and configuration details may change as the project evolves.

Testing, feedback, and suggestions are highly welcome.  
Please feel free to submit issues on GitHub for:
- Bug reports
- Usage feedback
- Feature requests

All constructive input is appreciated.