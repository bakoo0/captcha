# Adaptive CAPTCHA Real Widget

This is a real deployable version of the adaptive CAPTCHA project.

## Architecture

Browser website -> JavaScript widget -> FastAPI backend -> trained ML model -> MongoDB / runtime CSV -> adaptive CAPTCHA decision.

## Local run

```bash
python -m venv .venv
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Health check:

```text
http://127.0.0.1:8000/api/health
```

## MongoDB Atlas

Create `.env` from `.env.example` and add:

```env
MONGO_URI=mongodb+srv://USER:PASSWORD@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB=adaptive_captcha
```

If `MONGO_URI` is empty, the app still works and saves runtime data into `.runtime/events.csv` and `.runtime/sessions.csv`.

## Widget integration on another website

```html
<div id="behavior-captcha-container"></div>

<script
  src="https://YOUR-DOMAIN.com/widget/behavior-captcha-widget.js"
  data-endpoint="https://YOUR-DOMAIN.com"
  data-site-key="external-site">
</script>
```

## Deploy

The project includes `Dockerfile` and `render.yaml`, so it can be deployed as a Docker web service on Render.

Required Render environment variable for real storage:

```env
MONGO_URI=mongodb+srv://USER:PASSWORD@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB=adaptive_captcha
```
