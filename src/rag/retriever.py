import re

import chromadb

from rank_bm25 import BM25Okapi

from llama_index.core import VectorStoreIndex

from llama_index.core.schema import QueryBundle

from llama_index.core.vector_stores import (
    ExactMatchFilter,
    MetadataFilters,
)

from llama_index.embeddings.huggingface import (
    HuggingFaceEmbedding,
)

from llama_index.vector_stores.chroma import (
    ChromaVectorStore,
)

from src.rag.config import (
    DB_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    DENSE_TOP_K,
    BM25_TOP_K,
    HYBRID_TOP_K,
    RRF_K,
)

from src.rag.query_expander import (
    expand_query,
)


# =========================================================
# Embedding Model
# =========================================================

embed_model = HuggingFaceEmbedding(
    model_name=EMBEDDING_MODEL,
    device="cpu",
    normalize=True,
    query_instruction="query: ",
    text_instruction="passage: ",
)


# =========================================================
# Chroma
# =========================================================

client = chromadb.PersistentClient(
    path=DB_DIR
)

collection = client.get_collection(
    name=COLLECTION_NAME
)

vector_store = ChromaVectorStore(
    chroma_collection=collection
)


# =========================================================
# Dense Index
# =========================================================

index = VectorStoreIndex.from_vector_store(
    vector_store=vector_store,
    embed_model=embed_model,
)


# =========================================================
# Load Data for BM25
# =========================================================

chroma_data = collection.get(
    include=[
        "documents",
        "metadatas",
    ]
)

ALL_IDS = chroma_data["ids"]
ALL_DOCUMENTS = chroma_data["documents"]
ALL_METADATA = chroma_data["metadatas"]


# =========================================================
# Tokenization
# =========================================================

def tokenize(text):
    if not text:
        return []

    text = str(text).lower()

    return re.findall(
        r"[\u0600-\u06FF]+|[a-z0-9_-]+",
        text,
    )


# =========================================================
# BM25 Search Text
# =========================================================

def build_bm25_text(
    text,
    metadata,
):
    metadata = metadata or {}

    return " ".join(
        [
            str(
                metadata.get(
                    "source",
                    "",
                )
            ),

            str(
                metadata.get(
                    "category",
                    "",
                )
            ),

            str(
                metadata.get(
                    "applicable_to",
                    "",
                )
            ),

            str(
                metadata.get(
                    "file",
                    "",
                )
            ),

            str(text),
        ]
    )


# =========================================================
# BM25 Cache
# =========================================================

BM25_CACHE = {}


def get_bm25_for_category(
    category=None,
):
    cache_key = (
        category
        or "__all__"
    )

    if cache_key in BM25_CACHE:
        return BM25_CACHE[
            cache_key
        ]

    ids = []

    documents = []

    metadatas = []

    search_documents = []

    for (
        node_id,
        text,
        metadata,
    ) in zip(
        ALL_IDS,
        ALL_DOCUMENTS,
        ALL_METADATA,
    ):
        metadata = metadata or {}

        if category:
            if (
                metadata.get(
                    "category"
                )
                != category
            ):
                continue

        ids.append(
            node_id
        )

        documents.append(
            text
        )

        metadatas.append(
            metadata
        )

        search_documents.append(
            build_bm25_text(
                text=text,
                metadata=metadata,
            )
        )

    tokenized_documents = [
        tokenize(text)
        for text
        in search_documents
    ]

    bm25 = BM25Okapi(
        tokenized_documents
    )

    BM25_CACHE[
        cache_key
    ] = {
        "bm25": bm25,
        "ids": ids,
        "documents": documents,
        "metadatas": metadatas,
    }

    return BM25_CACHE[
        cache_key
    ]


# =========================================================
# Dense Retrieval
# =========================================================

def dense_retrieve(
    query,
    category=None,
    top_k=DENSE_TOP_K,
):
    filters = None

    if category:
        filters = MetadataFilters(
            filters=[
                ExactMatchFilter(
                    key="category",
                    value=category,
                )
            ]
        )

    retriever = index.as_retriever(
        similarity_top_k=top_k,
        filters=filters,
    )

    nodes = retriever.retrieve(
        QueryBundle(
            query_str=query
        )
    )

    results = []

    for rank, node in enumerate(
        nodes,
        start=1,
    ):
        metadata = (
            node.node.metadata
            or {}
        )

        results.append(
            {
                "id":
                    node.node.node_id,

                "text":
                    node.node.get_content(),

                "source":
                    metadata.get(
                        "source",
                        "Unknown",
                    ),

                "page":
                    metadata.get(
                        "page"
                    ),

                "category":
                    metadata.get(
                        "category"
                    ),

                "applicable_to":
                    metadata.get(
                        "applicable_to"
                    ),

                "chunk_number":
                    metadata.get(
                        "chunk_number"
                    ),

                "rank":
                    rank,

                "score": (
                    float(
                        node.score
                    )
                    if node.score
                    is not None
                    else None
                ),
            }
        )

    return results


# =========================================================
# BM25 Retrieval
# =========================================================

def bm25_retrieve(
    query,
    category=None,
    top_k=BM25_TOP_K,
):
    data = get_bm25_for_category(
        category
    )

    query_tokens = tokenize(
        query
    )

    scores = (
        data["bm25"]
        .get_scores(
            query_tokens
        )
    )

    ranked_indexes = sorted(
        range(
            len(scores)
        ),
        key=lambda i: scores[i],
        reverse=True,
    )[:top_k]

    results = []

    for rank, index_ in enumerate(
        ranked_indexes,
        start=1,
    ):
        metadata = (
            data["metadatas"][
                index_
            ]
            or {}
        )

        results.append(
            {
                "id":
                    data["ids"][
                        index_
                    ],

                "text":
                    data["documents"][
                        index_
                    ],

                "source":
                    metadata.get(
                        "source",
                        "Unknown",
                    ),

                "page":
                    metadata.get(
                        "page"
                    ),

                "category":
                    metadata.get(
                        "category"
                    ),

                "applicable_to":
                    metadata.get(
                        "applicable_to"
                    ),

                "chunk_number":
                    metadata.get(
                        "chunk_number"
                    ),

                "rank":
                    rank,

                "score":
                    float(
                        scores[index_]
                    ),
            }
        )

    return results


# =========================================================
# Three-Way Reciprocal Rank Fusion
# =========================================================

def reciprocal_rank_fusion(
    ranking_groups,
    top_k=HYBRID_TOP_K,
):
    """
    Weighted Reciprocal Rank Fusion.

    Supports both:
    - (name, results)
    - (name, results, weight)

    If weight is not provided, default = 1.0.
    """

    combined = {}

    for group in ranking_groups:

        # Backward compatibility
        if len(group) == 2:
            ranking_name, results = group
            weight = 1.0

        elif len(group) == 3:
            ranking_name, results, weight = group

        else:
            raise ValueError(
                "Each ranking group must contain "
                "(name, results) or (name, results, weight)"
            )

        for result in results:

            node_id = result["id"]

            if node_id not in combined:
                combined[node_id] = {
                    "id": node_id,
                    "text": result["text"],
                    "source": result["source"],
                    "page": result["page"],
                    "category": result["category"],
                    "applicable_to": result["applicable_to"],
                    "chunk_number": result["chunk_number"],

                    "rrf_score": 0.0,

                    "retrieval_ranks": {},
                    "retrieval_scores": {},
                }

            rank = result["rank"]

            combined[node_id]["rrf_score"] += (
                float(weight)
                /
                (
                    RRF_K
                    + rank
                )
            )

            combined[node_id]["retrieval_ranks"][
                ranking_name
            ] = rank

            combined[node_id]["retrieval_scores"][
                ranking_name
            ] = result.get("score")

    fused = sorted(
        combined.values(),
        key=lambda item: item["rrf_score"],
        reverse=True,
    )

    return fused[:top_k]
# =========================================================
# Main Retriever
# =========================================================

def retrieve_geosa_context(
    query,
    top_k=HYBRID_TOP_K,
    category=None,
):
    """
    Meyaar Cross-Lingual Hybrid Retrieval

    Arabic Query
          |
          +--> E5 Arabic
          |
          +--> Automatic English Expansion
                    |
                    +--> E5 English
          |
          +--> Arabic + English BM25
                    |
                    v
                  RRF
                    |
                    v
               Final Top K
    """

    # -----------------------------------------------------
    # 1. Automatic English query expansion
    # -----------------------------------------------------

    expanded_query = expand_query(
        query
    )

    # -----------------------------------------------------
    # 2. Original Arabic E5 retrieval
    # -----------------------------------------------------

    original_dense = dense_retrieve(
        query=query,
        category=category,
        top_k=DENSE_TOP_K,
    )

    # -----------------------------------------------------
    # 3. Expanded English E5 retrieval
    # -----------------------------------------------------

    expanded_dense = dense_retrieve(
        query=expanded_query,
        category=category,
        top_k=DENSE_TOP_K,
    )

    # -----------------------------------------------------
    # 4. Bilingual BM25 retrieval
    # -----------------------------------------------------

    bilingual_query = (
        f"{query} "
        f"{expanded_query}"
    )

    bm25_results = bm25_retrieve(
        query=bilingual_query,
        category=category,
        top_k=BM25_TOP_K,
    )

    # -----------------------------------------------------
    # 5. Three-way RRF
    # -----------------------------------------------------

    fused_results = reciprocal_rank_fusion(
    ranking_groups=[
        (
            "dense_original",
            original_dense,
            1.0,
        ),
        (
            "bm25_bilingual",
            bm25_results,
            1.0,
        ),
        (
            "dense_expanded",
            expanded_dense,
            1.0,
        ),
    ],
    top_k=top_k,)
    # -----------------------------------------------------
    # 6. Final Output
    # -----------------------------------------------------

    results = []

    seen = set()

    for result in fused_results:

        duplicate_key = (
            result.get(
                "source"
            ),
            result.get(
                "page"
            ),
            result.get(
                "text",
                "",
            ).strip(),
        )

        if duplicate_key in seen:
            continue

        seen.add(
            duplicate_key
        )

        results.append(
            {
                "text":
                    result.get(
                        "text"
                    ),

                "source":
                    result.get(
                        "source"
                    ),

                "page":
                    result.get(
                        "page"
                    ),

                "category":
                    result.get(
                        "category"
                    ),

                "applicable_to":
                    result.get(
                        "applicable_to"
                    ),

                "chunk_number":
                    result.get(
                        "chunk_number"
                    ),

                "rrf_score":
                    result.get(
                        "rrf_score"
                    ),

                "retrieval_ranks":
                    result.get(
                        "retrieval_ranks"
                    ),

                "retrieval_scores":
                    result.get(
                        "retrieval_scores"
                    ),

                # Helpful for debugging only.
                "expanded_query":
                    expanded_query,
            }
        )

    return results