# Setting up Ollama for BaseLayer (100% Free, Local AI)

BaseLayer supports [Ollama](https://ollama.com) out of the box. Running Ollama allows you to use SocratiQ tutoring, code discussions, drawing evaluations, and the agentic course builder **100% locally with zero API keys, no subscriptions, and complete privacy**.

---

## 1. Quick Start: 3 Steps

If you already know the basics, here is the fastest way to get running:

1. **Install Ollama**
   - **macOS:** `brew install ollama` (or download from [ollama.com/download](https://ollama.com/download))
   - **Linux:** `curl -fsSL https://ollama.com/install.sh | sh`
   - **Windows:** Download the installer from [ollama.com/download](https://ollama.com/download)
2. **Pull a Model**
   ```bash
   ollama pull llama3.2
   ```
   *(Or `ollama pull qwen2.5-coder:7b` for optimal coding performance)*
3. **Run Ollama & Connect BaseLayer**
   ```bash
   ollama serve
   ```
   Open BaseLayer Web Studio at [http://localhost:5173](http://localhost:5173), go to **Learning Guide** (or user menu) &rarr; **AI Features**, choose **Ollama**, and click **Test connection & Activate Ollama**.

---

## 2. Installation by Operating System

### macOS

You have two easy options:

- **Homebrew:**
  ```bash
  brew install ollama
  ```
- **Desktop Application:**
  Download and run the installer from [ollama.com/download](https://ollama.com/download). The desktop app automatically adds Ollama to your menu bar and runs the local server in the background on port `11434`.

Apple Silicon (M1/M2/M3/M4) Macs will automatically utilize the unified memory Metal GPU acceleration for fast inference.

### Linux

Install using the official install script:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

The script configures Ollama as a `systemd` service that starts automatically on boot.

- **Check service status:**
  ```bash
  systemctl status ollama
  ```
- **Start or restart manually:**
  ```bash
  sudo systemctl start ollama
  ```

Ollama automatically detects NVIDIA GPUs (CUDA) and AMD GPUs (ROCm).

### Windows

1. Download the Windows installer (`OllamaSetup.exe`) from [ollama.com/download](https://ollama.com/download).
2. Run the installer and launch the Ollama app from your Start Menu. It will run in your system tray.
3. Alternatively, if you develop inside **WSL2** (Windows Subsystem for Linux), you can install Linux Ollama inside your WSL distribution to share your NVIDIA GPU directly.

---

## 3. Recommended Models for BaseLayer

Ollama hosts thousands of open-source models. For BaseLayer exercises and tutoring, we recommend the following models:

| Model | Pull Command | Min RAM / VRAM | Best For |
|---|---|---|---|
| **Llama 3.2 (3B)** *(Default)* | `ollama pull llama3.2` | ~4 GB | Laptops, standard CPUs, fast SocratiQ tutoring & reflections |
| **Qwen 2.5 Coder (7B)** | `ollama pull qwen2.5-coder:7b` | ~8 GB | Dedicated coding exercises, unit test validation, course generation |
| **Llama 3.3 (70B)** | `ollama pull llama3.3` | ~32 GB+ | Workstations or high-end GPUs needing complex architectural reasoning |

### Why Qwen 2.5 Coder 7B?
If your computer has 8 GB or more of free RAM/VRAM, `qwen2.5-coder:7b` is strongly recommended for BaseLayer. It excels at Python syntax, unit test debugging, and generates higher-fidelity micro-lessons in the course builder.

---

## 4. Starting and Verifying Ollama

If you run Ollama from the CLI (or if the desktop app is not running), start the server:

```bash
ollama serve
```

By default, Ollama listens on `http://localhost:11434`.

### Verify that Ollama is reachable

Open a new terminal and run:

```bash
curl http://localhost:11434/
```

You should see:

```text
Ollama is running
```

To see which models you have downloaded locally:

```bash
ollama list
```

---

## 5. Configuring BaseLayer

### Option A: Via the Web Studio UI (Recommended)

1. Launch BaseLayer with `./dev.sh` and visit [http://localhost:5173](http://localhost:5173).
2. Open the **Learning Guide** (or User menu &rarr; **Local Studio**).
3. Select the **AI Features** tab.
4. Under "Free to start", select **Ollama**.
5. Pick your preferred model (`llama3.2` or `qwen2.5-coder:7b`).
6. Click **Test connection & Activate Ollama**. BaseLayer will ping your local endpoint, verify reachability, activate the provider in memory, and save the settings to your `.env` file.

### Option B: Via `.env`

You can also configure Ollama directly in your `.env` file at the root of the BaseLayer repository:

```bash
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
LLM_API_BASE=http://localhost:11434/v1
```

For coding with Qwen:

```bash
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5-coder:7b
LLM_API_BASE=http://localhost:11434/v1
```

---

## 6. Docker & Remote Network Configuration

When running BaseLayer inside Docker containers (`./docker-dev.sh`) or hosting Ollama on a different machine/VM, follow these network configuration tips.

### Enabling CORS (`OLLAMA_ORIGINS`)

By default, Ollama only permits requests from localhost web origins. If you run into CORS issues or connect from browser clients on custom hostnames, set `OLLAMA_ORIGINS="*"`.

#### On macOS
Run in your terminal:
```bash
launchctl setenv OLLAMA_ORIGINS "*"
```
Then restart the Ollama desktop app.

#### On Linux (systemd)
Edit the systemd service configuration:
```bash
sudo systemctl edit ollama.service
```
Add the following block:
```ini
[Service]
Environment="OLLAMA_ORIGINS=*"
Environment="OLLAMA_HOST=0.0.0.0:11434"
```
Reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

#### On Windows
1. Open Windows Search &rarr; **Edit system environment variables**.
2. Click **Environment Variables...**.
3. Under User or System variables, click **New...**:
   - Variable name: `OLLAMA_ORIGINS`
   - Variable value: `*`
4. If exposing across the local network, also add:
   - Variable name: `OLLAMA_HOST`
   - Variable value: `0.0.0.0:11434`
5. Right-click the Ollama icon in the taskbar notification tray and choose **Exit**, then reopen Ollama.

### Running BaseLayer in Docker Compose with Host Ollama

If BaseLayer is containerized via `./docker-dev.sh` and Ollama is running on your host machine:

1. Ensure Ollama listens on all interfaces by setting `OLLAMA_HOST=0.0.0.0:11434`.
2. In BaseLayer's `.env`, configure `LLM_API_BASE` to reach the host gateway:
   ```bash
   LLM_PROVIDER=ollama
   LLM_MODEL=llama3.2
   LLM_API_BASE=http://host.docker.internal:11434/v1
   ```

---

## 7. Troubleshooting

### "Could not reach Ollama at http://localhost:11434"
- Make sure the Ollama server is running:
  - macOS/Windows: Ensure the Ollama app is open in your menu bar / taskbar.
  - Linux: Run `ollama serve` or `sudo systemctl start ollama`.
- Test reachability from your shell: `curl http://localhost:11434/`.
- If running on a custom port, make sure the port in BaseLayer's `API Base URL` matches (e.g. `http://localhost:11435/v1`).

### "Model not found" or "Ollama model not found"
- You must pull the model before using it:
  ```bash
  ollama pull llama3.2
  ```
- Run `ollama list` to confirm the exact model tag matches what you entered in BaseLayer (e.g. `llama3.2` or `qwen2.5-coder:7b`).

### Tutor responses are slow or timing out
- If you have an integrated GPU or older CPU, larger models (like 70B) will swap into system RAM and run very slowly.
- Switch to `llama3.2` (3B parameters) which is designed for fast, lightweight inference.
- Check active GPU offloading by running `ollama ps` while generating a response.

### Connection Refused inside Docker
- Use `http://host.docker.internal:11434/v1` instead of `localhost`.
- Set `OLLAMA_HOST=0.0.0.0:11434` on the machine running Ollama so it accepts connections from the Docker bridge interface.
