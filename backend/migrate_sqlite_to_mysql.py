"""Copy existing SQLite rows into an empty MySQL database without deleting source data."""

from pathlib import Path

from sqlalchemy import MetaData, URL, Table, create_engine, insert, inspect, select

import models
from config import BASE_DIR
from database import Base, engine

SOURCE_DATABASE = BASE_DIR / "farmguardian.db"


def migrate() -> None:
    if not SOURCE_DATABASE.is_file():
        raise FileNotFoundError(f"SQLite source database does not exist: {SOURCE_DATABASE}")

    source_engine = create_engine(URL.create("sqlite", database=str(SOURCE_DATABASE)))
    copied = {}
    try:
        Base.metadata.create_all(bind=engine)
        tables = Base.metadata.sorted_tables

        with engine.connect() as target:
            populated = [
                table.name
                for table in tables
                if target.execute(select(table).limit(1)).first() is not None
            ]
        if populated:
            raise RuntimeError(
                "Target MySQL database must be empty before migration. Populated tables: "
                + ", ".join(populated)
            )

        source_inspector = inspect(source_engine)
        source_tables = set(source_inspector.get_table_names())
        with source_engine.connect() as source, engine.begin() as target:
            for table in tables:
                if table.name not in source_tables:
                    copied[table.name] = 0
                    continue

                source_columns = {
                    column["name"] for column in source_inspector.get_columns(table.name)
                }
                shared_columns = [
                    column.name for column in table.columns if column.name in source_columns
                ]
                source_table = Table(
                    table.name, MetaData(), autoload_with=source_engine
                )
                rows = source.execute(
                    select(*(source_table.c[name] for name in shared_columns))
                ).mappings().all()
                if rows:
                    target.execute(insert(table), [dict(row) for row in rows])
                copied[table.name] = len(rows)
    finally:
        source_engine.dispose()

    print("Migration finished; SQLite source was not changed.")
    for table_name, count in copied.items():
        if count:
            print(f"{table_name}: {count} rows")


if __name__ == "__main__":
    migrate()
