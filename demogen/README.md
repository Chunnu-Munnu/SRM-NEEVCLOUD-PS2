# DemoGen

DemoGen is an AI-powered interactive walkthrough generator for NeevCloud. Give it a natural-language intent and it will:

- Plan the best UI navigation flow for the goal.
- Crawl the portal with Playwright and capture screenshots.
- Generate step narration, API mappings, and code snippets with Gemini.
- Provide multilingual narration (English, Hindi, Tamil, Telugu).
- Let users click through steps, use voice narration, export PDF, and create share links.

## Project Structure

```
demogen/
+-- backend/
+-- frontend/
```

## Backend Setup (Python 3.11)

1. Clone and enter backend:

```bash
git clone <your-repo-url>
cd demogen/backend
```

2. Create Python 3.11 virtual environment:

```bash
py -3.11 -m venv .venv
```

3. Activate it:

```bash
.\.venv\Scripts\Activate.ps1
python --version
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Install Playwright Chromium:

```bash
playwright install chromium
```

6. Create `.env` in `backend/`:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

7. Start backend:

```bash
uvicorn main:app --reload --port 8000
```

## Frontend Setup

1. Open new terminal:

```bash
cd demogen/frontend
```

2. Install and run:

```bash
npm install
npm run dev
```

3. Open app:

- [http://localhost:5173](http://localhost:5173)

## API Endpoints

- `POST /generate` - Generates a complete walkthrough.
- `POST /export/link` - Saves demo steps to a local share file and returns URL.
- `GET /share/{share_id}` - Fetches shared demo JSON.
- `POST /export/pdf` - Exports walkthrough as PDF.

## Troubleshooting

### NeevCloud Requires Login

If portal pages redirect to login, keep the visible browser open and log in manually once. Continue generation afterward so the crawler can capture authenticated pages. If login still blocks navigation, use fallback screenshot mode by relying on captured login-page steps and generated fallback narration.

### Playwright Timeouts

If pages load slowly:

- Reduce planned steps by using a more focused prompt.
- Increase timeouts in `backend/crawler.py` (`goto` and `wait_for_load_state`).
- Retry when network conditions are stable.

### Gemini API Limits

If you hit rate limits:

- Add or increase delay between narration calls in `backend/main.py` (for example, `await asyncio.sleep(1)`).
- Retry after a short cooldown.
- Keep intent concise to reduce total step count.

## Notes

- Browser automation runs in non-headless mode (`headless=False`) for live demo visibility.
- Screenshots are stored in `backend/screenshots/` with session-prefixed names to avoid collisions.
- No database is used; sessions are kept in memory and share exports are file-based.

### Manual Browser Mode For NeevCloud

If Cloudflare keeps blocking automated browser launches, use a normal Edge session and let DemoGen attach to it.

1. Close every Edge window.
2. Start Edge manually with remote debugging:

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="D:\Amogh Projects\SRM-HACK\demogen\backend\manual_edge_profile"
```

3. In that Edge window, open `https://console.ai.neevcloud.com/login`, solve Cloudflare, and log in fully.
4. In `backend/.env`, set:

```env
BROWSER_CDP_URL=http://127.0.0.1:9222
```

5. Restart backend and run DemoGen again. The crawler will attach to your existing verified browser session instead of launching a fresh one.

### Manual Capture Folder Mode

If NeevCloud keeps blocking automated browsing, DemoGen can generate the walkthrough from screenshots you capture yourself in a normal browser session.

1. Open NeevCloud in your own Edge window and log in normally.
2. Capture each important page as an image.
3. Save the images into `backend/manual_capture/` using an ordered naming scheme such as:
   - `01_dashboard.png`
   - `02_instances.png`
   - `03_launch_form.png`
   - `04_pricing_review.png`
4. In `backend/.env`, set:

```env
PREFER_MANUAL_CAPTURES=true
```

5. Start the backend and run DemoGen. It will reuse those screenshots and still generate narration, API mapping, multilingual text, PDF export, and the walkthrough UI.
