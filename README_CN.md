<p align="center">
  <img src="images/Banner.png" alt="Briefing" width="100%" />
</p>

<p align="center">
  <strong>自动聚合各平台发布的新视频，生成自我迭代的精炼简报</strong>
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

## 🎬 演示

<p align="center">
  <img alt="Briefing demo" src="images/briefing01.gif" width="100%" />
</p>

## 1. 功能简介

这是一个用于 **自动跟踪你订阅的博主** 并 **总结其最新发布的视频** (包括往期视频) 的服务。

系统会定期检查指定博主是否有新视频发布，自动完成 **下载 → 转写 → 内容精炼**，并生成 **结构化、简洁的总结报告** 推送到指定接收端。可在极短时间内掌握大量博主输出的 **核心观点与高频信息**。

### 1.1 当前支持平台

| Platform | Support | Notes |
|--------|--------|------|
| <img src="images/Youtube.svg" width="14"/> **YouTube** | ✅ | 自动 |
| <img src="images/Bilibili.svg" width="14"/> **Bilibili** | ✅ | 自动 |
| <img src="images/TikTok.svg" width="14"/> **TikTok** | ✅ | 自动 |
| <img src="images/TikTok.svg" width="14"/> **Douyin** | ✅ | 自动（通过 [f2](https://github.com/Johnserf-Seed/f2)）|
| 📡 **Live Stream Recordings** | 外部下载器支持 [DouyinLiveRecorder](https://github.com/ihmily/DouyinLiveRecorder) | [See below for details](#12-external-downloader-compatibility) |
| 📕 **Xiaohongshu** | 开发中 | |
| <img src="images/Instagram.svg" width="14"/> **Instagram** | 开发中 | |
| <img src="images/Reddit.svg" width="14"/> **Reddit** | 开发中 | |
| <img src="images/X.svg" width="14"/> **X** | 开发中 | |

### 1.2 本项目兼容外部下载器
将下载目录/外部音频文件置于`briefing/data/audio`目录，系统将自动检测并处理这些文件。

### 1.3 多模型支持

| 服务商 | 是否支持 |
|--------|--------|
| <img src="images/chatgpt.svg" width="14"/> **OpenAI** | ✅ |
| <img src="images/deepseek.svg" width="14"/> **DeepSeek** | ✅ |
| <img src="images/gemini.svg" width="14"/> **Gemini** | ✅ |
| 🔀 **OpenRouter** | ✅ |
| ✨ **More** | 即将到来 |

![多模型支持](images/6.png)

### 1.4 自进化摘要

在任意报告下留一句反馈，摘要Agent便会**从你的反馈中学习**，随时间越来越贴合你的喜好。

![自进化摘要](images/7.png)

---

## 2. 功能展示

### 2.1 图形化界面阅读

<p align="center">
  <img alt="Briefing demo" src="images/briefing01.gif" width="100%" />
</p>

### 2.2 发送总结到终端
![1](images/1.png)

---

## 3. 快速开始（无需配置，一键使用）

### 3.1 下载

前往 [Releases](https://github.com/YutaiGu/briefing/releases/)，下载最新版 `briefing-vX.X.X-windows.zip`

> Windows 7/8 或更早期版本需安装[Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)

### 3.2 解压并运行

解压到任意目录，双击 `briefing.exe` 即可启动。

### 3.3 API 配置（必须）
本项目依赖API用于：内容总结、翻译、压缩处理

![5](images/5.png)

OpenAI官方文档
* [https://platform.openai.com/docs/quickstart](https://platform.openai.com/docs/quickstart)

中文获取教程（国内代理网站）
* [https://github.com/chatanywhere/GPT_API_free?tab=readme-ov-file#如何使用](https://github.com/chatanywhere/GPT_API_free?tab=readme-ov-file#如何使用)

### 3.4 ntfy消息推送配置（可选）
本项目使用 ntfy 作为消息推送通道，只需要想一个自己专属、不会重复的字符串即可：`https://ntfy.sh/example123`

可以通过网页登录此链接的方式阅读报告

### 3.5 主页链接填写方式

![3](images/3.png)

- **YouTube**: https://www.youtube.com/@example/videos
- **BiliBili**: https://space.bilibili.com/example/upload/video
- **TikTok**: https://www.tiktok.com/@example

### 3.6 Firefox（推荐）

如果本机安装了 Firefox 并且曾经登录过视频站点，下载器会自动读取默认 Firefox 配置文件的 cookies，用于处理仅登录可见的视频。无需额外配置，启动服务前保持 Firefox 已下载且使用过即可。

## 4. 从源码运行（开发者）

**环境要求**：Python 3.10（不支持 3.8 / 3.9）

```bash
git clone https://github.com/YutaiGu/briefing.git
cd briefing
conda create -n briefing python=3.10
conda activate briefing
pip install -r requirements.txt
python launcher.py
```

## 5. 反馈与贡献

项目持续迭代中，欢迎通过Issues提交：使用反馈 · 问题报告 · 功能建议

---

*本项目与任何第三方下载器及相关平台不存在官方合作或隶属关系。用户需自行遵守各平台服务条款。*