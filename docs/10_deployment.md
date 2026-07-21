# Deployment

## Local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Start the REST API in a second terminal when API testing is needed:

```bash
source .venv/bin/activate
uvicorn api:app --reload
```

Open `http://127.0.0.1:8000/docs` for Swagger or call `http://127.0.0.1:8000/health` with a browser or `curl`.

The default configuration uses local demo mode. To enable an OpenAI-compatible API, set the key, model, base URL, and `DEMO_MODE=false` in `.env`.

## Optional Streamlit Cloud

1. Push the repository without `.env` or `gearlead.db`.
2. Create a Streamlit Community Cloud app with `app.py` as the entry point.
3. Keep `DEMO_MODE=true`, or add API secrets in the platform secret manager.
4. Verify that CSV seed files and assets are included.

## Pre-deployment Checklist

- Run `pytest`.
- Run the 25-case evaluation.
- Search for API keys and local paths.
- Confirm generated replies retain the review notice.
- Confirm no real buyer PII is in the repository.
- Confirm runtime database files are ignored.
