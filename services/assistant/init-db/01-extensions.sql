-- Runs once on first database initialization (docker-entrypoint-initdb.d).
-- Enables pgvector so the `vector` column type and distance operators
-- (<=> cosine, <-> L2) are available. The chunk table + HNSW index that
-- use this arrive in Chunk 2.
CREATE EXTENSION IF NOT EXISTS vector;
