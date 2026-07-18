"""Tests for QdrantService, mocking the underlying AsyncQdrantClient."""

from types import SimpleNamespace

from qdrant_client.http.models import MatchAny, MatchValue, PointIdsList

from knowledge_mcp.qdrant import str_to_uuid


def test_str_to_uuid_is_deterministic():
    assert str_to_uuid("k-abc123") == str_to_uuid("k-abc123")


def test_str_to_uuid_differs_per_input():
    assert str_to_uuid("k-abc123") != str_to_uuid("k-xyz789")


class TestBuildFilter:
    def test_empty_filters_returns_none(self, qdrant_service):
        assert qdrant_service._build_filter({}) is None

    def test_scalar_value_uses_match_value(self, qdrant_service):
        result = qdrant_service._build_filter({"knowledge_type": "note"})
        assert len(result.must) == 1
        assert result.must[0].key == "knowledge_type"
        assert isinstance(result.must[0].match, MatchValue)
        assert result.must[0].match.value == "note"

    def test_list_value_uses_match_any(self, qdrant_service):
        result = qdrant_service._build_filter({"status": ["active", "planned"]})
        assert isinstance(result.must[0].match, MatchAny)
        assert result.must[0].match.any == ["active", "planned"]

    def test_tags_expand_to_and_logic(self, qdrant_service):
        result = qdrant_service._build_filter({"tags": ["python", "mcp"]})
        assert len(result.must) == 2
        assert all(c.key == "tags" for c in result.must)
        assert [c.match.any for c in result.must] == [["python"], ["mcp"]]


class TestEnsureCollections:
    async def test_creates_missing_collections_with_indexes(
        self, qdrant_service, mock_qdrant_client
    ):
        mock_qdrant_client.get_collections.return_value = SimpleNamespace(collections=[])

        await qdrant_service.ensure_collections()

        created = {
            call.kwargs["collection_name"]
            for call in mock_qdrant_client.create_collection.await_args_list
        }
        assert created == {"knowledge", "skills", "projects", "private"}

        indexed_fields = [
            (call.kwargs["collection_name"], call.kwargs["field_name"])
            for call in mock_qdrant_client.create_payload_index.await_args_list
        ]
        assert ("knowledge", "tags") in indexed_fields
        assert ("knowledge", "knowledge_type") in indexed_fields
        assert ("skills", "name") in indexed_fields
        assert ("projects", "name") in indexed_fields
        assert ("projects", "status") in indexed_fields
        assert ("private", "private_type") in indexed_fields

    async def test_skips_existing_collections(self, qdrant_service, mock_qdrant_client):
        mock_qdrant_client.get_collections.return_value = SimpleNamespace(
            collections=[
                SimpleNamespace(name="knowledge"),
                SimpleNamespace(name="skills"),
                SimpleNamespace(name="projects"),
                SimpleNamespace(name="private"),
            ]
        )

        await qdrant_service.ensure_collections()

        mock_qdrant_client.create_collection.assert_not_awaited()
        mock_qdrant_client.create_payload_index.assert_not_awaited()


class TestSearch:
    async def test_returns_payload_with_score(self, qdrant_service, mock_qdrant_client):
        mock_qdrant_client.query_points.return_value = SimpleNamespace(
            points=[
                SimpleNamespace(payload={"title": "A"}, score=0.9),
                SimpleNamespace(payload={"title": "B"}, score=0.5),
            ]
        )

        results = await qdrant_service.search(collection="knowledge", vector=[0.1, 0.2])

        assert results == [
            {"title": "A", "score": 0.9},
            {"title": "B", "score": 0.5},
        ]

    async def test_handles_missing_payload(self, qdrant_service, mock_qdrant_client):
        mock_qdrant_client.query_points.return_value = SimpleNamespace(
            points=[SimpleNamespace(payload=None, score=0.4)]
        )

        results = await qdrant_service.search(collection="knowledge", vector=[0.1])
        assert results == [{"score": 0.4}]


class TestUpsert:
    async def test_with_vector_upserts_point(self, qdrant_service, mock_qdrant_client):
        await qdrant_service.upsert(
            collection="knowledge", id="k-abc", vector=[0.1, 0.2], payload={"title": "T"}
        )

        mock_qdrant_client.upsert.assert_awaited_once()
        kwargs = mock_qdrant_client.upsert.await_args.kwargs
        assert kwargs["collection_name"] == "knowledge"
        point = kwargs["points"][0]
        assert point.id == str_to_uuid("k-abc")
        assert point.vector == [0.1, 0.2]
        assert point.payload == {"title": "T"}
        mock_qdrant_client.set_payload.assert_not_awaited()

    async def test_without_vector_update_sets_payload_only(
        self, qdrant_service, mock_qdrant_client
    ):
        await qdrant_service.upsert(
            collection="knowledge",
            id="k-abc",
            vector=None,
            payload={"title": "T"},
            update_vector=False,
        )

        mock_qdrant_client.set_payload.assert_awaited_once()
        kwargs = mock_qdrant_client.set_payload.await_args.kwargs
        assert kwargs["payload"] == {"title": "T"}
        assert kwargs["points"] == [str_to_uuid("k-abc")]
        mock_qdrant_client.upsert.assert_not_awaited()


class TestGetById:
    async def test_returns_payload_when_found(self, qdrant_service, mock_qdrant_client):
        mock_qdrant_client.retrieve.return_value = [SimpleNamespace(payload={"title": "T"})]

        result = await qdrant_service.get_by_id(collection="knowledge", id="k-abc")
        assert result == {"title": "T"}

    async def test_returns_none_when_not_found(self, qdrant_service, mock_qdrant_client):
        mock_qdrant_client.retrieve.return_value = []
        assert await qdrant_service.get_by_id(collection="knowledge", id="k-missing") is None

    async def test_returns_none_on_client_error(self, qdrant_service, mock_qdrant_client):
        mock_qdrant_client.retrieve.side_effect = RuntimeError("boom")
        assert await qdrant_service.get_by_id(collection="knowledge", id="k-abc") is None


class TestGetByField:
    async def test_returns_first_match(self, qdrant_service, mock_qdrant_client):
        mock_qdrant_client.scroll.return_value = ([SimpleNamespace(payload={"name": "x"})], None)
        result = await qdrant_service.get_by_field("skills", "name", "x")
        assert result == {"name": "x"}

    async def test_returns_none_when_no_match(self, qdrant_service, mock_qdrant_client):
        mock_qdrant_client.scroll.return_value = ([], None)
        assert await qdrant_service.get_by_field("skills", "name", "missing") is None


class TestDelete:
    async def test_deletes_by_converted_id(self, qdrant_service, mock_qdrant_client):
        await qdrant_service.delete(collection="knowledge", id="k-abc")

        kwargs = mock_qdrant_client.delete.await_args.kwargs
        assert kwargs["collection_name"] == "knowledge"
        selector = kwargs["points_selector"]
        assert isinstance(selector, PointIdsList)
        assert selector.points == [str_to_uuid("k-abc")]


class TestListAll:
    async def test_returns_results_and_total(self, qdrant_service, mock_qdrant_client):
        mock_qdrant_client.count.return_value = SimpleNamespace(count=42)
        mock_qdrant_client.scroll.return_value = (
            [SimpleNamespace(payload={"title": "A"}), SimpleNamespace(payload={"title": "B"})],
            None,
        )

        results, total = await qdrant_service.list_all(collection="knowledge", limit=2, offset=0)

        assert total == 42
        assert results == [{"title": "A"}, {"title": "B"}]
