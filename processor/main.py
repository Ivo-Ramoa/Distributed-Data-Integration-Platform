import os, time, csv, io, threading, uuid
from datetime import datetime
import requests
import boto3
from botocore.client import Config
from fastapi import FastAPI, Request
import uvicorn

S3_ENDPOINT = (os.getenv("SUPABASE_S3_ENDPOINT") or "").rstrip("/")
S3_REGION   = os.getenv("SUPABASE_S3_REGION")
S3_ACCESS   = os.getenv("SUPABASE_S3_ACCESS_KEY")
S3_SECRET   = os.getenv("SUPABASE_S3_SECRET_KEY")
BUCKET      = os.getenv("SUPABASE_BUCKET_NAME")

POLL_SECONDS   = int(os.getenv("PROCESSOR_POLL_SECONDS", "10"))
WEBHOOK_PORT   = int(os.getenv("PROCESSOR_WEBHOOK_PORT", "8089"))
MAPPER_VERSION = os.getenv("MAPPER_VERSION", "v1")
XML_SERVICE_URL = os.getenv("XML_SERVICE_URL", "http://xml-service:3000/ingest")

# Provider externo (neste exemplo: stooq)
EXTERNAL_API_PROVIDER = (os.getenv("EXTERNAL_API_PROVIDER") or "stooq").lower()

# S3 client (Supabase S3 costuma precisar addressing_style=path)
s3 = boto3.client(
    "s3",
    region_name=S3_REGION,
    aws_access_key_id=S3_ACCESS,
    aws_secret_access_key=S3_SECRET,
    endpoint_url=S3_ENDPOINT,
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)

app = FastAPI()
pending = {}  # request_id -> incoming_key

# cache simples para não chamar API externa a cada linha
# symbol -> (ts_epoch, avg30d, max6m)
_enrich_cache = {}

CACHE_TTL_SECONDS = 60 * 10  # 10 min


@app.post("/webhook/xml")
async def webhook_xml(req: Request):
    body = await req.json()
    request_id = body.get("request_id")
    status = body.get("status")
    doc_id = body.get("doc_id")

    print("WEBHOOK RECEIVED:", body)

    if request_id in pending and status == "OK":
        key = pending.pop(request_id)
        try:
            s3.delete_object(Bucket=BUCKET, Key=key)
            print(f"Deleted incoming: {key} (doc_id={doc_id})")
        except Exception as e:
            print("Delete failed:", e)

    return {"ok": True}


def list_incoming():
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix="incoming/")
    return [
        o["Key"]
        for o in resp.get("Contents", [])
        if o["Key"].endswith(".csv") and not o["Key"].endswith("/.keep")
    ]


def download_text(key: str) -> str:
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return obj["Body"].read().decode("utf-8", errors="replace")


def upload_text(key: str, content: str):
    s3.put_object(Bucket=BUCKET, Key=key, Body=content.encode("utf-8"))


# -----------------------------
# API externa: Stooq (histórico diário via CSV)
# Ex: https://stooq.com/q/d/l/?s=aapl.us&i=d
# -----------------------------
def _stooq_symbol(sym: str) -> str:
    s = (sym or "").strip().lower()
    if not s:
        return s
    # Se já tiver .us / .de / etc, mantém.
    if "." in s:
        return s
    # Para tickers tipo AAPL/TSLA, o mais comum é .us
    return f"{s}.us"


def _fetch_stooq_history_close(symbol: str):
    s = _stooq_symbol(symbol)
    if not s:
        return []

    url = f"https://stooq.com/q/d/l/?s={s}&i=d"
    r = requests.get(url, timeout=20)
    r.raise_for_status()

    # CSV com colunas: Date,Open,High,Low,Close,Volume
    rows = []
    reader = csv.DictReader(io.StringIO(r.text))
    for row in reader:
        try:
            c = float(row.get("Close") or "")
            # ignora valores inválidos
            if c > 0:
                rows.append(c)
        except Exception:
            continue

    return rows


def _compute_avg30d_max6m_from_closes(closes: list[float]):
    # 30 dias úteis ~ 30 registos
    last30 = closes[-30:] if len(closes) >= 30 else closes[:]
    # 6 meses úteis ~ 126; usamos 180 para margem
    last6m = closes[-180:] if len(closes) >= 180 else closes[:]

    if not last30 or not last6m:
        return None, None

    avg30 = sum(last30) / len(last30)
    max6m = max(last6m)
    return avg30, max6m


def _fallback_enrich(price: float):
    # fallback igual ao teu (não rebenta pipeline)
    return round(price * 0.98, 2), round(price * 1.05, 2)


def _external_enrich(symbol: str, price: float):
    """
    Devolve (avg30d, max6m) reais se possível.
    Se falhar, devolve fallback.
    """
    now = time.time()
    sym_key = (symbol or "").strip().upper()

    # cache
    if sym_key in _enrich_cache:
        ts, a, m = _enrich_cache[sym_key]
        if now - ts < CACHE_TTL_SECONDS:
            return a, m

    try:
        if EXTERNAL_API_PROVIDER == "stooq":
            closes = _fetch_stooq_history_close(symbol)
            avg30, max6m = _compute_avg30d_max6m_from_closes(closes)
            if avg30 is None or max6m is None:
                raise RuntimeError("Not enough data from provider")
            avg30 = round(avg30, 2)
            max6m = round(max6m, 2)
        else:
            # se um dia quiseres trocar provider sem partir tudo
            raise RuntimeError(f"Unknown provider: {EXTERNAL_API_PROVIDER}")

        _enrich_cache[sym_key] = (now, avg30, max6m)
        return avg30, max6m

    except Exception as e:
        print(f"External API enrich failed for {symbol}: {e}")
        avg30, max6m = _fallback_enrich(price)
        _enrich_cache[sym_key] = (now, avg30, max6m)
        return avg30, max6m


def enrich_row(mapped: dict) -> dict:
    # Agora com API externa real + fallback
    price = float(mapped["price"])
    symbol = mapped.get("symbol", "")
    avg30, max6m = _external_enrich(symbol, price)
    mapped["avg30d"] = f"{avg30:.2f}"
    mapped["max6m"]  = f"{max6m:.2f}"
    return mapped


def process_one(incoming_key: str):
    print("Processing:", incoming_key)
    text = download_text(incoming_key)

    reader = csv.DictReader(io.StringIO(text))
    out = io.StringIO()
    fieldnames = ["internal_id","symbol","category","price","volume","avg30d","max6m"]
    w = csv.DictWriter(out, fieldnames=fieldnames)
    w.writeheader()

    for row in reader:
        mapped = {
            "internal_id": row.get("internal_id",""),
            "symbol": row.get("symbol",""),
            "category": row.get("category",""),
            "price": row.get("price","0"),
            "volume": row.get("volume","0"),
        }
        w.writerow(enrich_row(mapped))

    processed_key = incoming_key.replace("incoming/", "processed/")
    upload_text(processed_key, out.getvalue())
    print("Uploaded processed:", processed_key)

    request_id = str(uuid.uuid4())
    pending[request_id] = incoming_key

    files = {"file": ("mapped.csv", out.getvalue(), "text/csv")}
    data = {
        "mapper_version": MAPPER_VERSION,
        "request_id": request_id,
        "webhook_url": f"http://processor:{WEBHOOK_PORT}/webhook/xml",
    }

    r = requests.post(XML_SERVICE_URL, files=files, data=data, timeout=30)
    print("XML service:", r.status_code, r.text)


def poll_loop():
    while True:
        try:
            keys = list_incoming()
            if keys:
                process_one(keys[0])
        except Exception as e:
            print("poll error:", e)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    threading.Thread(target=poll_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=WEBHOOK_PORT)
