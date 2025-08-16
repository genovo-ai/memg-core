from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from memg_core.api.public import add_memory
from memg_core.api.public import search as public_search
from memg_core.core.exceptions import ValidationError
from memg_core.core.interfaces.embedder import Embedder
from memg_core.core.interfaces.kuzu import KuzuInterface
from memg_core.core.interfaces.qdrant import QdrantInterface

# ---- Imports from core ----
from memg_core.core.models import Memory, SearchResult
from memg_core.core.pipeline.indexer import add_memory_index
from memg_core.core.pipeline.retrieval import graph_rag_search
from memg_core.core.yaml_translator import build_anchor_text, create_memory_from_yaml

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
    def add_point(
        self, vector, payload, point_id: str | None = None, collection: str | None = None
    ):
        pid = point_id or f"p_{len(self.points) + 1}"
        self.points[pid] = {"vector": vector, "payload": payload}
        return True, pid

    # search
    def search_points(
        self,
        vector,
        limit: int = 5,
        collection: str | None = None,
        user_id: str | None = None,
        filters: dict | None = None,
    ):
        # Fabricate two hits with descending scores
        results = []
        for i in range(2):
            pid = f"p{i + 1}"
            results.append(
                {
                    "id": pid,
                    "score": 1.0 - i * 0.1,
                    "payload": {
                        "core": {
                            "user_id": user_id or "u",
                            "memory_type": filters.get("core.memory_type", "memo")
                            if filters
                            else "memo",
                            "created_at": datetime.now(UTC).isoformat(),
                            "hrid": f"MEMO_AAA10{i}",  # make deterministic and usable in ordering tests
                        },
                        "entity": {
                            "statement": f"vector-hit-{i + 1}",  # Use content as anchor for memo_test
                            "details": f"details-{i + 1}",
                        },
                        # Flat mirrors for backward compatibility - retrieval still expects statement
                        "statement": f"vector-hit-{i + 1}",  # Use content as anchor for memo_test
                        "details": f"details-{i + 1}",
                    },
                }
            )
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
        _id = properties.get("id") or properties.get("uuid") or f"m_{len(self.nodes) + 1}"
        self.nodes[_id] = properties

    def add_relationship(
        self,
        from_table: str,
        to_table: str,
        rel_type: str,
        from_id: str,
        to_id: str,
        props: dict | None = None,
    ):
        self.edges.append((from_id, to_id, rel_type))

    def query(self, cypher: str, params: dict | None = None):
        # Return a small set of rows mimicking Memory fields
        # Use params to gate by user_id/memo_type roughly
        mt = (params or {}).get("memo_type") or "memo"
        uid = (params or {}).get("user_id") or "u"
        rows = [
            {
                "m.id": "g1",
                "m.user_id": uid,
                "m.memory_type": mt,
                "m.statement": "graph-candidate-1",  # Use statement as anchor
                # No hardcoded tags - removed as part of audit
                "m.created_at": datetime.now(UTC).isoformat(),
                "m.updated_at": datetime.now(UTC).isoformat(),
            },
            {
                "m.id": "g2",
                "m.user_id": uid,
                "m.memory_type": mt,
                "m.statement": "graph-candidate-2",  # Use statement as anchor
                # No hardcoded tags - removed as part of audit
                "m.created_at": datetime.now(UTC).isoformat(),
                "m.updated_at": datetime.now(UTC).isoformat(),
            },
        ]
        return rows

    def neighbors(
        self,
        node_label: str,
        node_id: str,
        rel_types=None,
        direction: str = "any",
        limit: int = 5,
        neighbor_label: str | None = None,
    ):
        # Produce a single neighbor per seed
        return [
            {
                "id": f"n-{node_id}",
                "user_id": "u",
                "memory_type": "memo",
                "statement": f"neighbor-of-{node_id}",  # Use statement as anchor
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]


# ----------------------------- Fixtures -----------------------------


# ----------------------------- Tests: YAML translator -----------------------------


def test_yaml_translator_anchor_and_validation():
    mem = create_memory_from_yaml("memo", {"statement": "sum"}, user_id="u")
    assert mem.statement == "sum"
    # build anchor resolves to statement for memo
    anchor = build_anchor_text(mem)
    assert anchor == "sum"


# ----------------------------- Tests: Indexer -----------------------------


def test_indexer_adds_to_both_stores(monkeypatch):
    # monkeypatch interfaces used by indexer caller
    from memg_core.core.pipeline import indexer as idx

    monkeypatch.setattr(idx, "Embedder", FakeEmbedder)
    monkeypatch.setattr(idx, "QdrantInterface", FakeQdrant)
    monkeypatch.setattr(idx, "KuzuInterface", FakeKuzu)

    m = Memory(
        memory_type="memo_test",
        payload={"statement": "hello", "details": "hello world"},
        user_id="u",
    )
    fq = FakeQdrant()
    fk = FakeKuzu()
    e = FakeEmbedder()

    pid = add_memory_index(
        m, cast("QdrantInterface", fq), cast("KuzuInterface", fk), cast("Embedder", e)
    )
    assert pid in fq.points
    # Node mirrored with YAML anchor text (now uses dynamic anchor field name)
    assert any(v.get("id") == m.id for v in fk.nodes.values())  # kuzu stores the memory node

    # HRID should be set and present in Qdrant payload mirrored from Memory
    qp = fq.get_point(pid)
    assert qp is not None
    core = qp["payload"]["core"]
    assert isinstance(core.get("hrid"), str) and len(core["hrid"]) >= 7


# ----------------------------- Tests: Retrieval -----------------------------


def test_retrieval_vector_first(monkeypatch):
    q = cast("QdrantInterface", FakeQdrant())
    k = cast("KuzuInterface", FakeKuzu())
    e = cast("Embedder", FakeEmbedder())

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


def test_retrieval_graph_first(monkeypatch):
    q = cast("QdrantInterface", FakeQdrant())
    k = cast("KuzuInterface", FakeKuzu())
    e = cast("Embedder", FakeEmbedder())

    results = graph_rag_search(
        query=None,
        user_id="u",
        limit=3,
        qdrant=q,
        kuzu=k,
        embedder=e,
        filters=None,
        relation_names=[],
        neighbor_cap=1,
        memo_type="memo_test",
        modified_within_days=7,
        mode="graph",
    )
    assert len(results) > 0
    # Results should have proper YAML-defined payload fields
    assert all(isinstance(r.memory.payload, dict) for r in results)


# ----------------------------- Tests: Public API -----------------------------


def test_public_add_memory_validates_memo_test_schema(monkeypatch):
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

    # Test strict YAML validation - memo_test must have required fields
    m = add_memory(
        "memo_test",
        {
            "statement": "Test memo_test summary",
            "details": "This is the full memo_test body content",
        },
        user_id="u",
    )

    assert m.statement == "Test memo_test summary"
    assert m.payload["details"] == "This is the full memo_test body content"
    assert m.memory_type == "memo_test"


def test_public_search_validation(monkeypatch):
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


def test_retrieval_uses_hrid_for_ties(monkeypatch):
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
                            "hrid": hrid_,
                        },
                        "entity": {"statement": "x", "details": "x"},
                    },
                }

            a = make_result("pA", "NOTE_AAA100")
            b = make_result("pB", "MEMO_AAA050")
            return [a, b]

    q = cast("QdrantInterface", _Q())
    k = cast("KuzuInterface", FakeKuzu())
    e = cast("Embedder", FakeEmbedder())
    results = graph_rag_search(
        query="tie",
        user_id="u",
        limit=5,
        qdrant=q,
        kuzu=k,
        embedder=e,
        mode="vector",
    )
    assert [r.memory.hrid for r in results[:2]] == ["MEMO_AAA050", "NOTE_AAA100"]


def test_neighbors_default_whitelist_applies(monkeypatch):
    # With relation_names=None, no neighbors should be added (no hardcoded defaults)
    q = cast("QdrantInterface", FakeQdrant())
    k = cast("KuzuInterface", FakeKuzu())
    e = cast("Embedder", FakeEmbedder())

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
    # With no relation names, no neighbors should be added
    assert not any(r.source == "graph_neighbor" for r in res)


def test_projection_prunes_payload_fields(monkeypatch):
    q = cast("QdrantInterface", FakeQdrant())
    k = cast("KuzuInterface", FakeKuzu())
    e = cast("Embedder", FakeEmbedder())

    # Create a memory to be returned by the search
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
    assert "details" not in p0
    assert "statement" in p0

    # include_details="self" with projection for type "memo" → keep 'title' (+ anchor field)
    res_proj = graph_rag_search(
        query="find",
        user_id="u",
        limit=1,
        qdrant=q,
        kuzu=k,
        embedder=e,
        include_details="self",
        projection={"memo": ["details"]},
        mode="vector",
    )
    assert res_proj
    p1 = res_proj[0].memory.payload
    # With projection, should have content (anchor) + title
    assert "statement" in p1  # anchor field always present
    assert "details" in p1


def test_public_api_projection_integration(monkeypatch):
    # Test that public API search() properly passes through projection controls
    import memg_core.api.public as pub

    # Patch dependencies
    monkeypatch.setattr(pub, "Embedder", FakeEmbedder)
    monkeypatch.setattr(pub, "KuzuInterface", FakeKuzu)

    # config shim
    class _Cfg:
        def __init__(self):
            self.memg = SimpleNamespace(
                qdrant_collection_name="memories",
                kuzu_database_path="/tmp/kuzu",
            )

    monkeypatch.setattr(pub, "get_config", lambda: _Cfg())

    # Create a FakeQdrant instance and populate it with a memory
    q = FakeQdrant()
    memory = Memory(
        id="p1",
        user_id="u",
        memory_type="memo",
        payload={"statement": "vector-hit-1", "details": "details-1"},
    )
    q.add_point(vector=[0.1] * 8, payload=memory.to_qdrant_payload(), point_id="p1")
    monkeypatch.setattr(pub, "QdrantInterface", lambda *args, **kwargs: q)

    # Test default behavior (include_details="self" - includes all fields)
    res_default = pub.search(query="test", user_id="u", limit=1, mode="vector")
    assert res_default
    p_default = res_default[0].memory.payload
    # Default now includes all fields from the fake memory
    expected_keys = {"statement", "details"}  # YAML-enforced fields
    assert expected_keys.issubset(set(p_default.keys()))

    # Test explicit include_details="none" (anchors-only)
    res_none = pub.search(query="test", user_id="u", limit=1, include_details="none", mode="vector")
    assert res_none
    p_none = res_none[0].memory.payload
    assert "details" not in p_none
    assert "statement" in p_none

    # Test include_details="self" with projection
    res_projected = pub.search(
        query="test",
        user_id="u",
        limit=1,
        include_details="self",
        projection={"memo": ["details"]},
        mode="vector",
    )
    assert res_projected
    p_projected = res_projected[0].memory.payload
    # Should have statement field (anchor) + details (from projection)
    assert "statement" in p_projected  # anchor field always present
    assert "details" in p_projected
