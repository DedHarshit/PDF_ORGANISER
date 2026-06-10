# PDF Organiser

An AI-powered desktop app that automatically sorts PDF files into folders using GPT-4o. Drop a PDF into the inbox folder and it gets classified and moved — no manual sorting needed.

---

## How It Works

```
inbox/  →  GPT-4o classifies content  →  organised/Category/Subcategory/
```

PDFs are read, sent to the AI for classification, and moved into a matching folder structure like `Finance/Tax_Returns` or `Exams/Civil_Services`. Failed files go to `organised/_errors/`.

---

## Requirements

- Python 3.10+
- A GitHub Marketplace API token (for GPT-4o access)

---

## Installation

**1. Clone the repo**
```bash
git clone https://github.com/DedHarshit/PDF_ORGANISER.git
cd PDF_ORGANISER
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
pip install flask flask-cors pywebview pystray
```

**3. Create a `.env` file**
```env
GITHUB_TOKEN=your_github_marketplace_token_here
WATCH_DIR=./inbox
OUTPUT_DIR=./organised
LOG_LEVEL=INFO
```

> Get your token from [GitHub Marketplace Models](https://github.com/marketplace/models)

---

## Running the App

### Desktop App (recommended)
```bash
python desktop.py
```
Opens a desktop window with the full UI. Minimising hides it to the system tray.

### CLI / Headless Mode
```bash
python main.py
```
Runs the watcher directly in the terminal. Watches the inbox folder and processes PDFs as they arrive. Press `Ctrl+C` to stop.

### API Only
```bash
python api.py
```
Starts the Flask API at `http://localhost:5000`. Useful for testing or building your own frontend.

---

## Using the Desktop App

### Step 1 — Set up folders
On first launch, set your **Watch folder** (where you drop PDFs) and **Output folder** (where sorted PDFs go). These are saved automatically.

### Step 2 — Add your GitHub token
Enter your GitHub Marketplace token in the Settings tab. It's saved to your `.env` file.

### Step 3 — Sort PDFs

**One-time sweep** — click **Run Organiser** to process all PDFs currently in the inbox. Progress is shown in real time.

**Auto Watcher** — click **Start Watcher** to monitor the inbox continuously. Any new PDF dropped in gets sorted automatically. A tray notification appears for each file.

### Step 4 — Check results
Sorted files appear in your output folder, organised like:
```
organised/
├── Finance/
│   └── Tax_Returns/
│       └── invoice_2024.pdf
├── Exams/
│   └── Civil_Services/
│       └── mock_paper.pdf
└── _errors/
    └── extraction_error/
        └── corrupted_file.pdf
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | App status, watcher state, file count |
| GET | `/api/config` | Current configuration |
| POST | `/api/config` | Update configuration |
| GET | `/api/scan` | List PDFs in watch folder |
| GET/POST | `/api/run` | Run organiser (SSE stream) |
| POST | `/api/watcher/start` | Start background watcher |
| GET/POST | `/api/watcher/sweep` | Sweep existing files (SSE stream) |
| GET | `/api/watcher/events` | Live watcher events (SSE stream) |
| POST | `/api/watcher/stop` | Stop background watcher |
| GET | `/api/log` | Last N lines of log file |

---

## File Actions

| Mode | Behaviour |
|------|-----------|
| `move` | Moves PDF to organised folder (default) |
| `copy` | Copies PDF, keeps original in inbox |
| `dry_run` | Shows where files would go, moves nothing |

Set the file action in the Settings tab or via `/api/config`.

---

## Project Structure

```
PDF_ORGANISER/
├── main.py          # CLI entry point
├── desktop.py       # Desktop app (PyWebView + system tray)
├── api.py           # Flask REST API + SSE endpoints
├── classifier.py    # PDF extraction + GPT-4o classification
├── organiser.py     # File move/copy logic
├── watcher.py       # Watchdog filesystem monitor
├── pdf_organiser.html  # Frontend UI
├── style.css        # Frontend styles
├── app.js           # Frontend logic
├── requirements.txt
└── .env             # Your tokens and paths (not committed)
```

---

## Troubleshooting

**"Missing required environment variable: GITHUB_TOKEN"**
Add your token to the `.env` file or enter it in the Settings tab.

**PDF moved to `_errors/extraction_error`**
The PDF may be corrupted, password-protected, or a scanned image with no embedded text/images.

**PDF moved to `_errors/api_error`**
The GitHub API call failed after 3 retries. Check your token is valid and you have API quota remaining.

**Watcher not detecting new files**
Make sure the Watch folder path in Settings matches where you're dropping files.

