# Local AI Configuration and Learning Modalities

This document explains the local onboarding workflow, the provider-agnostic LLM setup, and the learning modalities supported in BaseLayer.

## 1. Overview

When running BaseLayer locally, learners and educators need:
1. Optional AI features (SocratiQ, drawing grades, course generation) via **any OpenAI-compatible provider**.
2. An overview of the studio modalities.
3. Guidance on authoring file-based courses.

Gemini is a convenient free cloud option (Google AI Studio). It is not required. Coding and spreadsheets work with no LLM at all.

## 2. AI Setup

Supported providers: **Ollama** (local, 100% free, no key — see the [Ollama Setup Guide](ollama_setup.md)), **Gemini** (free AI Studio key), **Groq** (free tier), **LM Studio** (local, no key), **OpenAI**, **OpenRouter**, and **custom** OpenAI-compatible endpoints.

### A. Web Studio (Local Welcome → AI Features)
- `GET /ai/status` reports the current provider and the full provider list.
- The modal shows provider cards. Gemini keeps the **Get a free key from Google AI Studio** link.
- `POST /ai/configure-key` is local-only (`localhost` or `ALLOW_LOCAL_WELCOME=true`) and writes `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` / `LLM_API_BASE` to `.env`. Gemini also writes `GEMINI_API_KEY` so older setups keep working.
- Skip the tab to code without AI.

### B. `./dev.sh`
Prints that AI is optional if nothing is configured. It does not block on a Gemini key.

### C. `.env` examples

```bash
# Free Gemini key from https://aistudio.google.com/app/apikey
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite
LLM_API_KEY=your_gemini_key

# Local, no key
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
```

`GEMINI_API_KEY` and `OPENAI_API_KEY` remain valid aliases.

## 3. Backend Endpoints

### `GET /ai/status`

```json
{
  "configured": true,
  "has_key": true,
  "provider": "gemini",
  "model": "gemini-3.5-flash-lite",
  "api_base": "https://generativelanguage.googleapis.com/v1beta/openai/",
  "providers": []
}
```

### `POST /ai/configure-key`

Local-only.

```json
{
  "provider": "gemini",
  "api_key": "your-gemini-api-key",
  "model": "gemini-3.5-flash-lite"
}
```

## 4. Learning Modalities in BaseLayer

BaseLayer supports three interactive modalities to accommodate different cognitive styles:

### 1. Code Execution Studio
- **Editor**: Monaco Editor with full syntax highlighting, indentation, and code completion.
- **Languages**: Multi-language support for Python and Rust.
- **Sandboxing**: Runs code inside isolated Docker containers (local `sandbox-runner`) or serverless Modal Sandboxes.
- **Testing**: Automated unit test assertions execute on submission, capturing stdout and stderr with structured error reporting.
- **Solution Verification**: Reference solutions (`solution.py` / `solution.rs`) can be reviewed when configured.

### 2. Spreadsheet Workspaces (Tensor & Matrix Intuition)
- **Integration**: Embedded Google Sheets in the right-hand split pane.
- **Pedagogical Goal**: Developing mechanical, spatial mental models for matrix operations before writing algorithmic code.
- **Capabilities**: Hands-on experimentation with matrix multiplication (`MMULT`), vector broadcasting, and array formula manipulation (`ARRAYFORMULA`).
- **Configuration**: Declared via `metadata.json` specifying `google_sheet_id` and optional `copy_on_open`.

### 3. Hand-Drawn Visual Verification
- **Integration**: HTML5 canvas drawing toolbar overlaid onto architectural diagrams (`question.png`).
- **Tools**: Pencil, eraser, stroke width slider, color picker, undo, and clear canvas.
- **Multimodal AI Grading**: Submissions send the background diagram, the student sketch, and optional reference solution (`solution.png`) to the configured vision model.
- **Evaluation**: The model evaluates visual intent, connections, and data flow pathways rather than pixel-perfect drawing accuracy.

## 5. Customizing Your Own Learning

BaseLayer is built on a transparent file-based course engine. Learners and teachers can create custom lessons and full courses without database migrations or admin panels:

```text
courses/
└── your-course-slug/
    ├── README.md               # Course overview
    └── lesson-01-topic/
        ├── README.md           # Instructions for the left panel
        ├── main.py             # Starter code for the editor (or main.rs)
        ├── test.py             # Automated unit tests (or test.rs)
        └── solution.py         # (Optional) Reference solution
```

For spreadsheets or drawing exercises, add `metadata.json`:
- Spreadsheet: `{"exercise_type": "spreadsheet", "google_sheet_id": "YOUR_SHEET_ID"}`
- Hand Drawing: `{"exercise_type": "drawing"}` with `question.png`.

The backend scans the `courses/` directory dynamically, so new or edited content appears immediately upon page refresh.

## 6. Accessing the Guide at Any Time

Learners can revisit the onboarding guide and AI settings at any time by clicking the "Learning Guide" button in the top navigation bar on both the Courses overview page and the individual coding workspaces.
