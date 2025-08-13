# pyright: reportMissingImports=false
"""
Synthetic dataset generator for MEMG evaluation.

Generates a JSONL dataset that exercises:
- All `EntityType` variants
- Multiple `MemoryType`s (document, note, conversation, task)
- Basic relationships (MENTIONS)

Usage:
  python scripts/generate_synthetic_dataset.py --output ./data/memg_synth.jsonl --num 200

The output can be consumed by `scripts/evaluate_memg.py`.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from random import Random
from typing import Iterable

# Local imports from installed/editable package
try:
    from memory_system.models.core import (
        Entity,
        EntityType,
        Memory,
        MemoryType,
        Relationship,
        RelationshipStrength,
    )
except Exception:
    # Allow running directly from repo without installing the package
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from memory_system.models.core import (
        Entity,
        EntityType,
        Memory,
        MemoryType,
        Relationship,
        RelationshipStrength,
    )


@dataclass
class DatasetRow:
    """Row stored to JSONL for portability across tools."""

    memory: Memory
    entities: list[Entity]
    relationships: list[Relationship]

    def to_serializable(self) -> dict:
        return {
            "memory": json.loads(self.memory.model_dump_json()),
            "entities": [json.loads(e.model_dump_json()) for e in self.entities],
            "relationships": [
                json.loads(r.model_dump_json()) for r in self.relationships
            ],
        }


def _generate_note_content(rng: Random, i: int) -> str:
    tech = rng.choice(["Python", "Docker", "PostgreSQL", "Qdrant", "Kuzu", "FastAPI"])
    component = rng.choice(["AuthService", "InvoiceService", "Retriever", "Processor"])
    issue = rng.choice(
        [
            "ModuleNotFoundError",
            "ConnectionTimeout",
            "NullPointer",
            "SchemaMismatch",
        ]
    )
    solution = rng.choice(
        [
            "pin dependency versions",
            "increase timeout",
            "add null checks",
            "migrate schema and reindex",
        ]
    )
    return (
        f"Note {i}: Using {tech} in component {component}. Encountered {issue}, "
        f"solution was to {solution}."
    )


def _generate_document_content(rng: Random, i: int) -> str:
    lib = rng.choice(["pydantic", "httpx", "uvicorn", "orjson", "tenacity"])
    protocol = rng.choice(["HTTP", "WebSocket", "gRPC"])
    config = rng.choice(["pyproject.toml", "docker-compose.yml", "requirements.txt"])
    return (
        f"Doc {i}: Architecture uses {protocol}. Library {lib} is required. "
        f"Configuration lives in {config}."
    )


def _generate_conversation(rng: Random, i: int) -> str:
    q = rng.choice(
        [
            "How do we fix the 500 error in search?",
            "Why is embedding dimension mismatched?",
            "Where is the MCP health endpoint?",
        ]
    )
    a = rng.choice(
        [
            "Check Qdrant payload schema and index rebuild.",
            "Set EMBEDDING_DIMENSION_LEN to 384 and re-embed.",
            "Use /health on port 8787 in Docker.",
        ]
    )
    return f"User: {q}\nAssistant: {a}"


def _generate_task(i: int) -> dict:
    # Minimal task fields stored within Memory as metadata
    status = ["backlog", "todo", "in_progress", "in_review", "done"][i % 5]
    priority = ["low", "medium", "high", "critical"][i % 4]
    due = datetime.now(UTC) + timedelta(days=(i % 14) - 7)
    return {
        "task_status": status,
        "task_priority": priority,
        "assignee": f"dev{i%3}@company.com",
        "due_date": due,
        "story_points": (i % 8) + 1,
    }


def _spawn_entities_for_content(
    user_id: str, content: str, rng: Random
) -> list[Entity]:
    entities: list[Entity] = []
    # Simple heuristics to cover all EntityType values over dataset
    mapping: list[tuple[str, EntityType]] = [
        ("Python", EntityType.TECHNOLOGY),
        ("Docker", EntityType.TOOL),
        ("PostgreSQL", EntityType.DATABASE),
        ("Qdrant", EntityType.DATABASE),
        ("Kuzu", EntityType.DATABASE),
        ("FastAPI", EntityType.LIBRARY),
        ("AuthService", EntityType.SERVICE),
        ("InvoiceService", EntityType.COMPONENT),
        ("Architecture", EntityType.ARCHITECTURE),
        ("HTTP", EntityType.PROTOCOL),
        ("ModuleNotFoundError", EntityType.ERROR),
        ("ConnectionTimeout", EntityType.ISSUE),
        ("SchemaMismatch", EntityType.ISSUE),
        ("solution", EntityType.SOLUTION),
        ("workaround", EntityType.WORKAROUND),
        ("configuration", EntityType.CONFIGURATION),
        ("requirements.txt", EntityType.FILE_TYPE),
        ("concept", EntityType.CONCEPT),
        ("method", EntityType.METHOD),
    ]
    for token, etype in mapping:
        if token.lower() in content.lower():
            entities.append(
                Entity(
                    user_id=user_id,
                    name=token,
                    type=etype,
                    description=f"Auto-extracted entity for token '{token}'",
                    context=content[:240],
                )
            )

    # Ensure at least one technology present
    if not any(e.type == EntityType.TECHNOLOGY for e in entities):
        entities.append(
            Entity(
                user_id=user_id,
                name=rng.choice(["Python", "Docker", "FastAPI"]),
                type=EntityType.TECHNOLOGY,
                description="Fallback technology",
                context=content[:240],
            )
        )
    return entities


def _make_relationships(
    user_id: str, memory: Memory, entities: list[Entity]
) -> list[Relationship]:
    rels: list[Relationship] = []
    for e in entities:
        rels.append(
            Relationship(
                user_id=user_id,
                source_id=memory.id,
                target_id=e.id,
                relationship_type="MENTIONS",
                strength=RelationshipStrength.MODERATE,
                source_memory_id=memory.id,
            )
        )
    return rels


def generate_rows(
    *, user_id: str, count: int, seed: int | None = None
) -> Iterable[DatasetRow]:
    rng = Random(seed)
    for i in range(count):
        # Cycle memory types to cover all variants
        mtype = [
            MemoryType.NOTE,
            MemoryType.DOCUMENT,
            MemoryType.CONVERSATION,
            MemoryType.TASK,
        ][i % 4]

        if mtype == MemoryType.NOTE:
            content = _generate_note_content(rng, i)
        elif mtype == MemoryType.DOCUMENT:
            content = _generate_document_content(rng, i)
        elif mtype == MemoryType.CONVERSATION:
            content = _generate_conversation(rng, i)
        else:
            content = _generate_note_content(rng, i)  # task uses note-like text

        memory = Memory(
            user_id=user_id, content=content, memory_type=mtype, title=f"Example {i}"
        )

        # Enrich task fields where applicable
        if mtype == MemoryType.TASK:
            task = _generate_task(i)
            memory.task_status = task["task_status"]  # type: ignore[attr-defined]
            memory.task_priority = task["task_priority"]  # type: ignore[attr-defined]
            memory.assignee = task["assignee"]  # type: ignore[attr-defined]
            memory.due_date = task["due_date"]  # type: ignore[attr-defined]
            memory.story_points = task["story_points"]  # type: ignore[attr-defined]

        entities = _spawn_entities_for_content(user_id, content, rng)
        relationships = _make_relationships(user_id, memory, entities)
        yield DatasetRow(memory=memory, entities=entities, relationships=relationships)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic MEMG dataset (JSONL)"
    )
    parser.add_argument("--output", required=True, help="Output JSONL path")
    parser.add_argument(
        "--num", type=int, default=200, help="Number of rows to generate"
    )
    parser.add_argument("--user", default="eval_user", help="User ID to stamp in data")
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = generate_rows(user_id=args.user, count=args.num, seed=args.seed)

    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row.to_serializable(), ensure_ascii=False) + "\n")

    print(f"Wrote {args.num} rows to {out_path}")


if __name__ == "__main__":
    main()
