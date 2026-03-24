# AgenticSeek: Private, Local Manus Alternative.

<p align="center">
<img align="center" src="./media/agentic_seek_logo.png" width="300" height="300" alt="Agentic Seek Logo">
<p>

  English | [中文](./README_CHS.md) | [繁體中文](./README_CHT.md) | [Français](./README_FR.md) | [日本語](./README_JP.md) | [Português (Brasil)](./README_PTBR.md) | [Español](./README_ES.md) | [Türkçe](./README_TR.md)

*A **100% local alternative to Manus AI**, this voice-enabled AI assistant autonomously browses the web, writes code, and plans tasks while keeping all data on your device. Tailored for local reasoning models, it runs entirely on your hardware, ensuring complete privacy and zero cloud dependency.*

[![Visit AgenticSeek](https://img.shields.io/static/v1?label=Website&message=AgenticSeek&color=blue&style=flat-square)](https://fosowl.github.io/agenticSeek.html) ![License](https://img.shields.io/badge/license-GPL--3.0-green) [![Discord](https://img.shields.io/badge/Discord-Join%20Us-7289DA?logo=discord&logoColor=white)](https://discord.gg/8hGDaME3TC) [![Twitter](https://img.shields.io/twitter/url/https/twitter.com/fosowl.svg?style=social&label=Update%20%40Fosowl)](https://x.com/Martin993886460) [![GitHub stars](https://img.shields.io/github/stars/Fosowl/agenticSeek?style=social)](https://github.com/Fosowl/agenticSeek/stargazers)

### Why AgenticSeek ?

* 🔒 Fully Local & Private - Everything runs on your machine — no cloud, no data sharing. Your files, conversations, and searches stay private.

* 🌐 Smart Web Browsing - AgenticSeek can browse the internet by itself — search, read, extract info, fill web form — all hands-free.

* 💻 Autonomous Coding Assistant - Need code? It can write, debug, and run programs in Python, C, Go, Java, and more — all without supervision.

* 🧠 Smart Agent Selection - You ask, it figures out the best agent for the job automatically. Like having a team of experts ready to help.

* 📋 Plans & Executes Complex Tasks - From trip planning to complex projects — it can split big tasks into steps and get things done using multiple AI agents.

* 🎙️ Voice-Enabled - Clean, fast, futuristic voice and speech to text allowing you to talk to it like it's your personal AI from a sci-fi movie. (In progress)

### **Demo**

> *Can you search for the agenticSeek project, learn what skills are required, then open the CV_candidates.zip and then tell me which match best the project*

https://github.com/user-attachments/assets/b8ca60e9-7b3b-4533-840e-08f9ac426316

Disclaimer: This demo, including all the files that appear (e.g: CV_candidates.zip), are entirely fictional. We are not a corporation, we seek open-source contributors not candidates.

> 🛠⚠️️ **Active Work in Progress**

> 🙏 This project started as a side-project and has zero roadmap and zero funding. It's grown way beyond what I expected by ending in GitHub Trending. Contributions, feedback, and patience are deeply appreciated.

## ARK95X Python Scaffold

This repository now includes a Python-only ARK95X scaffold under `ark95x/` with a unified `main.py` entrypoint.

### Modules

- `ark95x/config.py`
  - Environment loading via `python-dotenv`
  - Desktop/cloud path resolution
  - API key and webhook configuration access

- `ark95x/utils.py`
  - JSON read/write helpers
  - Timestamp helpers
  - SHA-256 file hashing
  - Lightweight JSON schema validation utility

- `ark95x/task_runner.py`
  - Async task executor with retry + backoff
  - Structured task result object

- `ark95x/emerald_sync.py`
  - Snapshot-based file state tracking
  - Delta detection (`added`, `modified`, `deleted`)
  - Persistent sync state file

- `ark95x/ark95x_omni.py`
  - Omni task orchestration hub
  - Provider routing by task type
  - Webhook payload handling with signature validation

- `ark95x/n95_revenue.py`
  - Revenue and pipeline record persistence
  - KPI summaries by category/status

### Entry Point

`main.py` provides a single command-line interface:

- `python main.py sync`
- `python main.py omni --type analysis --task-id task-001`
- `python main.py revenue add --account "Prospect A" --amount 15000 --category real-estate --status proposal --source inbound`
- `python main.py revenue summary`

### Environment Variables

ARK95X settings were added to `.env.example`:

- `ARK95X_ENV`
- `ARK95X_DATA_ROOT`
- `ARK95X_STATE_DIR`
- `ARK95X_LOGS_DIR`
- `ARK95X_SYNC_STATE_FILE`
- `ARK95X_REVENUE_STATE_FILE`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `PERPLEXITY_API_KEY`
- `OMNI_WEBHOOK_INGEST_URL`
- `OMNI_WEBHOOK_SECRET`
