const express = require("express");
const multer = require("multer");
const { Pool } = require("pg");
const { parse } = require("csv-parse");
const { create } = require("xmlbuilder2");

const app = express();
const upload = multer({ storage: multer.memoryStorage() });

const PORT = process.env.XML_SERVICE_PORT || 3000;
const connectionString = process.env.DATABASE_URL;

const useSsl =
  (connectionString && connectionString.includes("amazonaws.com")) ||
  (connectionString && connectionString.includes("sslmode=require"));

const pool = new Pool({
  connectionString,
  ssl: useSsl ? { rejectUnauthorized: false } : false,
});

app.get("/health", (_, res) => res.json({ ok: true }));

// multipart: file, mapper_version, request_id, webhook_url
app.post("/ingest", upload.single("file"), async (req, res) => {
  const mapperVersion = req.body.mapper_version || "v1";
  const requestId = req.body.request_id || "no-request-id";
  const webhookUrl = req.body.webhook_url || null;

  if (!req.file) return res.status(400).json({ error: "missing file" });

  try {
    const rows = await parseCsv(req.file.buffer);
    const xml = buildXml(rows, mapperVersion);

    const q = `
      INSERT INTO tp3_documentos_xml(xml_documento, mapper_version, request_id)
      VALUES ($1::xml, $2, $3)
      RETURNING id
    `;
    const r = await pool.query(q, [xml, mapperVersion, requestId]);
    const docId = r.rows[0].id;

    // Resposta imediata ao caller
    res.json({ status: "OK", doc_id: docId, request_id: requestId });

    // Webhook assíncrono (não bloqueia o response)
    if (webhookUrl) {
      sendWebhook(webhookUrl, {
        request_id: requestId,
        status: "OK",
        doc_id: docId,
      })
        .then(() => console.log("Webhook sent:", webhookUrl, requestId))
        .catch((e) => console.log("Webhook failed:", e.message));
    }
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: "ingest failed" });

    // webhook de erro (assíncrono)
    const webhookUrl = req.body.webhook_url || null;
    if (webhookUrl) {
      sendWebhook(webhookUrl, {
        request_id: req.body.request_id || "no-request-id",
        status: "ERROR",
      }).catch(() => {});
    }
  }
});

function parseCsv(buffer) {
  return new Promise((resolve, reject) => {
    const records = [];
    const parser = parse(buffer, {
      columns: true,
      skip_empty_lines: true,
      trim: true,
    });

    parser.on("readable", () => {
      let record;
      while ((record = parser.read()) !== null) records.push(record);
    });

    parser.on("error", reject);
    parser.on("end", () => resolve(records));
  });
}

function buildXml(rows, mapperVersion) {
  const root = create({ version: "1.0" })
    .ele("RelatorioConformidade", {
      DataGeracao: new Date().toISOString(),
      Versao: "1.0",
    })
    .ele("Configuracao", { MapperVersion: mapperVersion, FonteCSV: "incoming" })
    .up()
    .ele("Ativos");

  for (const r of rows) {
    // CSV: internal_id,symbol,category,price,volume,avg30d,max6m
    const ativo = root.ele("Ativo", {
      IdInterno: r.internal_id,
      Ticker: r.symbol,
      Tipo: r.category,
    });

    // DetalheNegociacao
    ativo
      .ele("DetalheNegociacao")
      .ele("PrecoAtual", { Moeda: "EUR" })
      .txt(String(r.price))
      .up()
      .ele("VolumeNegociado", { Unidade: "Acoes" })
      .txt(String(r.volume))
      .up()
      .up();

    // HistoricoAPI (dados enriquecidos vindos do Processor/API externa)
    // Se não vierem preenchidos, ainda assim fica coerente
    ativo
      .ele("HistoricoAPI")
      .ele("Media30d")
      .txt(String(r.avg30d ?? ""))
      .up()
      .ele("Maximo6m")
      .txt(String(r.max6m ?? ""))
      .up()
      .up();

    ativo.up();
  }

  return root.up().up().end({ prettyPrint: true });
}

async function sendWebhook(url, payload) {
  // Node 18 tem fetch global
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`Webhook HTTP ${r.status}`);
}

// endpoints XMLTABLE (mantém os teus; podes deixar como já estavam)
// Nota: se quiseres também expor avg30d/max6m, adicionamos depois.
app.get("/query/ativos", async (req, res) => {
  const tipo = req.query.tipo;

  const sql = `
    SELECT
      x.ticker,
      x.tipo,
      (x.preco)::float AS preco,
      (x.volume)::bigint AS volume
    FROM tp3_documentos_xml d,
    LATERAL XMLTABLE(
      '/RelatorioConformidade/Ativos/Ativo'
      PASSING d.xml_documento
      COLUMNS
        ticker text PATH '@Ticker',
        tipo   text PATH '@Tipo',
        preco  text PATH 'DetalheNegociacao/PrecoAtual/text()',
        volume text PATH 'DetalheNegociacao/VolumeNegociado/text()'
    ) AS x
    WHERE ($1::text IS NULL OR x.tipo = $1::text)
    ORDER BY x.ticker
    LIMIT 200
  `;

  const r = await pool.query(sql, [tipo ?? null]);
  res.json({ ativos: r.rows });
});

app.get("/query/agg/category", async (req, res) => {
  const sql = `
    SELECT x.tipo, COUNT(*)::int AS total
    FROM tp3_documentos_xml d,
    LATERAL XMLTABLE(
      '/RelatorioConformidade/Ativos/Ativo'
      PASSING d.xml_documento
      COLUMNS
        tipo text PATH '@Tipo'
    ) AS x
    GROUP BY x.tipo
    ORDER BY total DESC
  `;
  const r = await pool.query(sql);
  res.json({ agg: r.rows });
});

app.get("/query/top-volume", async (req, res) => {
  const limit = Math.min(parseInt(req.query.limit || "5", 10), 50);

  const sql = `
    SELECT
      x.ticker,
      x.tipo,
      (x.volume)::bigint AS volume
    FROM tp3_documentos_xml d,
    LATERAL XMLTABLE(
      '/RelatorioConformidade/Ativos/Ativo'
      PASSING d.xml_documento
      COLUMNS
        ticker text PATH '@Ticker',
        tipo   text PATH '@Tipo',
        volume text PATH 'DetalheNegociacao/VolumeNegociado/text()'
    ) AS x
    ORDER BY (x.volume)::bigint DESC
    LIMIT $1
  `;
  const r = await pool.query(sql, [limit]);
  res.json({ top: r.rows });
});

app.listen(PORT, () => console.log(`xml-service on :${PORT}`));
