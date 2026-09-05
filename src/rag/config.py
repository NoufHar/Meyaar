from pathlib import Path


# =========================================================
# Paths
# =========================================================

DOCS_DIR = Path("data/geosa_docs")

DB_DIR = "data/geosa_chroma"

COLLECTION_NAME = "geosa_standards"


# =========================================================
# Embeddings
# =========================================================

EMBEDDING_MODEL = "intfloat/multilingual-e5-small"

CHUNKING_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"


# =========================================================
# Semantic Chunking
# =========================================================

SEMANTIC_BREAKPOINT_TYPE = "percentile"

SEMANTIC_BREAKPOINT_AMOUNT = 90


# =========================================================
# Retrieval
# =========================================================

DENSE_TOP_K = 15

BM25_TOP_K = 15

HYBRID_TOP_K = 10

RRF_K = 60


# =========================================================
# Query Expansion
# =========================================================

QUERY_EXPANSION_MODEL = "openai/gpt-oss-20b"


# =========================================================
# Final RAG
# =========================================================

RETRIEVE_TOP_K = 10

FINAL_TOP_K = 3