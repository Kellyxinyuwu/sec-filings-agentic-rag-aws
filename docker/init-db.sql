-- Enable pgvector in rag_db (POSTGRES_DB from docker-compose).
-- Table schema comes later in app/store.py init_schema() — not here.
CREATE EXTENSION IF NOT EXISTS vector;