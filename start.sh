#!/usr/bin/env sh
# Arif Visual Answers: one-command start for macOS and Linux (also works in Git Bash on Windows).
# Installs what the app needs (first run only), builds the web page, starts the server
# on http://localhost:8000 and opens it in the browser. Press Ctrl+C to stop Arif.
set -e
cd "$(dirname "$0")"
export PATH="$PATH:$HOME/.local/bin:$HOME/.cargo/bin"
export PYTHONUTF8=1

if ! command -v uv >/dev/null 2>&1; then
  echo "[!] 'uv' is not installed. See step 2 of the guide: docs/Arif-Visual-Answers-Guide.pdf"; exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "[!] Node.js is not installed. See step 2 of the guide: docs/Arif-Visual-Answers-Guide.pdf"; exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created the settings file .env"
fi

# Live mode when .env has an API key, otherwise the offline demo (recorded answers).
MOCK_LLM=1
if grep -Eq '^(GROQ|GEMINI)_API_KEY=[^ #]' .env; then MOCK_LLM=0; fi
export MOCK_LLM

echo; echo "[1/3] Installing the server part (the first run takes a few minutes)..."
(cd backend && uv sync)

echo; echo "[2/3] Building the web page..."
(cd frontend && { [ -d node_modules ] || npm ci; } && npm run build)

echo
if [ "$MOCK_LLM" = 1 ]; then
  echo "[3/3] Starting Arif in OFFLINE DEMO mode: no API key in .env."
  echo "      Real answers only for the sample PDFs in fixtures/pdfs. Add a key for your own PDFs."
else
  echo "[3/3] Starting Arif in LIVE mode with the API key from .env."
fi
echo "      Arif opens in your browser at http://localhost:8000. Press Ctrl+C to stop."
echo

open_browser() {
  i=0
  while [ $i -lt 90 ]; do
    if curl -fs http://localhost:8000/healthz >/dev/null 2>&1; then
      if command -v open >/dev/null 2>&1; then open http://localhost:8000
      elif command -v xdg-open >/dev/null 2>&1; then xdg-open http://localhost:8000
      elif command -v cmd.exe >/dev/null 2>&1; then cmd.exe /c start http://localhost:8000
      fi
      return
    fi
    i=$((i + 1)); sleep 1
  done
}
open_browser &

cd backend
exec uv run uvicorn app.main:app --port 8000
