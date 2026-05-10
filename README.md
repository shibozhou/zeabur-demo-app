# sentinel-demo-app

Tiny FastAPI service used to demo the **Sentinel** Zeabur agent skill.

- `main` branch: clean. `/work` always returns 200.
- `feature/checkout-v2` branch: every third `/work` request raises `KeyError: 'tax_total'`.

A startup task hits `/work` once per second so an external load generator isn't needed — the app produces its own error rate.

Run locally:

```
pip install -r requirements.txt
uvicorn main:app --port 8080
```
