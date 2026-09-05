import pandas as pd

from src.rag.retriever import retrieve_geosa_context


def infer_category(row):
    """
    Map each evaluation question to the category
    that would realistically be known by Meyaar.
    """

    applicable_to = str(row.get("applicable_to", "")).lower()
    topic = str(row.get("expected_topic", "")).lower()
    source = str(row.get("expected_source", "")).lower()

    # Cartography / Vision questions
    if (
        "cartography" in source
        or "map" in applicable_to
        or "vision" in applicable_to
        or "cartography" in topic
    ):
        return "cartography"

    # SANSRS / CRS questions
    if (
        "sansrs" in source
        or "crs" in applicable_to
        or "spatial_reference" in topic
        or "spatial reference" in topic
    ):
        return "spatial_reference"

    # Governance questions
    if (
        "governance" in source
        or "governance" in topic
    ):
        return "governance"

    # Roads / Buildings / General data quality
    return "data_quality"


def get_result_score(result):
    """
    Support both the old retriever score
    and the new Hybrid RRF score.
    """

    if not result:
        return None

    return result.get(
        "rrf_score",
        result.get("score"),
    )


def evaluate_rag(csv_path, top_k=3):
    df = pd.read_csv(csv_path)

    details = []

    hit_at_1_count = 0
    hit_at_3_count = 0
    citation_count = 0

    for _, row in df.iterrows():

        question = row["question"]
        expected_source = str(row["expected_source"]).strip()
        expected_page = int(row["expected_page"])

        category = infer_category(row)

        results = retrieve_geosa_context(
            query=question,
            top_k=top_k,
            category=category,
        )

        top_result = results[0] if results else None

        hit_at_1 = False
        hit_at_3 = False

        # =================================================
        # Hit@1
        # =================================================

        if top_result:
            hit_at_1 = (
                top_result.get("source") == expected_source
                and int(top_result.get("page")) == expected_page
            )

        # =================================================
        # Hit@3
        # =================================================

        for result in results:

            if (
                result.get("source") == expected_source
                and int(result.get("page")) == expected_page
            ):
                hit_at_3 = True
                break

        # =================================================
        # Counters
        # =================================================

        if hit_at_1:
            hit_at_1_count += 1

        if hit_at_3:
            hit_at_3_count += 1

        # Citation Accuracy
        #
        # For the current benchmark, a correct citation means
        # the expected source + page appears in the retrieved
        # evidence set.
        if hit_at_3:
            citation_count += 1

        # =================================================
        # Details
        # =================================================

        details.append(
            {
                "question": question,
                "category": category,
                "expected_source": expected_source,
                "expected_page": expected_page,

                "retrieved_source": (
                    top_result.get("source")
                    if top_result
                    else None
                ),

                "retrieved_page": (
                    top_result.get("page")
                    if top_result
                    else None
                ),

                "retrieved_score": get_result_score(
                    top_result
                ),

                "hit_at_1": hit_at_1,
                "hit_at_3": hit_at_3,
            }
        )

    total = len(df)

    metrics = {
        "questions": total,

        "hit_at_1": (
            hit_at_1_count / total
            if total
            else 0
        ),

        "hit_at_3": (
            hit_at_3_count / total
            if total
            else 0
        ),

        "citation_accuracy": (
            citation_count / total
            if total
            else 0
        ),
    }

    details_df = pd.DataFrame(
        details
    )

    return metrics, details_df