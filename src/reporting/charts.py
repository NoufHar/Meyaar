from pathlib import Path

import plotly.graph_objects as go


# ============================================================
# MEYAAR COLORS
# ============================================================

NAVY = "#062B4F"
TEAL = "#14B8A6"
DARK_TEAL = "#0F8F83"
TEXT = "#243447"
MUTED = "#6B7C8F"
GRID = "#E5ECEF"
WHITE = "#FFFFFF"


RULE_TO_DIMENSION = {
    "RD001": "Logical Consistency",
    "RD002": "Logical Consistency",
    "RD003": "Logical Consistency",
    "RD004": "Logical Consistency",
    "RD005": "Completeness",

    "BLD001": "Logical Consistency",
    "BLD002": "Logical Consistency",
    "BLD003": "Logical Consistency",
    "BLD004": "Completeness",

    "GIS001": "Spatial Reference",
    "GIS002": "Spatial Validity",
    "GIS003": "Completeness",
    "GIS004": "Attribute Quality",
    "GIS005": "Attribute Quality",
}


# ============================================================
# THEME
# ============================================================

def apply_meyaar_theme(
    fig,
    labels,
    values,
):
    longest_label = max(
        (
            len(str(label))
            for label in labels
        ),
        default=20,
    )

    left_margin = min(
        max(
            90,
            longest_label * 5,
        ),
        220,
    )

    largest_value = max(
        values,
        default=0,
    )

    digits = len(
        f"{largest_value:,}"
    )

    right_margin = min(
        max(
            80,
            digits * 12,
        ),
        150,
    )

    fig.update_layout(
        paper_bgcolor=WHITE,
        plot_bgcolor=WHITE,
        font=dict(
            family="Arial",
            color=TEXT,
            size=13,
        ),
        margin=dict(
            l=left_margin,
            r=right_margin,
            t=80,
            b=60,
        ),
        showlegend=False,
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor=GRID,
        zeroline=False,
        automargin=True,
        tickfont=dict(
            color=MUTED,
        ),
    )

    fig.update_yaxes(
        showgrid=False,
        automargin=True,
        tickfont=dict(
            color=TEXT,
        ),
    )


# ============================================================
# RULE CHART
# ============================================================

def create_findings_by_rule_chart(
    validation,
    output_path,
):
    summary = validation.get(
        "summary",
        [],
    )

    if not summary:
        return None

    rows = sorted(
        summary,
        key=lambda row: row[
            "findings"
        ],
    )

    labels = [
        (
            f"{row['rule_id']} · "
            f"{row['finding_type']}"
        )
        for row in rows
    ]

    values = [
        row["findings"]
        for row in rows
    ]

    colors = [
        TEAL
        if index % 2 == 0
        else DARK_TEAL
        for index in range(
            len(rows)
        )
    ]

    max_value = max(
        values,
        default=1,
    )

    chart_height = max(
        340,
        95 * len(rows),
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(
                color=colors,
            ),
            text=[
                f"{value:,}"
                for value in values
            ],
            textposition="outside",
            cliponaxis=False,
            textfont=dict(
                color=NAVY,
                size=13,
            ),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Candidate Findings: "
                "%{x:,}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=dict(
            text=(
                "Candidate Findings "
                "by Validation Rule"
            ),
            font=dict(
                color=NAVY,
                size=20,
            ),
            x=0,
        ),
        width=1000,
        height=chart_height,
        bargap=0.35,
    )

    fig.update_xaxes(
        title="Candidate Findings",
        range=[
            0,
            max_value * 1.18,
        ],
    )

    apply_meyaar_theme(
        fig,
        labels,
        values,
    )

    output_path = Path(
        output_path
    ).resolve()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fig.write_image(
        str(output_path),
        width=1000,
        height=chart_height,
        scale=2,
    )

    return str(
        output_path
    )


# ============================================================
# QUALITY DIMENSION CHART
# ============================================================

def create_quality_dimension_chart(
    validation,
    output_path,
):
    summary = validation.get(
        "summary",
        [],
    )

    if not summary:
        return None

    dimensions = {}

    for row in summary:
        dimension = (
            RULE_TO_DIMENSION.get(
                row["rule_id"],
                "Other",
            )
        )

        dimensions[dimension] = (
            dimensions.get(
                dimension,
                0,
            )
            + row["findings"]
        )

    # A one-bar chart adds no value
    if len(dimensions) <= 1:
        return None

    rows = sorted(
        dimensions.items(),
        key=lambda item: item[1],
    )

    labels = [
        item[0]
        for item in rows
    ]

    values = [
        item[1]
        for item in rows
    ]

    max_value = max(
        values,
        default=1,
    )

    chart_height = max(
        340,
        95 * len(rows),
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(
                color=TEAL,
            ),
            text=[
                f"{value:,}"
                for value in values
            ],
            textposition="outside",
            cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Candidate Findings: "
                "%{x:,}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=dict(
            text=(
                "Candidate Findings "
                "by Quality Dimension"
            ),
            font=dict(
                color=NAVY,
                size=20,
            ),
            x=0,
        ),
        width=1000,
        height=chart_height,
        bargap=0.35,
    )

    fig.update_xaxes(
        title="Candidate Findings",
        range=[
            0,
            max_value * 1.18,
        ],
    )

    apply_meyaar_theme(
        fig,
        labels,
        values,
    )

    output_path = Path(
        output_path
    ).resolve()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fig.write_image(
        str(output_path),
        width=1000,
        height=chart_height,
        scale=2,
    )

    return str(
        output_path
    )