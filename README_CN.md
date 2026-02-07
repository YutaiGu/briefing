# Video Monitoring & Summarization Service

[English](README_EN.md)

## 1. 功能简介

这是一个用于 **自动跟踪并总结长视频内容** 的后端服务。

系统会定期获取指定博主新发布的视频，自动完成 **下载、转写与内容精炼**，并将 **结构化、简洁的总结报告** 推送到指定接收端，帮助用户以极低时间成本获取 **高频、重要信息**。

当前已支持以下平台：
- **YouTube**
- **BiliBili**

---

## 2. 功能展示

![panel](images/1.png)

---

## 3. 配置与运行说明

### 3.1 Python 环境要求

- **Python 3.10（必须）**
- 不支持 Python 3.8 / 3.9

建议使用独立环境（示例使用 conda）：

```bash
conda create -n briefing python=3.10
conda activate briefing
pip install -r requirements.txt
```

### 3.2 API 配置（必须）
本项目依赖API用于：内容总结、翻译、压缩处理

OpenAI官方文档
* [https://platform.openai.com/docs/quickstart](https://platform.openai.com/docs/quickstart)

中文获取教程（国内代理网站）
* [https://github.com/chatanywhere/GPT_API_free?tab=readme-ov-file#如何使用](https://github.com/chatanywhere/GPT_API_free?tab=readme-ov-file#如何使用)

### 3.3 消息推送配置（ntfy）
本项目使用 ntfy 作为消息推送通道，只需要想一个自己专属、不会重复的字符串即可：https://ntfy.sh/your_special_str

可以通过登录此链接的方式阅读报告

### 3.4 将 API key 和 ntfy 地址填入 data/config.txt

该文件不应提交至代码库。

### 3.5 启动服务
激活环境后，在项目根目录执行：

```bash
python -m uvicorn backend.app.main:app --port 8000
```

## 4. 开发阶段说明

本项目目前仍处于**持续开发阶段**，接口设计、功能细节及配置方式可能会发生调整。

欢迎进行测试、试用，并通过 GitHub Issues 提交：
- 使用反馈
- 问题报告
- 功能建议

所有建设性意见都将有助于项目的进一步完善。