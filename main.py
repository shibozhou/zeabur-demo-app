import asyncio
import logging
import os
import sys

import httpx
from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("checkout")

app = FastAPI()
_counter = 0


def compute_total(cart: dict) -> float:
    subtotal = sum(item["price"] * item["qty"] for item in cart["items"])
    return subtotal + cart["tax"]


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/work")
def work():
    global _counter
    _counter += 1
    cart = {
        "items": [{"price": 19.99, "qty": 2}, {"price": 4.50, "qty": 1}],
        "tax": 3.45,
    }
    total = compute_total(cart)
    log.info("checkout request %d total=%.2f", _counter, total)
    return {"request_id": _counter, "total": total}


async def self_tick():
    port = int(os.environ.get("PORT", "8080"))
    url = f"http://127.0.0.1:{port}/work"
    await asyncio.sleep(2)
    async with httpx.AsyncClient(timeout=2.0) as client:
        while True:
            try:
                await client.get(url)
            except Exception as e:
                log.warning("self-tick failed: %s", e)
            await asyncio.sleep(1)


@app.on_event("startup")
async def startup():
    asyncio.create_task(self_tick())
    log.info("checkout service ready (self-tick @ 1Hz)")
