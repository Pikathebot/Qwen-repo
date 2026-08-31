import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session

from app.main import app
from app.config import settings
from app.database import get_session


@pytest.fixture
def artifacts_test_env(tmp_path, monkeypatch):
    """Isolated database and workspace directory for artifacts testing."""
    test_db = tmp_path / "test_artifacts.db"
    db_url = f"sqlite:///{test_db}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    test_workspace = tmp_path / "workspace"
    test_workspace.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "workspace_path", str(test_workspace))

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


def test_create_and_retrieve_artifact_v1(artifacts_test_env):
    client = artifacts_test_env

    payload = {
        "name": "calc.py",
        "type": "code",
        "content": "def add(a, b):\n    return a + b\n",
        "summary": "Initial calculator function"
    }

    res = client.post("/api/artifacts", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["name"] == "calc.py"
    assert data["type"] == "code"
    assert data["version"] == 1
    assert "def add" in data["content"]

    artifact_id = data["id"]

    # Retrieve by ID
    get_res = client.get(f"/api/artifacts/{artifact_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == artifact_id

    # Verify version 1 exists in version history
    ver_res = client.get(f"/api/artifacts/{artifact_id}/versions")
    assert ver_res.status_code == 200
    versions = ver_res.json()
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert versions[0]["summary"] == "Initial calculator function"


def test_artifact_version_history_and_updates(artifacts_test_env):
    client = artifacts_test_env

    # 1. Create v1
    art = client.post("/api/artifacts", json={
        "name": "index.html",
        "type": "html",
        "content": "<h1>Hello v1</h1>"
    }).json()
    art_id = art["id"]

    # 2. Add version 2 via POST /api/artifacts/{id}/versions
    v2_res = client.post(f"/api/artifacts/{art_id}/versions", json={
        "content": "<h1>Hello v2</h1><p>Added paragraph</p>",
        "summary": "Add paragraph in body"
    })
    assert v2_res.status_code == 201
    v2_data = v2_res.json()
    assert v2_data["version"] == 2
    assert v2_data["content"] == "<h1>Hello v2</h1><p>Added paragraph</p>"

    # 3. Add version 3 via PUT /api/artifacts/{id} with create_new_version=True
    put_res = client.put(f"/api/artifacts/{art_id}", json={
        "content": "<h1>Hello v3</h1><footer>Footer</footer>",
        "create_new_version": True,
        "summary": "Added footer"
    })
    assert put_res.status_code == 200
    assert put_res.json()["version"] == 3

    # 4. Check full version history
    all_vers = client.get(f"/api/artifacts/{art_id}/versions").json()
    assert len(all_vers) == 3
    version_numbers = [v["version"] for v in all_vers]
    assert version_numbers == [1, 2, 3]


def test_list_and_delete_artifact(artifacts_test_env):
    client = artifacts_test_env

    # Create 2 artifacts
    a1 = client.post("/api/artifacts", json={"name": "a.txt", "type": "markdown", "content": "a"}).json()
    a2 = client.post("/api/artifacts", json={"name": "b.txt", "type": "markdown", "content": "b"}).json()

    list_res = client.get("/api/artifacts").json()
    assert len(list_res) == 2

    # Delete a1
    del_res = client.delete(f"/api/artifacts/{a1['id']}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # a1 should be gone, a2 remains
    after_list = client.get("/api/artifacts").json()
    assert len(after_list) == 1
    assert after_list[0]["id"] == a2["id"]
