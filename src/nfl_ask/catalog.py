"""What the model knows about the data: the served tables, their columns, and their definitions.

Built from what the project already documents, so there is one source of truth:
- each mart's description and column notes, from dbt_project/models/marts/marts.yml
- the definitions written at the top of each mart's SQL (e.g. cap share and "worth it")
- the columns and types actually served, from the serving database

Only served tables are described: a mart the model can't query must not be offered to it.
"""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MARTS_DIR = Path("dbt_project") / "models" / "marts"

NOTES = {
    "_publications": "When each table was last published to this database, and how many rows it has.",
}


def sql_header(sql_path: Path) -> str:
    """The comment block at the top of a mart's SQL file, without the `-- ` markers."""
    lines = []
    for line in sql_path.read_text().splitlines():
        if not line.startswith("--"):
            break
        lines.append(line[2:].strip())
    return "\n".join(lines).strip()


def catalog_text(columns: dict[str, list[tuple[str, str]]], project_root: Path = PROJECT_ROOT) -> str:
    """`columns` maps each served table to its (column, type) pairs, in order."""
    models = {}
    for path in sorted((project_root / MARTS_DIR).glob("*.yml")):
        for model in yaml.safe_load(path.read_text()).get("models", []):
            models[model["name"]] = model

    sections = []
    for table, table_columns in sorted(columns.items()):
        model = models.get(table, {})
        notes = {c["name"]: " ".join(c.get("description", "").split()) for c in model.get("columns", [])}
        lines = [f"## {table}"]
        description = " ".join(model.get("description", NOTES.get(table, "")).split())
        if description:
            lines.append(description)
        sql_path = project_root / MARTS_DIR / f"{table}.sql"
        if sql_path.exists() and (header := sql_header(sql_path)):
            lines += ["Definitions:", header]
        lines.append("Columns:")
        for name, data_type in table_columns:
            note = notes.get(name)
            lines.append(f"- {name} {data_type}" + (f": {note}" if note else ""))
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def served_columns(conn) -> list[tuple[str, str, str]]:
    """Every served table's columns, in order: (table, column, type)."""
    return [tuple(row) for row in conn.execute(
        "select table_name, column_name, data_type from information_schema.columns"
        " where table_schema = 'marts' order by table_name, ordinal_position"
    ).fetchall()]


def grouped(rows: list[tuple[str, str, str]]) -> dict[str, list[tuple[str, str]]]:
    columns: dict[str, list[tuple[str, str]]] = {}
    for table, column, data_type in rows:
        columns.setdefault(table, []).append((column, data_type))
    return columns


def build_catalog(conn, project_root: Path = PROJECT_ROOT) -> str:
    """The catalog for the tables currently served (read from the serving database)."""
    return catalog_text(grouped(served_columns(conn)), project_root)


class LiveCatalog:
    """The catalog, kept in step with the database: each question checks the served columns
    (one small query) and the text is rebuilt only when they changed, such as a new mart's
    first publish. Unchanged, it's the same text, so the model's prompt cache still hits."""

    def __init__(self, project_root: Path = PROJECT_ROOT):
        self.project_root, self.rows, self.text = project_root, None, ""

    def __call__(self, conn) -> str:
        rows = served_columns(conn)
        if rows != self.rows:
            self.text, self.rows = catalog_text(grouped(rows), self.project_root), rows
        return self.text
