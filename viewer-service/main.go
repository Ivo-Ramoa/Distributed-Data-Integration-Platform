package main

import (
	"bytes"
	"io"
	"log"
	"net/http"
	"os"
)

func main() {
	biURL := os.Getenv("BI_SERVICE_URL")
	if biURL == "" {
		biURL = "http://bi-service:8000"
	}
	port := os.Getenv("VIEWER_PORT")
	if port == "" {
		port = "8080"
	}

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		io.WriteString(w, indexHTML)
	})

	// Proxy para evitar CORS: o browser chama /graphql no viewer-service,
	// e o viewer-service reencaminha para o BI Service.
	http.HandleFunc("/graphql", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Only POST", http.StatusMethodNotAllowed)
			return
		}
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "Bad body", http.StatusBadRequest)
			return
		}

		req, err := http.NewRequest(http.MethodPost, biURL+"/graphql", bytes.NewReader(body))
		if err != nil {
			http.Error(w, "Upstream request failed", http.StatusBadGateway)
			return
		}
		req.Header.Set("Content-Type", "application/json")

		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			http.Error(w, "Upstream unreachable", http.StatusBadGateway)
			return
		}
		defer resp.Body.Close()

		w.Header().Set("Content-Type", resp.Header.Get("Content-Type"))
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	})

	log.Printf("viewer-service on :%s (proxy -> %s)\n", port, biURL)
	log.Fatal(http.ListenAndServe("0.0.0.0:"+port, nil))
}

const indexHTML = `<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>TP3 - Viewer (Go)</title>
  <style>
    body{font-family:Arial,sans-serif;margin:20px;}
    button{margin-right:10px;margin-bottom:10px;}
    pre{background:#111;color:#0f0;padding:12px;border-radius:6px;overflow:auto;}
    input{width:80px;}
  </style>
</head>
<body>
  <h3>TP3 - Viewer Service (Go)</h3>
  <p>Este serviço prova uma 3.ª linguagem (Go) e consome o BI Service via GraphQL.</p>

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
</html>`
