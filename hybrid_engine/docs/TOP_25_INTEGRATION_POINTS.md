# TOP 25 INTEGRATION POINTS
## ARK95X Hybrid Engine — OpenClaw · BlackBox Desktop · Ollama · Comet · Copilot
### End-to-End Routing with Bottleneck Bridge Architecture

---

## ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WINDOWS OS WRAPPER (Copilot)                     │
│         System Tray · Global Hotkey · Transparent Overlay           │
│                    Clipboard Bridge · IPC                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                        COMMS HUB (#25)                              │
│         Pub/Sub · WebSocket Relay · Token Streaming · Audit         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                     HYBRID ROUTER (#24)                             │
│    Task Classification · Pipeline Chaining · Fan-out · Caching      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                  BOTTLENECK BRIDGE (#23) ◄── ALL TRAFFIC            │
│   Priority Queue · Circuit Breaker · Load Balancer · Failover       │
└──┬──────────┬──────────┬──────────┬──────────┬──────────────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│OPEN  │ │BLACK   │ │OLLAMA  │ │COMET / │ │COPILOT │
│CLAW  │ │BOX     │ │(Local) │ │PERPLX  │ │(GitHub)│
│#1-5  │ │#6-10   │ │#11-14  │ │#15-18  │ │#19-22  │
└──────┘ └────────┘ └────────┘ └────────┘ └────────┘
   │          │          │          │          │
   └──────────┴──────────┴──────────┴──────────┘
                    BRIDGES LAYER
         Ollama↔OpenClaw · Copilot↔BlackBox · Comet↔Ollama
```

---

## THE 25 INTEGRATION POINTS

### OPENCLAW — Points #1-5

| # | Integration Point | File | Method |
|---|-------------------|------|--------|
| 1 | **REST API Task Dispatch** | `clients/openclaw_client.py` | `dispatch_task()` |
| 2 | **WebSocket Streaming Bridge** | `clients/openclaw_client.py` | `stream_task()` |
| 3 | **Tool-Call Passthrough** (shell/file/browser) | `clients/openclaw_client.py` | `execute_tool()` |
| 4 | **Session State Sync** with BottleneckBridge | `clients/openclaw_client.py` | `sync_session()` |
| 5 | **Ollama Model Handoff** (local inference fallback) | `clients/openclaw_client.py` | `handoff_to_ollama()` |

**What OpenClaw provides:** Agentic task execution — it can run shell commands, read/write files,
and control a browser. It's the "hands" of the hybrid engine.

**Routing:** OpenClaw is preferred for `shell`, `file`, and `browser` task types.
When OpenClaw is offline, the BottleneckBridge automatically routes to Ollama (#5).

---

### BLACKBOX DESKTOP — Points #6-10

| # | Integration Point | File | Method |
|---|-------------------|------|--------|
| 6 | **IPC Socket Bridge** (Unix socket / named pipe) | `clients/blackbox_client.py` | `send_ipc()` |
| 7 | **Code Completion Passthrough** to hybrid router | `clients/blackbox_client.py` | `get_completion()` |
| 8 | **Context Window Sync** (file tree, open tabs, cursor) | `clients/blackbox_client.py` | `sync_context()` |
| 9 | **Copilot Suggestion Arbitration** (best-of-N) | `clients/blackbox_client.py` | `arbitrate_suggestions()` |
| 10 | **Telemetry Aggregation** for routing intelligence | `clients/blackbox_client.py` | `collect_telemetry()` |

**What BlackBox Desktop provides:** IDE-integrated AI with deep workspace awareness.
It knows your open files, cursor position, and project structure.

**Routing:** BlackBox is preferred for `code_completion` and `code` tasks.
Its telemetry (#10) feeds the BottleneckBridge's routing decisions.

---

### OLLAMA — Points #11-14

| # | Integration Point | File | Method |
|---|-------------------|------|--------|
| 11 | **Local Model Inference** (primary local backend) | `clients/ollama_client.py` | `generate()` / `chat()` |
| 12 | **Model Pull/Management** via hybrid engine CLI | `clients/ollama_client.py` | `pull_model()` / `list_models()` |
| 13 | **Streaming Token Bridge** to CommsHub | `clients/ollama_client.py` | `stream_generate()` |
| 14 | **Embeddings for Semantic Routing** | `clients/ollama_client.py` | `embed()` / `cosine_similarity()` |

**What Ollama provides:** 100% local, private LLM inference. No API keys, no data leaving
your machine. Supports Llama3, Mistral, CodeLlama, Phi-3, DeepSeek-Coder, and more.

**Routing:** Ollama is the universal fallback — if all cloud clients fail, Ollama handles it.
Its embeddings (#14) power the semantic routing in the HybridRouter.

---

### COMET / PERPLEXITY AI BROWSER — Points #15-18

| # | Integration Point | File | Method |
|---|-------------------|------|--------|
| 15 | **Perplexity Search API** (web-grounded answers) | `clients/comet_client.py` | `search()` |
| 16 | **Comet Browser Automation** (CDP/WebDriver bridge) | `clients/comet_client.py` | `browse_url()` / `screenshot_url()` |
| 17 | **Deep Research Passthrough** (streaming) | `clients/comet_client.py` | `deep_research()` |
| 18 | **Context Injection** into hybrid engine window | `clients/comet_client.py` | `_inject_context()` / `build_context_string()` |

**What Comet/Perplexity provides:** Real-time web knowledge. While Ollama knows up to its
training cutoff, Comet knows what happened today. It's the "eyes on the internet."

**Routing:** Comet is exclusively preferred for `web_search`, `deep_research`, and `real_time` tasks.
Its context buffer (#18) is injected into subsequent Ollama reasoning calls.

---

### GITHUB COPILOT + WINDOWS OS WRAPPER — Points #19-22

| # | Integration Point | File | Method |
|---|-------------------|------|--------|
| 19 | **Copilot LSP Bridge** (Language Server Protocol) | `clients/copilot_client.py` | `connect_lsp()` / `get_lsp_completion()` |
| 20 | **Copilot Chat API** (conversational coding) | `clients/copilot_client.py` | `chat()` |
| 21 | **Suggestion Ranking** + arbitration injection | `clients/copilot_client.py` | `rank_suggestions()` |
| 22 | **Windows OS Wrapper** (tray, hotkey, overlay UI) | `clients/copilot_client.py` + `deployment/windows_overlay.py` | `launch_windows_overlay()` |

**What Copilot provides:** GitHub's AI coding assistant with deep code understanding.
The Windows OS wrapper (#22) puts the entire hybrid engine behind a global hotkey
accessible from any application on the desktop.

---

### BOTTLENECK BRIDGE — Point #23

| # | Integration Point | File | Description |
|---|-------------------|------|-------------|
| 23 | **Central Bottleneck Bridge** | `routing/bottleneck.py` | ALL traffic routes through here |

**Architecture:**
- **Priority Queue:** `CRITICAL > HIGH > NORMAL > LOW > BACKGROUND`
- **Circuit Breaker:** Per-client fault isolation (CLOSED → OPEN → HALF_OPEN)
- **Load Balancer:** Routes to best client based on success rate + latency
- **Capability Map:** `code_completion → [copilot, blackbox, ollama]`, etc.
- **Metrics:** Per-client success rate, avg latency, circuit state

---

### HYBRID ROUTER — Point #24

| # | Integration Point | File | Description |
|---|-------------------|------|-------------|
| 24 | **High-Level Hybrid Router** | `routing/router.py` | Pipelines, fan-out, caching |

**Built-in Pipelines:**
```
research_and_code:   Comet search → Ollama reason → Copilot code
local_first_code:    Ollama → BlackBox → Copilot (privacy-first)
deep_analysis:       Perplexity deep research → Ollama → BlackBox summary
multi_agent_fanout:  All agents simultaneously → merge best result
```

---

### COMMS HUB — Point #25

| # | Integration Point | File | Description |
|---|-------------------|------|-------------|
| 25 | **Real-Time Comms Hub** | `comms/hub.py` | Pub/sub, WebSocket, token relay |

**Topics:**
```
task.submitted / task.completed / task.failed
client.online / client.offline
stream.token / stream.done
pipeline.started / pipeline.step / pipeline.done
overlay.command / overlay.response
context.updated / session.created / session.ended
```

---

## DEPLOYMENT GUIDE

### Local Development
```bash
# 1. Start Ollama (required — local inference backbone)
ollama serve
ollama pull llama3:8b

# 2. Set environment variables
export PERPLEXITY_API_KEY=pplx-...
export GITHUB_TOKEN=ghp_...

# 3. Start the hybrid engine API
python hybrid_engine_main.py serve

# 4. Route a task
python hybrid_engine_main.py route "Write a Python function to parse JSON"

# 5. Run a pipeline
python hybrid_engine_main.py pipeline research_and_code "Latest AI models 2026"
```

### Docker Deployment
```yaml
# docker-compose.yml addition:
hybrid-engine:
  build: .
  command: python hybrid_engine_main.py serve
  ports:
    - "8765:8765"
  environment:
    - OLLAMA_URL=http://ollama:11434
    - PERPLEXITY_API_KEY=${PERPLEXITY_API_KEY}
    - GITHUB_TOKEN=${GITHUB_TOKEN}
  depends_on:
    - ollama
```

### Windows Desktop Deployment
```batch
REM Launch with overlay enabled
set ENABLE_OVERLAY=true
python hybrid_engine_main.py serve

REM Or launch overlay standalone
python hybrid_engine/deployment/windows_overlay.py --hotkey ctrl+shift+space
```

### API Endpoints
```
GET  /health          — All client health checks
GET  /status          — Router status, metrics, queue depth
GET  /metrics         — Per-client success rate, latency
GET  /pipelines       — List available pipelines
POST /route           — Route a single task
WS   /ws/comms        — Real-time event stream
GET  /comms/history   — Message history
GET  /comms/stats     — Pub/sub statistics
```

---

## ROUTING DECISION MATRIX

| Task Type | Primary | Secondary | Tertiary | Fallback |
|-----------|---------|-----------|----------|----------|
| `code_completion` | Copilot | BlackBox | Ollama | — |
| `code` | BlackBox | Copilot | OpenClaw | Ollama |
| `shell` | OpenClaw | Ollama | — | — |
| `file` | OpenClaw | BlackBox | — | — |
| `browser` | Comet | OpenClaw | — | — |
| `web_search` | Comet | — | — | Ollama |
| `deep_research` | Comet | Ollama | — | — |
| `reasoning` | Ollama | OpenClaw | Copilot | — |
| `chat` | Copilot | BlackBox | Ollama | — |
| `inference` | Ollama | OpenClaw | BlackBox | Copilot |
| `embeddings` | Ollama | — | — | — |
| `real_time` | Comet | — | — | — |

---

## BRIDGE ARCHITECTURE

```
Ollama ↔ OpenClaw Bridge:
  reason_then_execute()    — Ollama plans → OpenClaw executes
  execute_then_summarize() — OpenClaw runs → Ollama summarizes
  local_tool_call()        — Ollama validates args → OpenClaw executes

Copilot ↔ BlackBox Bridge:
  get_best_completion()    — Both generate → arbitrate winner
  sync_workspace_context() — Push IDE context to both simultaneously
  ranked_chat()            — Both respond → rank and return best

Comet ↔ Ollama Bridge:
  search_and_reason()      — Comet searches → Ollama reasons locally
  stream_grounded_answer() — Comet context → Ollama streams answer
  embed_and_search()       — Ollama embeds → Comet fetches → rank by similarity
  deep_local_research()    — Perplexity deep research → Ollama synthesizes
```

---

## PRIVACY & HYBRID STRATEGY

| Scenario | Route |
|----------|-------|
| Sensitive code (no cloud) | Ollama only (local) |
| Need latest web info | Comet → Ollama (search + local reason) |
| Best code completion | Copilot + BlackBox arbitration |
| Complex agentic task | OpenClaw + Ollama bridge |
| Research + code | Full pipeline: Comet → Ollama → Copilot |
| Offline mode | Ollama only |
| Maximum speed | Fan-out all → first response wins |

---

*Generated by ARK95X Hybrid Engine — Network-95 LLC*
