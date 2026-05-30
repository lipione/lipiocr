from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_initial_schema(tmp_path: Path):
    db_path = tmp_path / "alembic.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    names = set(inspect(engine).get_table_names())
    assert {"cases", "documents", "audit_events", "ocr_blocks", "jobs"}.issubset(names)
