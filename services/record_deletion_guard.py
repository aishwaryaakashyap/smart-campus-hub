from sqlalchemy import MetaData, Table, func, inspect, select

from extensions import db


def find_referencing_records(target_table_name, record_id, exclude_tables=None):
    """
    Count all direct foreign-key references to a record.

    Database inspection errors are allowed to propagate. A failed
    inspection must never be treated as permission to delete.
    """
    excluded = set(exclude_tables or ())
    inspector = inspect(db.engine)
    metadata = MetaData()
    table_cache = {}
    checked_columns = set()
    references = []

    for table_name in inspector.get_table_names():
        if table_name in excluded:
            continue

        for foreign_key in inspector.get_foreign_keys(table_name):
            if foreign_key.get("referred_table") != target_table_name:
                continue

            local_columns = foreign_key.get("constrained_columns") or []
            remote_columns = foreign_key.get("referred_columns") or []

            for local_column, remote_column in zip(
                local_columns,
                remote_columns
            ):
                if remote_column != "id":
                    continue

                key = (table_name, local_column)

                if key in checked_columns:
                    continue

                checked_columns.add(key)

                if table_name not in table_cache:
                    table_cache[table_name] = Table(
                        table_name,
                        metadata,
                        autoload_with=db.engine
                    )

                table = table_cache[table_name]

                count = db.session.execute(
                    select(func.count())
                    .select_from(table)
                    .where(table.c[local_column] == record_id)
                ).scalar_one()

                if count:
                    references.append({
                        "table": table_name,
                        "column": local_column,
                        "count": int(count)
                    })

    return references
