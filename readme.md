# semantix

grammarly but not grammarly

## run

```sh
uvicorn backend.main:app --reload --port 8000 --timeout-graceful-shutdown 3
```

starts vite automatically. open http://localhost:5173

## config

`semantix.config.json` (auto-created, gitignored):

```json
{
  "base_url": "http://localhost:11434",
  "api_style": "auto", // or 'ollama'/'openai'
  "api_key": "",
  "analyzer_model": "gemma-e4b:latest",
  "translate_model": "gemma4:26b"
}
```

## tests

```sh
python -m pytest backend/tests -q
```
