# Distributed Data Integration Platform

Distributed microservices platform for financial market data integration, transformation and interoperability.

The system implements an end-to-end pipeline that generates market data in CSV format, processes and enriches it, converts it to hierarchical XML, persists it in PostgreSQL and exposes the resulting data through multiple communication interfaces.

## Project Report

- [View Project Report](project-report.pdf)

## Architecture

The platform is composed of independent containerized services orchestrated with Docker Compose.

```text
Crawler
   |
   v
Supabase S3 Storage
   |
   v
Processor
   |
   v
XML Service
   |
   v
PostgreSQL
   |
   +---- REST
   |
   +---- GraphQL
   |
   +---- XML-RPC
   |
   +---- gRPC
   |
   +---- Go Viewer
```

## Data Pipeline

### Crawler

A Python service periodically generates simulated financial market data in CSV format and uploads it to Supabase Storage through its S3-compatible API.

### Processor

The processor monitors incoming CSV files and performs an ETL workflow:

- Reads CSV data from S3-compatible storage
- Normalizes the input schema
- Enriches records using external market data
- Calculates additional financial metrics
- Stores the processed dataset
- Sends enriched data to the XML Service

A webhook confirmation mechanism ensures that source files are removed only after successful XML persistence.

### XML Service

Implemented with Node.js, the XML Service:

- Receives enriched CSV data
- Converts records into hierarchical XML
- Persists XML documents in PostgreSQL
- Stores processing metadata
- Exposes REST endpoints for querying the persisted XML

PostgreSQL `XMLTABLE` and XPath expressions are used to transform XML nodes into queryable relational results.

### BI Service

A Python GraphQL service provides a unified query interface over the XML Service, supporting:

- Asset listing
- Aggregation by category
- Ranking by trading volume

### Viewer Service

A lightweight Go service consumes the GraphQL API and provides a simple web interface for visualizing query results.

## Interoperability

The same underlying information can be consumed through multiple communication technologies:

- REST
- GraphQL
- XML-RPC
- gRPC / Protocol Buffers

This demonstrates interoperability between heterogeneous clients and protocols.

## Storage

The system uses:

- **Supabase Storage / S3-compatible API** for asynchronous CSV exchange
- **PostgreSQL** for XML document persistence and metadata

## Containerization

The local environment is orchestrated with Docker Compose and includes:

- PostgreSQL
- Crawler
- Processor
- XML Service
- BI Service
- Viewer Service
- XML-RPC Service
- gRPC Service

## Cloud Deployment

The XML Service was also deployed independently to **Microsoft Azure Container Apps** to validate containerized cloud deployment and public HTTP availability.

The `/health` endpoint was successfully exposed and tested.

> The complete pipeline, including PostgreSQL persistence and the remaining services, was executed locally using Docker Compose. The Azure deployment was limited to the XML Service and was not connected to the local PostgreSQL database.

## Technologies

- Python
- Node.js
- Go
- PostgreSQL
- XML
- XPath / XMLTABLE
- REST APIs
- GraphQL
- XML-RPC
- gRPC
- Protocol Buffers
- Docker
- Docker Compose
- Supabase Storage / S3 API
- Microsoft Azure Container Apps

## Repository Structure

```text
.
├── bi-service/
├── crawler/
├── grpc-service/
├── infra/
├── processor/
├── viewer-service/
├── xml-service/
├── xmlrpc-service/
├── docker-compose.yml
├── sample.csv
├── test.csv
├── project-report.pdf
└── README.md
```

## Running Locally

### Requirements

- Docker
- Docker Compose
- Supabase project with S3-compatible storage credentials
- A Supabase Storage bucket created and accessible through the S3-compatible API
- Internet access for Supabase Storage and external market-data enrichment

Create a local `.env` file containing the required configuration:

```text
SUPABASE_S3_ENDPOINT=
SUPABASE_S3_REGION=
SUPABASE_S3_ACCESS_KEY=
SUPABASE_S3_SECRET_KEY=
SUPABASE_BUCKET_NAME=

CRAWLER_POLL_SECONDS=15

PROCESSOR_POLL_SECONDS=10
PROCESSOR_WEBHOOK_PORT=8089
MAPPER_VERSION=v1
XML_SERVICE_URL=http://xml-service:3000/ingest

XML_SERVICE_PORT=3000
BI_PORT=8000
XML_SERVICE_BASE=http://xml-service:3000

POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
```

The `.env` file is intentionally excluded from version control.

Start the complete environment with:

```bash
docker compose up --build
```

## Project Highlights

- Distributed microservices architecture
- Python, Node.js and Go services
- Asynchronous processing pipeline
- S3-compatible object storage
- External data enrichment
- CSV-to-XML transformation
- XML persistence in PostgreSQL
- XPath and XMLTABLE queries
- REST and GraphQL APIs
- XML-RPC and gRPC interoperability
- Dockerized local deployment
- Azure Container Apps deployment validation

## Author

Ivo Ramoa

Developed as part of the Systems Integration coursework at **IPVC - Escola Superior de Tecnologia e Gestão**.
