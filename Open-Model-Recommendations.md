# Open Model Recommendations for Limited Hardware

**Source context:** Recommendations tailored to a laptop with the following specs:
- Device: DESKTOP-M034EJG
- Processor: Intel Core i5-7200U @ 2.50 GHz (2 cores / 4 threads, Kaby Lake)
- RAM: 8.00 GB (7.44 GB usable)
- Storage: 238 GB SSD
- Graphics: Intel HD Graphics 620 (CPU-only inference required)

## Practical Hardware Ceiling

| Model size / quant | Fits on this PC? | Verdict | Approx. size (Q4) | Primary role / notes |
|--------------------|------------------|---------|-------------------|----------------------|
| 0.5–1.5B | Excellent | Fastest | ~1 GB or less | Everyday light tasks |
| 2–4B | Good | Sweet spot | 1.5–3.2 GB | Best balance of capability & speed |
| 7–8B Q4 | Possible | Slow but usable | ~4–5 GB | Memory pressure; close everything else |
| 12–14B Q4 | Not recommended | RAM bottleneck | ~7–8 GB+ | Uncomfortable / thrashing |
| 30B+ / 70B | No | Don't bother | Far too large | Impossible |

## Recommended Models

| Model | Size (approx.) | Role | Why it fits |
|-------|----------------|------|-------------|
| **Qwen3.5 2B (Q4_K_M)** | ~1.5 GB | Everyday assistant | Fastest comfortable option; good for general Q&A, light coding, SQL, Python, summarisation, classification, lightweight RAG, local agents |
| **Phi-4-mini (Q4_K_M)** | ~2.4 GB | Reasoning / coding | Smartest model that still fits well; strong on Python/SQL/code reasoning and data-analysis explanations |
| **Gemma 3 4B (Q4)** | ~3.2 GB | Documents / general AI | Viable upper end; writing, summarisation, document analysis, basic coding, RAG |

### Setup Recommendation
Install **Ollama + Open WebUI** (or `llama.cpp` for finer control of quantisation, threads, and context).

Example commands:
```bash
ollama run qwen3.5:2b
# or
ollama run phi4-mini
```

Keep only one model loaded at a time. Expect “usable local assistant” speed rather than ChatGPT-level latency, especially on ≥4B models.

**Final pick:**
- **Phi-4-mini Q4_K_M** if quality/reasoning matters most.
- **Qwen3.5 2B Q4_K_M** if speed matters most.
A 4B model is roughly the practical upper limit; avoid 7B/8B except for experimentation with everything else closed.

---

## Why These Models Work Well for an End-to-End LLM-Powered Customer Intelligence Pipeline

### 1. Hardware reality forces small, efficient models — and that is a feature, not a bug
Customer-intelligence pipelines frequently run on modest developer or analyst laptops rather than GPU servers. The i5-7200U + 8 GB RAM constraint means only models ≤ ~3–4 GB in Q4 quantisation leave enough headroom for the OS, the inference engine (Ollama/llama.cpp), the KV cache, and concurrent tools (Pandas, a local vector store, a web UI). Qwen3.5 2B and Phi-4-mini sit comfortably inside that envelope. Larger models would force constant swapping or force the user to close every other application, destroying the interactive “analyse this dataset” workflow that a customer-intelligence system needs.

### 2. The recommended models excel at the exact tasks a customer-intelligence pipeline requires
Typical stages in such a pipeline include:
- Natural-language querying of customer data (“Show me the top complaints about shipping last quarter”).
- Code generation/execution for Pandas/Polars/SQL analysis.
- Summarisation and classification of free-text reviews or support tickets.
- Lightweight RAG over internal documents or historical customer interactions.
- Simple agentic loops that call tools (run a query, plot a chart, write a short insight).

Phi-4-mini is repeatedly noted for strong Python/SQL/code reasoning—precisely the skill needed when the LLM must generate and interpret analysis code while Python actually performs the computation. Qwen3.5 2B is fast enough for interactive use and still competent at summarisation, classification, and light RAG. Gemma 3 4B adds stronger document-handling capability when the pipeline needs to ingest longer customer feedback or policy documents. None of these models need to be “giant general-purpose LLMs”; the heavy numerical work stays in Pandas/Polars, so the LLM only has to be good at orchestration and explanation.

### 3. Local-first, privacy-preserving architecture aligns with customer data sensitivity
Customer intelligence pipelines routinely handle PII, order history, and support transcripts. Running the LLM entirely on-device (Ollama or llama.cpp) keeps data inside the organisation’s boundary. The recommended approach turns the laptop into a “small local data-analysis AI server” with Open WebUI as the front-end and the LLM generating/executing analysis code. That pattern maps directly onto an end-to-end customer-intelligence system: CSV/Excel → Pandas → LLM natural-language interface → actionable insights, all without sending customer data to external APIs.

### 4. Quantisation + selective loading keep the system practical day-to-day
Because the three recommended models total only a few gigabytes, a developer can keep them on disk and load only the one needed for the current stage of the pipeline (fast Qwen for quick triage, Phi-4-mini for deeper reasoning, Gemma for document-heavy tasks). Context windows remain usable without exhausting the 7.44 GB of available RAM. This is far more practical for iterative customer-analysis work than attempting to run a single oversized model that constantly fights the OS for memory.

### 5. Extensibility for a full pipeline
Once the core LLM is running locally, the same stack can be extended with:
- A local vector store for RAG over historical customer interactions.
- Tool-calling so the model can invoke Pandas, SQL, or simple statistical functions.
- A lightweight agent loop for multi-step analysis (“segment customers → identify churn drivers → draft a summary”).

All of these remain feasible on the described hardware precisely because the base models stay small.

In short, Qwen3.5 2B, Phi-4-mini, and (at the upper limit) Gemma 3 4B are not compromises; they are the models that actually make a usable, private, end-to-end LLM-powered customer-intelligence pipeline realistic on everyday analyst hardware.
