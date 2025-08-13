"""
Evaluation runner for MEMG using a synthetic (or real) JSONL dataset.

Two modes:
1) Offline validation-only: Validate models and schema compatibility without DB/AI calls
   python scripts/evaluate_memg.py --data ./data/memg_synth.jsonl --mode offline

2) Live processing (requires env + services):
   - Embeds + writes to Qdrant and Kuzu using UnifiedMemoryProcessor
   - Validates pipeline with `PipelineValidator`
   python scripts/evaluate_memg.py --data ./data/memg_synth.jsonl --mode live
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# pyright: reportMissingImports=false
try:
    from memory_system.models.core import Entity, Memory, Relationship
    from memory_system.processing.unified_memory_processor import UnifiedMemoryProcessor
    from memory_system.validation.pipeline_validator import PipelineValidator
except Exception:
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))
    from memory_system.models.core import Entity, Memory, Relationship
    from memory_system.processing.unified_memory_processor import UnifiedMemoryProcessor
    from memory_system.validation.pipeline_validator import PipelineValidator


@dataclass
class EvalStats:
    rows: int = 0
    memories: int = 0
    entities: int = 0
    relationships: int = 0
    errors: int = 0
    warnings: int = 0
    duration_s: float = 0.0


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            yield json.loads(line)


def to_models(row: dict) -> tuple[Memory, list[Entity], list[Relationship]]:
    memory = Memory(**row["memory"])  # type: ignore[arg-type]
    entities = [Entity(**e) for e in row.get("entities", [])]
    relationships = [Relationship(**r) for r in row.get("relationships", [])]
    return memory, entities, relationships


def evaluate_offline(data_path: Path) -> EvalStats:
    validator = PipelineValidator()
    stats = EvalStats()
    start = time.time()

    for row in read_jsonl(data_path):
        memory, _e, _r = to_models(row)

        # Validate database compatibility for each object
        mem_q = validator.schema_validator.validate_database_compatibility(
            memory, "qdrant"
        )
        mem_k = validator.schema_validator.validate_database_compatibility(
            memory, "kuzu"
        )
        for ent in _e:
            _ = validator.schema_validator.validate_database_compatibility(ent, "kuzu")
        for rel in _r:
            _ = validator.schema_validator.validate_relationship_schema(
                rel.to_kuzu_props()
            )

        # Accumulate counts
        stats.rows += 1
        stats.memories += 1
        stats.entities += len(_e)
        stats.relationships += len(_r)
        stats.errors += sum(
            1 for i in mem_q.issues if i.level.name in ("ERROR", "CRITICAL")
        )
        stats.errors += sum(
            1 for i in mem_k.issues if i.level.name in ("ERROR", "CRITICAL")
        )
        stats.warnings += sum(1 for i in mem_q.issues if i.level.name == "WARNING")
        stats.warnings += sum(1 for i in mem_k.issues if i.level.name == "WARNING")

    stats.duration_s = time.time() - start
    return stats


def evaluate_live(data_path: Path) -> EvalStats:
    """Live path: run through UnifiedMemoryProcessor for embeddings + storage.

    Requires environment configured (GOOGLE_API_KEY, Qdrant, Kuzu). The dataset content
    is already structured; we pass it through the processor as-is for embedding and storage,
    while still validating with PipelineValidator. We do not perform actual retrieval here.
    """
    processor = UnifiedMemoryProcessor()
    validator = PipelineValidator()
    stats = EvalStats()
    start = time.time()

    for row in read_jsonl(data_path):
        memory, _entities, _relationships = to_models(row)

        # Build a minimal CreateMemoryRequest-like dict to reuse processor API
        # Import locally to avoid heavy import at module import time
        try:
            from memory_system.models.api import CreateMemoryRequest
        except Exception:
            import sys as _sys2
            from pathlib import Path as _Path2

            _sys2.path.insert(0, str(_Path2(__file__).resolve().parents[1] / "src"))
            from memory_system.models.api import CreateMemoryRequest

        req = CreateMemoryRequest(
            user_id=memory.user_id,
            content=memory.content,
            memory_type=memory.memory_type,
            title=memory.title,
            tags=memory.tags,
            project_id=memory.project_id,
            project_name=memory.project_name,
        )

        result = processor.process_memory.__wrapped__(processor, req)  # type: ignore[attr-defined]
        # The method is async; if an event loop is needed, fall back to running it.
        if hasattr(result, "__await__"):
            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                processor.process_memory(req)
            )

        # Validate stored memory objects quickly (vector len checks etc.)
        val_report = validator.validate_memory_creation_flow(
            content=memory.content,
            ai_analysis={"dummy": True},
            ai_extraction={"dummy": True},
            final_memories=[result.memory] if hasattr(result, "memory") else [],
        )

        stats.rows += 1
        stats.memories += 1
        # In live mode we validate creation flow; entities/relationships from dataset are not used
        stats.errors += val_report.error_count
        stats.warnings += val_report.warning_count

    stats.duration_s = time.time() - start
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate MEMG with a dataset")
    parser.add_argument("--data", required=True, help="Path to JSONL dataset")
    parser.add_argument(
        "--mode",
        choices=["offline", "live"],
        default="offline",
        help="offline: schema/db-only, live: full processing (embeddings + storage)",
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise SystemExit(f"Dataset not found: {data_path}")

    if args.mode == "offline":
        stats = evaluate_offline(data_path)
    else:
        stats = evaluate_live(data_path)

    print(
        (
            f"Rows={stats.rows} | Memories={stats.memories} | Entities={stats.entities} | "
            f"Relationships={stats.relationships} | Errors={stats.errors} | "
            f"Warnings={stats.warnings} | Duration={stats.duration_s:.2f}s"
        )
    )


if __name__ == "__main__":
    main()
