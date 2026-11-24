"""Propietario, clave temporal y sesiones versionadas.

Revision ID: c4e8f1a2b9d7
Revises: 5ad66518e25c
Create Date: 2026-11-22
"""

from alembic import op
import sqlalchemy as sa

revision = "c4e8f1a2b9d7"
down_revision = "5ad66518e25c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column(
            "es_propietario",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "usuarios",
        sa.Column(
            "debe_cambiar_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "usuarios",
        sa.Column("password_temporal_expira_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "usuarios",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # El primer admin activo pasa a ser el propietario. Si no hay admins, no
    # se toca nada: el seed lo resuelve.
    op.execute(
        """
        UPDATE usuarios
        SET es_propietario = true
        WHERE id = (
            SELECT id FROM usuarios
            WHERE rol = 'admin' AND activo = true
            ORDER BY id
            LIMIT 1
        )
        """
    )

    # Los clientes existentes sin responsable quedan a cargo del propietario
    # (o del primer admin). Sólo la versión vigente: el historial no se altera.
    op.execute(
        """
        UPDATE cliente_versiones
        SET contador_id = (
            SELECT id FROM usuarios
            WHERE rol = 'admin' AND activo = true
            ORDER BY es_propietario DESC, id
            LIMIT 1
        )
        WHERE contador_id IS NULL
          AND id IN (
              SELECT MAX(id) FROM cliente_versiones GROUP BY cliente_id
          )
        """
    )


def downgrade() -> None:
    op.drop_column("usuarios", "token_version")
    op.drop_column("usuarios", "password_temporal_expira_en")
    op.drop_column("usuarios", "debe_cambiar_password")
    op.drop_column("usuarios", "es_propietario")
