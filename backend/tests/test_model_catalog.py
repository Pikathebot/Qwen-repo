import json

import pytest
from fastapi.testclient import TestClient

from app.agent.model_catalog import ModelCatalog
from app.main import app


def _gguf(path, size=1024):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)
    return path


@pytest.fixture
def models_dir(tmp_path):
    """A models/ tree shaped like the real one: two top-level GGUFs plus a vendor download
    subdirectory holding a duplicate and a multimodal projector."""
    root = tmp_path / "models"
    _gguf(root / "Qwen3.5-9B-UD-Q3_K_XL.gguf", 5000)
    _gguf(root / "Qwen3.5-4B-UD-Q4_K_XL.gguf", 3000)
    _gguf(root / "unsloth" / "Qwen3.5-4B-MTP-GGUF" / "Qwen3.5-4B-UD-Q4_K_XL.gguf", 3100)
    _gguf(root / "unsloth" / "Qwen3.5-4B-MTP-GGUF" / "mmproj-F32.gguf", 1300)
    return root


@pytest.fixture
def catalog(models_dir, tmp_path):
    return ModelCatalog(models_dir=models_dir, state_path=tmp_path / "models.json")


def test_discover_lists_only_chat_models(catalog):
    ids = [m.id for m in catalog.discover()]
    assert not any("mmproj" in model_id for model_id in ids)
    assert len(ids) == 3


def test_projectors_are_reported_separately(catalog):
    projectors = catalog.projectors()
    assert len(projectors) == 1
    assert projectors[0].name == "mmproj-F32"


def test_top_level_models_are_recommended_and_come_first(catalog):
    models = catalog.discover()

    # Order is part of the contract: a client renders this list as-is.
    assert [m.recommended for m in models] == [True, True, False]
    assert models[-1].id.endswith("unsloth/Qwen3.5-4B-MTP-GGUF/Qwen3.5-4B-UD-Q4_K_XL.gguf")


def test_family_is_parsed_from_the_filename(catalog):
    families = {m.name: m.family for m in catalog.discover()}
    assert families["Qwen3.5-9B-UD-Q3_K_XL"] == "9B"
    assert families["Qwen3.5-4B-UD-Q4_K_XL"] == "4B"


def test_select_persists_and_marks_the_slot(catalog, tmp_path):
    target = next(m for m in catalog.discover() if m.family == "9B")
    catalog.select("main", target.id)

    assert catalog.selected("main") == target.id
    saved = json.loads((tmp_path / "models.json").read_text(encoding="utf-8"))
    assert saved["selection"]["main"] == target.id

    reloaded = ModelCatalog(models_dir=catalog.models_dir, state_path=tmp_path / "models.json")
    assert reloaded.selected("main") == target.id
    assert "main" in next(m for m in reloaded.discover() if m.id == target.id).slots


def test_both_slots_can_be_selected_independently(catalog):
    nine = next(m for m in catalog.discover() if m.family == "9B")
    four = next(m for m in catalog.discover() if m.family == "4B")

    catalog.select("main", nine.id)
    catalog.select("fast", four.id)

    assert catalog.selection() == {"main": nine.id, "fast": four.id}


def test_clear_restores_the_configured_fallback(catalog):
    target = catalog.discover()[0]
    catalog.select("main", target.id)
    catalog.clear("main")

    assert catalog.selected("main") is None


def test_unknown_slot_is_rejected(catalog):
    target = catalog.discover()[0]
    with pytest.raises(ValueError, match="Unknown slot"):
        catalog.select("turbo", target.id)


def test_projector_cannot_be_selected_as_a_chat_model(catalog):
    projector = catalog.projectors()[0]
    with pytest.raises(ValueError, match="projector"):
        catalog.select("main", projector.id)


def test_model_outside_models_dir_is_rejected(catalog, tmp_path):
    outside = _gguf(tmp_path / "elsewhere" / "Sneaky.gguf")
    with pytest.raises(ValueError, match="must live under"):
        catalog.select("main", str(outside))


def test_missing_file_is_rejected(catalog, models_dir):
    # Inside models/, so containment passes and the existence check is what has to reject it.
    with pytest.raises(ValueError, match="Not an existing"):
        catalog.select("main", str(models_dir / "DoesNotExist.gguf"))


def test_unreadable_state_file_falls_back_to_no_selection(models_dir, tmp_path):
    state = tmp_path / "models.json"
    state.write_text("{not json", encoding="utf-8")

    catalog = ModelCatalog(models_dir=models_dir, state_path=state)
    assert catalog.selection() == {"main": None, "fast": None}


# --- API ---------------------------------------------------------------


@pytest.fixture
def client(monkeypatch, catalog):
    import app.agent.model_catalog as model_catalog
    import app.routers.models as models_router

    monkeypatch.setattr(model_catalog, "_catalog", catalog)
    monkeypatch.setattr(models_router, "get_model_catalog", lambda: catalog)
    return TestClient(app)


def test_list_endpoint_returns_recommended_first(client, catalog):
    body = client.get("/api/models").json()

    assert [m["recommended"] for m in body["models"]] == [True, True, False]
    assert len(body["projectors"]) == 1
    assert body["slots"] == ["main", "fast"]
    assert body["selection"] == {"main": None, "fast": None}


def test_select_endpoint_records_the_choice_without_activating(client, catalog):
    target = catalog.discover()[0]

    body = client.post(
        "/api/models/select",
        json={"slot": "fast", "model_id": target.id, "activate": False},
    ).json()

    assert body["selected"]["id"] == target.id
    assert body["selection"]["fast"] == target.id
    assert body["activated"] is False
    assert body["error"] is None


def test_select_endpoint_rejects_a_projector(client, catalog):
    projector = catalog.projectors()[0]

    response = client.post(
        "/api/models/select",
        json={"slot": "main", "model_id": projector.id, "activate": False},
    )

    assert response.status_code == 400
    assert "projector" in response.json()["detail"]


def test_select_endpoint_reports_a_load_failure_but_keeps_the_choice(client, catalog, monkeypatch):
    """A model that will not load is still remembered, so the user can retry rather than
    having their selection silently discarded."""
    import app.routers.models as models_router

    class _Failing:
        current_model_kind = None
        is_externally_managed = False

        async def reload(self, kind):
            raise RuntimeError("llama-server exited prematurely with code 1 during startup.")

    monkeypatch.setattr(models_router, "_runtime_manager", lambda: _Failing())
    target = catalog.discover()[0]

    body = client.post(
        "/api/models/select",
        json={"slot": "main", "model_id": target.id, "activate": True},
    ).json()

    assert body["activated"] is False
    assert "code 1" in body["error"]
    assert catalog.selected("main") == target.id


def test_clear_endpoint_drops_the_override(client, catalog):
    target = catalog.discover()[0]
    catalog.select("main", target.id)

    body = client.delete("/api/models/select/main").json()

    assert body["selection"]["main"] is None


def test_clear_endpoint_rejects_an_unknown_slot(client):
    assert client.delete("/api/models/select/turbo").status_code == 400
