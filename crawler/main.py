import os, time, csv, io, datetime, random
import boto3
from botocore.client import Config

S3_ENDPOINT = (os.getenv("SUPABASE_S3_ENDPOINT") or "").rstrip("/")
S3_REGION   = os.getenv("SUPABASE_S3_REGION")
S3_ACCESS   = os.getenv("SUPABASE_S3_ACCESS_KEY")
S3_SECRET   = os.getenv("SUPABASE_S3_SECRET_KEY")
BUCKET      = os.getenv("SUPABASE_BUCKET_NAME")

POLL_SECONDS = int(os.getenv("CRAWLER_POLL_SECONDS", "15"))

s3 = boto3.client(
    "s3",
    region_name=S3_REGION,
    aws_access_key_id=S3_ACCESS,
    aws_secret_access_key=S3_SECRET,
    endpoint_url=S3_ENDPOINT,
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)

def generate_csv() -> str:
    # Ajusta aqui o tamanho do CSV (sem mexer em mais ficheiros)
    N = 50

    # Poucos símbolos para o processor usar cache e não ficar lento
    tickers = [
        ("AAPL", "Tecnologia"),
        ("TSLA", "Automovel"),
        ("MSFT", "Tecnologia"),
        ("AMZN", "Tecnologia"),
        ("GOOGL", "Tecnologia"),
    ]

    rows = []
    base_id = 3000
    for i in range(1, N + 1):
        sym, cat = random.choice(tickers)

        # Valores variam mas mantêm formato do CSV
        price = round(random.uniform(100.0, 400.0), 2)
        volume = random.randint(100_000, 2_000_000)

        rows.append({
            "internal_id": f"CSV_{base_id + i}",
            "symbol": sym,
            "category": cat,
            "price": f"{price}",
            "volume": f"{volume}",
        })

    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=["internal_id","symbol","category","price","volume"])
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()

def upload_incoming(content: str):
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    key = f"incoming/market_{ts}.csv"
    s3.put_object(Bucket=BUCKET, Key=key, Body=content.encode("utf-8"))
    print("Uploaded:", key)

if __name__ == "__main__":
    while True:
        try:
            upload_incoming(generate_csv())
        except Exception as e:
            print("crawler error:", e)
        time.sleep(POLL_SECONDS)
