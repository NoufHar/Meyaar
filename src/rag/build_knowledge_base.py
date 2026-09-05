import chromadb
import pymupdf

from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from src.rag.config import (
    COLLECTION_NAME,
    DB_DIR,
    DOCS_DIR,
    EMBEDDING_MODEL,
    CHUNKING_EMBEDDING_MODEL,
    SEMANTIC_BREAKPOINT_AMOUNT,
    SEMANTIC_BREAKPOINT_TYPE,
)


SOURCE_INFO = {
    "national_geospatial_data_standards.pdf": {
        "source": "National Geospatial Data Standards",
        "category": "data_quality",
        "applicable_to": "roads,buildings,general_gis",
    },

    "sansrs_user_guideline.pdf": {
        "source": "SANSRS User Guideline",
        "category": "spatial_reference",
        "applicable_to": "crs,coordinates,spatial_reference",
    },

    "cartography_technical_guideline.pdf": {
        "source": "Technical Guidelines for Cartography",
        "category": "cartography",
        "applicable_to": "map_images,vision,cartography",
    },

    "national_geospatial_governance_framework.pdf": {
        "source": "National Geospatial Governance Framework",
        "category": "governance",
        "applicable_to": "governance,policy,management",
    },
}


# =========================================================
# Semantic Chunking Model
# =========================================================

chunk_embeddings = HuggingFaceEmbeddings(
    model_name=CHUNKING_EMBEDDING_MODEL,
    model_kwargs={
        "device": "cpu",
    },
    encode_kwargs={
        "normalize_embeddings": True,
    },
)


semantic_chunker = SemanticChunker(
    embeddings=chunk_embeddings,
    breakpoint_threshold_type=SEMANTIC_BREAKPOINT_TYPE,
    breakpoint_threshold_amount=SEMANTIC_BREAKPOINT_AMOUNT,
)


# =========================================================
# Vector Embedding Model
# =========================================================
# E5 works best with query/passages instructions.

embed_model = HuggingFaceEmbedding(
    model_name=EMBEDDING_MODEL,
    device="cpu",
    normalize=True,
    embed_batch_size=16,
    query_instruction="query: ",
    text_instruction="passage: ",
)


# =========================================================
# Utilities
# =========================================================

def clean_text(text):
    if not text:
        return ""

    return " ".join(text.split())


def split_text_semantically(text):
    text = clean_text(text)

    if not text:
        return []

    try:
        documents = semantic_chunker.create_documents(
            [text]
        )

        chunks = []

        for document in documents:
            chunk_text = clean_text(
                document.page_content
            )

            if chunk_text:
                chunks.append(chunk_text)

        return chunks

    except Exception as error:
        print(
            "Semantic chunking failed. "
            "Using whole page as one chunk."
        )

        print("Reason:", error)

        return [text]


# =========================================================
# PDF Extraction
# =========================================================

def extract_pdf_nodes(
    pdf_path,
    source_info,
):
    document = pymupdf.open(
        pdf_path
    )

    nodes = []

    for page_index, page in enumerate(
        document,
        start=1,
    ):
        page_text = clean_text(
            page.get_text("text")
        )

        if not page_text:
            continue

        semantic_chunks = split_text_semantically(
            page_text
        )

        print(
            f"  Page {page_index}: "
            f"{len(semantic_chunks)} chunks"
        )

        for chunk_index, chunk_text in enumerate(
            semantic_chunks,
            start=1,
        ):
            node_id = (
                f"{pdf_path.stem}"
                f"_p{page_index}"
                f"_c{chunk_index}"
            )

            node = TextNode(
                id_=node_id,
                text=chunk_text,
                metadata={
                    "source": source_info["source"],
                    "file": pdf_path.name,
                    "page": int(page_index),
                    "category": source_info["category"],
                    "applicable_to": source_info["applicable_to"],
                    "chunk_number": int(chunk_index),
                },
            )

            nodes.append(node)

    document.close()

    return nodes


# =========================================================
# Build Knowledge Base
# =========================================================

def build_knowledge_base():
    print()
    print(
        "GeoSA LlamaIndex Knowledge Base"
    )
    print("=" * 60)

    if not DOCS_DIR.exists():
        raise FileNotFoundError(
            f"Documents directory not found: "
            f"{DOCS_DIR}"
        )

    # -----------------------------------------------------
    # Chroma
    # -----------------------------------------------------

    chroma_client = chromadb.PersistentClient(
        path=DB_DIR
    )

    try:
        chroma_client.delete_collection(
            name=COLLECTION_NAME
        )

        print(
            "\nOld Chroma collection removed."
        )

    except Exception:
        pass

    chroma_collection = (
        chroma_client.create_collection(
            name=COLLECTION_NAME,
            metadata={
                "hnsw:space": "cosine"
            },
        )
    )

    vector_store = ChromaVectorStore(
        chroma_collection=chroma_collection
    )

    storage_context = (
        StorageContext.from_defaults(
            vector_store=vector_store
        )
    )

    # -----------------------------------------------------
    # Extract Nodes
    # -----------------------------------------------------

    all_nodes = []

    for filename, source_info in SOURCE_INFO.items():

        pdf_path = (
            DOCS_DIR / filename
        )

        if not pdf_path.exists():

            print(
                f"\nWARNING: File not found: "
                f"{pdf_path}"
            )

            continue

        print()
        print("=" * 60)

        print(
            f"Processing: {filename}"
        )

        nodes = extract_pdf_nodes(
            pdf_path=pdf_path,
            source_info=source_info,
        )

        print(
            f"Total semantic chunks: "
            f"{len(nodes)}"
        )

        all_nodes.extend(
            nodes
        )

    if not all_nodes:
        raise RuntimeError(
            "No nodes were created."
        )

    print()
    print("=" * 60)

    print(
        f"Total nodes: "
        f"{len(all_nodes)}"
    )

    # -----------------------------------------------------
    # Create Index
    # -----------------------------------------------------

    print()
    print(
        f"Embedding model: "
        f"{EMBEDDING_MODEL}"
    )

    print(
        "Creating embeddings and index..."
    )

    VectorStoreIndex(
        nodes=all_nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True,
    )

    print()
    print("=" * 60)

    print(
        "Knowledge base created successfully."
    )

    print(
        "Collection:",
        COLLECTION_NAME,
    )

    print(
        "Nodes:",
        chroma_collection.count(),
    )

    print(
        "Database:",
        DB_DIR,
    )

    print(
        "Embedding model:",
        EMBEDDING_MODEL,
    )

    print("=" * 60)


if __name__ == "__main__":
    build_knowledge_base()