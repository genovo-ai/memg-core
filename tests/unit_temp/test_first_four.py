import os
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, UTC

import pytest
from typing import cast

# ---- Imports from core ----
from memg_core.core.models import Memory, SearchResult
from memg_core.core.exceptions import ValidationError
from memg_core.core.pipeline.indexer import add_memory_index
from memg_core.core.pipeline.retrieval import graph_rag_search
from memg_core.core.yaml_translator import create_memory_from_yaml, build_anchor_text
from memg_core.api.public import add_document, search as public_search
from memg_core.core.interfaces.qdrant import QdrantInterface
from memg_core.core.interfaces.kuzu import KuzuInterface
from memg_core.core.interfaces.embedder import Embedder


# ----------------------------- Fakes -----------------------------

class FakeEmbedder:
    def __init__(self, *_, **__):
        pass

    def get_embedding(self, text: str):
        # Deterministic dummy vector length 8 (Qdrant wrapper shouldn't enforce here in tests)
        return [0.1] * 8


class FakeQdrant:
    def __init__(self, collection_name: str = "memories", storage_path: str | None = None):
        self.collection_name = collection_name
        self.storage_path = storage_path
        self.points: dict[str, dict] = {}

    # collection mgmt
    def ensure_collection(self, collection: str | None = None, vector_size: int = 384):
        return True

    # upsert
    def add_point(self, vector, payload, point_id: str | None = None, collection: str | None = None):
        pid = point_id or f"p_{len(self.points)+1}"
        self.points[pid] = {"vector": vector, "payload": payload}
        return True, pid

    # search
    def search_points(self, vector, limit: int = 5, collection: str | None = None, user_id: str | None = None, filters: dict | None = None):
        # Fabricate two hits with descending scores
        results = []
        for i in range(2):
            pid = f"p{i+1}"
            results.append({
                "id": pid,
                "score": 1.0 - i * 0.1,
                "payload": {
                    "core": {
                        "user_id": user_id or "u",
                        "memory_type": filters.get("core.memory_type", "memo") if filters else "memo",
                        "created_at": datetime.now(UTC).isoformat(),
                        "is_valid": True,
                        "tags": ["t"],
                        "hrid": f"MEMO_AAA10{i}",  # make deterministic and usable in ordering tests
                    },
                    "entity": {
                        "statement": f"vector-hit-{i+1}",
                        "title": f"title-{i+1}",
                        "details": f"details-{i+1}",
                    },
                },
            })
        return results[:limit]

    def get_point(self, point_id: str, collection: str | None = None):
        rec = self.points.get(point_id)
        if not rec:
            return None
        return {"id": point_id, **rec}


class FakeKuzu:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str, str]] = []

    def add_node(self, table: str, properties: dict):
        _id = properties.get("id") or properties.get("uuid") or f"m_{len(self.nodes)+1}"
        self.nodes[_id] = properties

    def add_relationship(self, from_table: str, to_table: str, rel_type: str, from_id: str, to_id: str, props: dict | None = None):
        self.edges.append((from_id, to_id, rel_type))

    def query(self, cypher: str, params: dict | None = None):
        # Return a small set of rows mimicking Memory fields
        # Use params to gate by user_id/memo_type roughly
        mt = (params or {}).get("memo_type") or "memo"
        uid = (params or {}).get("user_id") or "u"
        rows = [
            {
                "m.id": f"g1",
                "m.user_id": uid,
                "m.memory_type": mt,
                "m.statement": "graph-candidate-1",
                "m.tags": ["g"],
                "m.created_at": datetime.now(UTC).isoformat(),
                "m.updated_at": datetime.now(UTC).isoformat(),
            },
            {
                "m.id": f"g2",
                "m.user_id": uid,
                "m.memory_type": mt,
                "m.statement": "graph-candidate-2",
                "m.tags": ["g"],
                "m.created_at": datetime.now(UTC).isoformat(),
                "m.updated_at": datetime.now(UTC).isoformat(),
            },
        ]
        return rows

    def neighbors(self, node_label: str, node_id: str, rel_types=None, direction: str = "any", limit: int = 5, neighbor_label: str | None = None):
        # Produce a single neighbor per seed
        return [
            {
                "id": f"n-{node_id}",
                "user_id": "u",
                "memory_type": "memo",
                "statement": f"neighbor-of-{node_id}",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]


# ----------------------------- Fixtures -----------------------------

@pytest.fixture()
def tmp_yaml(tmp_path: Path):
    y = tmp_path / "entities.yaml"
    y.write_text(
        """
version: 1
entities:
  - name: note
    anchor: statement
    fields:
      required: [statement]
  - name: document
    anchor: statement
    fields:
      required: [statement]
      optional: [details, title]
  - name: task
    anchor: statement
    fields:
      required: [statement]
      optional: [status, due_date]
""",
        encoding="utf-8",
    )
    os.environ["MEMG_YAML_SCHEMA"] = str(y)
    return y


# ----------------------------- Tests: YAML translator -----------------------------

def test_yaml_translator_anchor_and_validation(tmp_yaml):
    mem = create_memory_from_yaml("document", {"statement": "sum", "details": "body"}, user_id="u")
    assert mem.memory_type == "document"
    assert mem.payload["statement"] == "sum"
    # build anchor resolves to statement
    anchor = build_anchor_text(mem)
    assert anchor == "sum"


# ----------------------------- Tests: Indexer -----------------------------

def test_indexer_adds_to_both_stores(monkeypatch, tmp_yaml):
    # monkeypatch interfaces used by indexer caller
    from memg_core.core.pipeline import indexer as idx

    monkeypatch.setattr(idx, "Embedder", FakeEmbedder)
    monkeypatch.setattr(idx, "QdrantInterface", FakeQdrant)
    monkeypatch.setattr(idx, "KuzuInterface", FakeKuzu)

    m = Memory(
        memory_type="note",
        payload={"statement": "hello"},
        user_id="u",
        confidence=0.8,
        vector=None,
        is_valid=True,
        supersedes=None,
        superseded_by=None,
    )
    fq = FakeQdrant()
    fk = FakeKuzu()
    e = FakeEmbedder()

    pid = add_memory_index(m, cast(QdrantInterface, fq), cast(KuzuInterface, fk), cast(Embedder, e))
    assert pid in fq.points
    # Node mirrored
    assert any(v.get("statement") == "hello" for v in fk.nodes.values())

    # HRID should be set and present in Qdrant payload mirrored from Memory
    qp = fq.get_point(pid)
    assert qp is not None
    core = qp["payload"]["core"]
    assert isinstance(core.get("hrid"), str) and len(core["hrid"]) >= 7


# ----------------------------- Tests: Retrieval -----------------------------

def test_retrieval_vector_first(monkeypatch, tmp_yaml):
    q = cast(QdrantInterface, FakeQdrant())
    k = cast(KuzuInterface, FakeKuzu())
    e = cast(Embedder, FakeEmbedder())

    results = graph_rag_search(
        query="find",
        user_id="u",
        limit=5,
        qdrant=q,
        kuzu=k,
        embedder=e,
        filters=None,
        relation_names=None,
        neighbor_cap=1,
        memo_type=None,
        modified_within_days=None,
        mode="vector",
    )
    assert isinstance(results, list)
    assert all(isinstance(r, SearchResult) for r in results)
    # vector-first seeds then neighbors appended; top result from vector
    assert results[0].source in {"qdrant", "graph_neighbor"}

    if results:
        assert isinstance(results[0].memory.hrid, (str, type(None)))


def test_retrieval_graph_first(monkeypatch, tmp_yaml):
    q = cast(QdrantInterface, FakeQdrant())
    k = cast(KuzuInterface, FakeKuzu())
    e = cast(Embedder, FakeEmbedder())

    results = graph_rag_search(
        query=None,
        user_id="u",
        limit=3,
        qdrant=q,
        kuzu=k,
        embedder=e,
        filters=None,
        relation_names=["RELATED_TO"],
        neighbor_cap=1,
        memo_type="task",
        modified_within_days=7,
        mode="graph",
    )
    assert len(results) > 0
    assert all(r.memory.payload.get("statement") for r in results)


# ----------------------------- Tests: Public API -----------------------------

def test_public_add_document_normalizes_statement_and_details(monkeypatch, tmp_yaml):
    # patch public API dependencies
    import memg_core.api.public as pub

    monkeypatch.setattr(pub, "Embedder", FakeEmbedder)
    monkeypatch.setattr(pub, "QdrantInterface", FakeQdrant)
    monkeypatch.setattr(pub, "KuzuInterface", FakeKuzu)

    # config shim
    class _Cfg:
        def __init__(self):
            self.memg = SimpleNamespace(
                qdrant_collection_name="memories",
                kuzu_database_path="/tmp/kuzu",
            )

    monkeypatch.setattr(pub, "get_config", lambda: _Cfg())

    m = add_document("x" * 300, user_id="u")
    statement = str(m.payload.get("statement") or "")
    details = str(m.payload.get("details") or "")
    assert len(statement) <= 203
    assert details.startswith("x")


def test_public_search_validation(monkeypatch, tmp_yaml):
    import memg_core.api.public as pub

    with pytest.raises(ValidationError):
        pub.search(query=None, user_id="u")

    # Patch deps to allow a successful call
    monkeypatch.setattr(pub, "Embedder", FakeEmbedder)
    monkeypatch.setattr(pub, "QdrantInterface", FakeQdrant)
    monkeypatch.setattr(pub, "KuzuInterface", FakeKuzu)

    class _Cfg:
        def __init__(self):
            self.memg = SimpleNamespace(
                qdrant_collection_name="memories",
                kuzu_database_path="/tmp/kuzu",
            )

    monkeypatch.setattr(pub, "get_config", lambda: _Cfg())

    res = public_search(query="foo", user_id="u", limit=5)
    assert isinstance(res, list)
    if res:
        assert isinstance(res[0], SearchResult)

def test_retrieval_uses_hrid_for_ties(monkeypatch, tmp_yaml):
    # two vector hits with same score but different HRIDs → order by hrid_to_index
    class _Q(FakeQdrant):
        def search_points(self, vector, limit=5, collection=None, user_id=None, filters=None):
            def make_result(id_, hrid_):
                return {
                    "id": id_,
                    "score": 0.9,
                    "payload": {
                        "core": {
                            "user_id": user_id or "u",
                            "memory_type": "memo",
                            "created_at": datetime.now(UTC).isoformat(),
                            "is_valid": True,
                            "tags": ["t"],
                            "hrid": hrid_,
                        },
                        "entity": {"statement": "x"}
                    }
                }

            a = make_result("pA", "NOTE_AAA100")
            b = make_result("pB", "TASK_AAA050")
            return [a, b]

    q = _Q()
    k = FakeKuzu()
    e = FakeEmbedder()
    results = graph_rag_search(
        query="tie",
        user_id="u",
        limit=5,
        qdrant=q,
        kuzu=k,
        embedder=e,
        mode="vector",
    )
    assert [r.memory.hrid for r in results[:2]] == ["NOTE_AAA100", "TASK_AAA050"]


def test_neighbors_default_whitelist_applies(monkeypatch, tmp_yaml):
    # With relation_names=None, we should still get neighbor expansions (default whitelist)
    q = FakeQdrant()
    k = FakeKuzu()
    e = FakeEmbedder()

    res = graph_rag_search(
        query="find",
        user_id="u",
        limit=5,
        qdrant=q,
        kuzu=k,
        embedder=e,
        relation_names=None,  # intentionally None
        neighbor_cap=1,
        mode="vector",
    )
    assert isinstance(res, list)
    # Ensure at least one neighbor source present
    assert any(r.source == "graph_neighbor" for r in res)


def test_projection_prunes_payload_fields(monkeypatch, tmp_yaml):
    q = FakeQdrant()
    k = FakeKuzu()
    e = FakeEmbedder()

    # include_details="none" → only 'statement' stays
    res_none = graph_rag_search(
        query="find",
        user_id="u",
        limit=1,
        qdrant=q,
        kuzu=k,
        embedder=e,
        include_details="none",
        mode="vector",
    )
    assert res_none
    p0 = res_none[0].memory.payload
    assert set(p0.keys()) <= {"statement"}

    # include_details="self" with projection for type "memo" → keep 'title' (+ statement)
    res_proj = graph_rag_search(
        query="find",
        user_id="u",
        limit=1,
        qdrant=q,
        kuzu=k,
        embedder=e,
        include_details="self",
        projection={"memo": ["title"]},
        mode="vector",
    )
    assert res_proj
    p1 = res_proj[0].memory.payload
    # statement must remain; title should be present; details must be pruned
    assert "statement" in p1
    assert "title" in p1
    assert "details" not in p1


def test_public_api_projection_integration(monkeypatch, tmp_yaml):
    # Test that public API search() properly passes through projection controls
    import memg_core.api.public as pub

    # Patch dependencies
    monkeypatch.setattr(pub, "Embedder", FakeEmbedder)
    monkeypatch.setattr(pub, "QdrantInterface", FakeQdrant)
    monkeypatch.setattr(pub, "KuzuInterface", FakeKuzu)

    # config shim
    class _Cfg:
        def __init__(self):
            self.memg = SimpleNamespace(
                qdrant_collection_name="memories",
                kuzu_database_path="/tmp/kuzu",
            )

    monkeypatch.setattr(pub, "get_config", lambda: _Cfg())

    # Test default behavior (anchors-only)
    res_default = pub.search(query="test", user_id="u", limit=1)
    assert res_default
    p_default = res_default[0].memory.payload
    assert set(p_default.keys()) <= {"statement"}

    # Test include_details="self" with projection
    res_projected = pub.search(
        query="test",
        user_id="u",
        limit=1,
        include_details="self",
        projection={"memo": ["title"]}
    )
    assert res_projected
    p_projected = res_projected[0].memory.payload
    # Should have statement (always) + title (from projection), but not details
    assert "statement" in p_projected
    assert "title" in p_projected
    assert "details" not in p_projected
