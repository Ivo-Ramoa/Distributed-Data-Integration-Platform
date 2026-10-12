CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tp3_documentos_xml (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  xml_documento XML NOT NULL,
  data_criacao TIMESTAMP NOT NULL DEFAULT NOW(),
  mapper_version TEXT NOT NULL,
  request_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tp3_request_id ON tp3_documentos_xml(request_id);
