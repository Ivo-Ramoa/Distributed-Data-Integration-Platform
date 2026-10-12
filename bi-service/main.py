import os
import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from strawberry.fastapi import GraphQLRouter
import strawberry


XML_SERVICE_BASE = os.getenv("XML_SERVICE_BASE", "http://xml-service:3000")

app = FastAPI()


@app.get("/health")
def health():
    return {"ok": True}


# -------------------------
# GraphQL types
# -------------------------
@strawberry.type
class Ativo:
    ticker: str
    tipo: str
    preco: float
    volume: int


@strawberry.type
class AggItem:
    tipo: str
    total: int


# -------------------------
# Helpers (calls to xml-service REST)
# -------------------------
def _get_json(path: str, params: dict | None = None) -> dict:
    url = f"{XML_SERVICE_BASE}{path}"
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


# -------------------------
# GraphQL resolvers
# -------------------------
@strawberry.type
class Query:
    @strawberry.field
    def ativos(self, tipo: str | None = None) -> list[Ativo]:
        data = _get_json("/query/ativos", params={"tipo": tipo} if tipo else None)
        rows = data.get("ativos", [])
        out = []
        for x in rows:
            out.append(
                Ativo(
                    ticker=str(x.get("ticker", "")),
                    tipo=str(x.get("tipo", "")),
                    preco=float(x.get("preco", 0)),
                    volume=int(x.get("volume", 0)),
                )
            )
        return out

    @strawberry.field
    def aggCategory(self) -> list[AggItem]:
        data = _get_json("/query/agg/category")
        rows = data.get("agg", [])
        out = []
        for x in rows:
            out.append(AggItem(tipo=str(x.get("tipo", "")), total=int(x.get("total", 0))))
        return out

    @strawberry.field
    def topVolume(self, limit: int = 5) -> list[Ativo]:
        data = _get_json("/query/top-volume", params={"limit": limit})
        rows = data.get("top", [])
        out = []
        for x in rows:
            out.append(
                Ativo(
                    ticker=str(x.get("ticker", "")),
                    tipo=str(x.get("tipo", "")),
                    preco=0.0,  # este endpoint não devolve preco; mantemos 0
                    volume=int(x.get("volume", 0)),
                )
            )
        return out


schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")


# -------------------------
# Simple web page (visualização)
# -------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>TP3 - Visualização</title>
  <style>
    body{font-family:Arial, sans-serif; margin:20px;}
    button{margin-right:10px; margin-bottom:10px;}
    pre{background:#111; color:#0f0; padding:12px; border-radius:6px; overflow:auto;}
    input{width:80px;}
  </style>
</head>
<body>
  <h3>TP3 - BI Service (Visualização)</h3>

  <button onclick="qAtivos()">Ativos</button>
  <button onclick="qAgg()">Agg por tipo</button>

  <label>Top N:</label>
  <input id="n" type="number" value="3" min="1" max="50"/>
  <button onclick="qTop()">Top Volume</button>

  <pre id="out">Carrega num botão...</pre>

<script>
async function run(query, variables=null){
  const r = await fetch('/graphql', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({query, variables})
  });
  const j = await r.json();
  document.getElementById('out').textContent = JSON.stringify(j, null, 2);
}

function qAtivos(){
  run('{ ativos { ticker tipo preco volume } }');
}
function qAgg(){
  run('{ aggCategory { tipo total } }');
}
function qTop(){
  const n = parseInt(document.getElementById('n').value || '3', 10);
  run('query($n:Int!){ topVolume(limit:$n){ ticker tipo volume } }', {n});
}
</script>
</body>
</html>
"""
