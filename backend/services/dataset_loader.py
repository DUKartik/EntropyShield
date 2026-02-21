"""
services/dataset_loader.py
==========================
Config-driven, chunked dataset ingestion for EntropyShield.

Design goals
------------
- Adding a new dataset = one new DatasetConfig entry in DATASET_REGISTRY.
- Constant peak RAM regardless of file size (chunked read + write).
- Stratified sampling (class imbalance) expressed declaratively, not inline.
- Idempotent: tables already containing data are skipped automatically.
- Deployment-friendly: dataset directory resolved via DATASET_DIR env-var
  with sensible fallbacks.
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from utils.debug_logger import get_logger

logger = get_logger()

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_dataset_dir() -> Path:
    """
    Return the directory that contains the raw CSV datasets.

    Priority:
      1. DATASET_DIR environment variable (absolute or relative to CWD)
      2. <project_root>/datasets   (project_root = 3 levels above this file)
      3. ../datasets               (relative to CWD — typical when running from backend/)
      4. datasets                  (CWD fallback)
    """
    env_override = os.getenv("DATASET_DIR")
    if env_override:
        p = Path(env_override)
        if p.is_dir():
            logger.info(f"Dataset dir from DATASET_DIR env: {p}")
            return p
        logger.warning(f"DATASET_DIR={env_override} does not exist — falling back.")

    # Derive project root: this file lives at backend/services/dataset_loader.py
    # so project root is three parents up.
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        project_root / "datasets",
        Path("../datasets"),
        Path("datasets"),
    ]
    for candidate in candidates:
        if candidate.is_dir():
            logger.info(f"Dataset dir resolved to: {candidate.resolve()}")
            return candidate.resolve()

    # Return best guess even if it doesn't exist; individual loaders will warn.
    best = candidates[0]
    logger.warning(f"No dataset directory found; using: {best}")
    return best


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------

@dataclass
class StratifiedConfig:
    """
    Describes how to create a class-balanced sample from an imbalanced dataset.

    Example: AML transactions where is_laundering=1 is rare.
      - label_column: "is_laundering"
      - positive_value: 1          # keep ALL these rows
      - max_clean_rows: 9000       # sample up to this many negative rows
    """
    label_column: str
    positive_value: Any              # value that marks the minority class
    max_clean_rows: int = 9000
    random_state: int = 42


@dataclass
class DatasetConfig:
    """
    Declarative description of a single CSV dataset.

    Fields
    ------
    filename        : CSV filename inside the datasets directory.
    table_name      : Destination SQLite table name.
    columns         : Optional explicit column names (replaces header row).
    read_rows       : Max rows to read from the CSV (None = full file).
    chunk_size      : Rows per chunk for reading + writing (memory control).
    if_exists       : SQLAlchemy behaviour: 'replace' or 'append'.
    stratify        : Optional stratified sampling config.
    pre_process     : Optional callable(df) -> df applied after reading,
                      before writing. Useful for type coercions, etc.
    """
    filename: str
    table_name: str
    columns: Optional[list[str]] = None
    read_rows: Optional[int] = None
    chunk_size: int = 10_000
    if_exists: str = "replace"
    stratify: Optional[StratifiedConfig] = None
    pre_process: Optional[Any] = None   # Callable[[pd.DataFrame], pd.DataFrame]


# ---------------------------------------------------------------------------
# Dataset registry — add new datasets here, touch nothing else
# ---------------------------------------------------------------------------

DATASET_REGISTRY: list[DatasetConfig] = [
    # ── GDPR articles ────────────────────────────────────────────────────────
    DatasetConfig(
        filename="gdpr_text.csv",
        table_name="gdpr_articles",
        chunk_size=5_000,
    ),

    # ── GDPR enforcement fines ───────────────────────────────────────────────
    DatasetConfig(
        filename="gdpr_violations.csv",
        table_name="gdpr_violations",
        chunk_size=5_000,
    ),

    # ── Financial transactions (2.97 GB) — stratified AML sample ─────────────
    # We read 100 k rows from the file then produce a balanced sample.
    # chunked writing keeps SQLite writes bounded to 10 k rows at a time.
    DatasetConfig(
        filename="LI-Medium_Trans.csv",
        table_name="financial_transactions",
        columns=[
            "timestamp", "from_bank", "from_account",
            "to_bank", "to_account",
            "amount_received", "receiving_currency",
            "amount_paid", "payment_currency",
            "payment_format", "is_laundering",
        ],
        read_rows=100_000,   # Scan first 100 k rows to find all positives
        chunk_size=10_000,
        stratify=StratifiedConfig(
            label_column="is_laundering",
            positive_value=1,
            max_clean_rows=9_000,
            random_state=42,
        ),
        pre_process=lambda df: df.drop(columns=["is_laundering"], errors="ignore"),
    ),

    # ── Bank account entity map ───────────────────────────────────────────────
    DatasetConfig(
        filename="LI-Medium_accounts.csv",
        table_name="bank_accounts",
        columns=["bank_name", "bank_id", "account_number", "entity_id", "entity_name"],
        read_rows=50_000,
        chunk_size=10_000,
    ),
]


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class DatasetLoader:
    """
    Orchestrates ingestion of all datasets defined in DATASET_REGISTRY.

    Usage (called once at startup):
        loader = DatasetLoader()
        loader.load_all(conn)        # conn: sqlite3.Connection
    """

    def __init__(self, dataset_dir: Optional[Path] = None) -> None:
        self.dataset_dir = dataset_dir or resolve_dataset_dir()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_all(self, conn: sqlite3.Connection) -> None:
        """Load every dataset defined in DATASET_REGISTRY."""
        logger.info(f"DatasetLoader: loading {len(DATASET_REGISTRY)} datasets...")
        loaded, skipped, failed = 0, 0, 0
        for cfg in DATASET_REGISTRY:
            if self._is_table_populated(conn, cfg.table_name):
                logger.info(f"  skip  {cfg.table_name} (already populated)")
                skipped += 1
                continue
            try:
                self.load_one(conn, cfg)
                loaded += 1
            except Exception as exc:
                logger.error(f"  FAIL  {cfg.table_name}: {exc}")
                failed += 1

        logger.info(
            f"DatasetLoader complete — loaded: {loaded}, "
            f"skipped: {skipped}, failed: {failed}"
        )

    def load_one(self, conn: sqlite3.Connection, cfg: DatasetConfig) -> None:
        """
        Ingest a single dataset described by *cfg*.

        Steps:
          1. Resolve and validate the CSV path.
          2. Read raw data (chunked or full, depending on stratification need).
          3. Apply optional stratified sampling.
          4. Apply optional pre_process hook.
          5. Write to SQLite in chunks.
        """
        csv_path = self.dataset_dir / cfg.filename
        if not csv_path.exists():
            logger.warning(f"  miss  {cfg.filename} — not found at {csv_path}")
            return

        logger.info(f"  load  {cfg.filename} → {cfg.table_name}")

        df = self._read(csv_path, cfg)

        if cfg.stratify:
            df = self._stratify(df, cfg.stratify)

        if cfg.pre_process:
            df = cfg.pre_process(df)

        self._write_chunks(df, conn, cfg)
        logger.info(f"        wrote {len(df):,} rows → {cfg.table_name}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_table_populated(conn: sqlite3.Connection, table: str) -> bool:
        """Return True if *table* exists and has at least one row."""
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            return cursor.fetchone()[0] > 0
        except sqlite3.OperationalError:
            return False

    @staticmethod
    def _read(csv_path: Path, cfg: DatasetConfig) -> pd.DataFrame:
        """
        Read the CSV into a single DataFrame.

        For files that need stratified sampling we must have the full
        candidate pool in memory first (100 k rows max).  For plain
        files we also read fully but respect `read_rows`.

        Memory note: even 100 k rows of the transactions file is ~40 MB —
        acceptable.  The chunking during *writing* is what keeps SQLite I/O
        bounded.
        """
        read_kwargs: dict[str, Any] = {}
        if cfg.read_rows is not None:
            read_kwargs["nrows"] = cfg.read_rows
        if cfg.columns is not None:
            read_kwargs["names"] = cfg.columns
            read_kwargs["header"] = 0   # skip the original header row

        return pd.read_csv(csv_path, **read_kwargs)

    @staticmethod
    def _stratify(df: pd.DataFrame, cfg: StratifiedConfig) -> pd.DataFrame:
        """
        Produce a balanced sample:
          - ALL minority (positive) rows
          - Up to `max_clean_rows` majority (negative) rows, randomly sampled
          - Shuffled result with fixed random seed for reproducibility
        """
        positives = df[df[cfg.label_column] == cfg.positive_value]
        negatives = df[df[cfg.label_column] != cfg.positive_value]

        n_clean = min(cfg.max_clean_rows, len(negatives))
        sampled_negatives = negatives.sample(n=n_clean, random_state=cfg.random_state)

        result = (
            pd.concat([positives, sampled_negatives])
            .sample(frac=1, random_state=cfg.random_state)
            .reset_index(drop=True)
        )
        logger.info(
            f"        stratify: {len(positives):,} positives + "
            f"{len(sampled_negatives):,} negatives = {len(result):,} total"
        )
        return result

    @staticmethod
    def _write_chunks(
        df: pd.DataFrame,
        conn: sqlite3.Connection,
        cfg: DatasetConfig,
    ) -> None:
        """
        Write *df* to SQLite in chunks of `cfg.chunk_size` rows.

        Using pandas + sqlite3 connection directly (no SQLAlchemy overhead
        for bulk inserts).  The first chunk uses `if_exists=cfg.if_exists`
        (typically 'replace') so the table is created/reset; subsequent
        chunks always append.
        """
        total = len(df)
        start = 0
        first_chunk = True
        while start < total:
            end = min(start + cfg.chunk_size, total)
            chunk = df.iloc[start:end]
            mode = cfg.if_exists if first_chunk else "append"
            chunk.to_sql(cfg.table_name, conn, if_exists=mode, index=False)
            first_chunk = False
            start = end
