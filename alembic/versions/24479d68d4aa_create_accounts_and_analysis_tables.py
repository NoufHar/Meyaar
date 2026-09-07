"""create accounts and analysis tables

Revision ID: 24479d68d4aa
Revises:
Create Date: 2026-09-06 21:09:07.308470
"""

from typing import Sequence,Union

from alembic import op
import sqlalchemy as sa


revision:str="24479d68d4aa"
down_revision:Union[str,Sequence[str],None]=None
branch_labels:Union[str,Sequence[str],None]=None
depends_on:Union[str,Sequence[str],None]=None


def upgrade()->None:
    op.create_table(
        "users",
        sa.Column("id",sa.Integer(),nullable=False),
        sa.Column("name",sa.String(length=100),nullable=False),
        sa.Column("email",sa.String(length=255),nullable=False),
        sa.Column("password_hash",sa.String(length=255),nullable=False),
        sa.Column("role",sa.String(length=20),nullable=False),
        sa.Column("is_active",sa.Boolean(),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_users_email"),
        "users",
        ["email"],
        unique=True,
    )

    op.create_table(
        "analyses",
        sa.Column("id",sa.Integer(),nullable=False),
        sa.Column("user_id",sa.Integer(),nullable=False),
        sa.Column("run_id",sa.String(length=100),nullable=False),
        sa.Column("filename",sa.String(length=255),nullable=False),
        sa.Column("input_type",sa.String(length=20),nullable=False),
        sa.Column("layer_type",sa.String(length=100),nullable=True),
        sa.Column("status",sa.String(length=50),nullable=False),
        sa.Column("total_findings",sa.Integer(),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_analyses_run_id"),
        "analyses",
        ["run_id"],
        unique=True,
    )

    op.create_index(
        op.f("ix_analyses_user_id"),
        "analyses",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "findings",
        sa.Column("id",sa.Integer(),nullable=False),
        sa.Column("analysis_id",sa.Integer(),nullable=False),
        sa.Column("finding_id",sa.String(length=100),nullable=True),
        sa.Column("rule_id",sa.String(length=100),nullable=True),
        sa.Column("feature_id",sa.String(length=255),nullable=True),
        sa.Column("error_type",sa.String(length=100),nullable=False),
        sa.Column("severity",sa.String(length=50),nullable=True),
        sa.Column("status",sa.String(length=50),nullable=True),
        sa.Column("message",sa.Text(),nullable=True),
        sa.Column("recommendation",sa.Text(),nullable=True),
        sa.Column("confidence",sa.Float(),nullable=True),
        sa.Column("location",sa.JSON(),nullable=True),
        sa.Column("measurements",sa.JSON(),nullable=True),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_findings_analysis_id"),
        "findings",
        ["analysis_id"],
        unique=False,
    )

    op.create_table(
        "reports",
        sa.Column("id",sa.Integer(),nullable=False),
        sa.Column("analysis_id",sa.Integer(),nullable=False),
        sa.Column("report_path",sa.String(length=500),nullable=True),
        sa.Column("audio_path",sa.String(length=500),nullable=True),
        sa.Column("audio_text",sa.Text(),nullable=True),
        sa.Column("report_json",sa.JSON(),nullable=True),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_reports_analysis_id"),
        "reports",
        ["analysis_id"],
        unique=True,
    )


def downgrade()->None:
    op.drop_index(
        op.f("ix_reports_analysis_id"),
        table_name="reports",
    )
    op.drop_table("reports")

    op.drop_index(
        op.f("ix_findings_analysis_id"),
        table_name="findings",
    )
    op.drop_table("findings")

    op.drop_index(
        op.f("ix_analyses_user_id"),
        table_name="analyses",
    )
    op.drop_index(
        op.f("ix_analyses_run_id"),
        table_name="analyses",
    )
    op.drop_table("analyses")

    op.drop_index(
        op.f("ix_users_email"),
        table_name="users",
    )
    op.drop_table("users")