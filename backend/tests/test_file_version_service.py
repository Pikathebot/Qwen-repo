import pytest
from sqlmodel import create_engine, SQLModel
from app.services.file_version_service import FileVersionService
from app.database.models import FileVersion


@pytest.fixture
def isolated_file_service(tmp_path):
    """Creates an isolated FileVersionService instance backed by a temporary SQLite DB."""
    db_file = tmp_path / "test_file_versions.db"
    test_engine = create_engine(f"sqlite:///{db_file}")
    SQLModel.metadata.create_all(test_engine)
    return FileVersionService(db_engine=test_engine)


def test_capture_version_snapshots_file(tmp_path, isolated_file_service):
    """Verify capture_version reads file and creates FileVersion in DB with auto-incrementing versions."""
    test_file = tmp_path / "example.py"
    test_file.write_text("print('version 1')", encoding="utf-8")

    # 1. First snapshot
    ver1 = isolated_file_service.capture_version(str(test_file), session_id="sess_1", created_by="agent")
    assert ver1 is not None
    assert ver1.version_number == 1
    assert "version 1" in ver1.content

    # 2. Modify and snapshot again
    test_file.write_text("print('version 2')", encoding="utf-8")
    ver2 = isolated_file_service.capture_version(str(test_file), session_id="sess_1", created_by="agent")
    assert ver2 is not None
    assert ver2.version_number == 2
    assert "version 2" in ver2.content


def test_capture_version_nonexistent_file(tmp_path, isolated_file_service):
    """Verify capture_version gracefully returns None for non-existent files."""
    assert isolated_file_service.capture_version(str(tmp_path / "ghost.py"), session_id="sess_1") is None


def test_get_versions_history(tmp_path, isolated_file_service):
    """Verify get_versions returns ordered version history."""
    test_file = tmp_path / "script.py"
    test_file.write_text("initial", encoding="utf-8")
    isolated_file_service.capture_version(str(test_file), session_id="sess_1")

    test_file.write_text("second", encoding="utf-8")
    isolated_file_service.capture_version(str(test_file), session_id="sess_1")

    versions = isolated_file_service.get_versions(str(test_file), session_id="sess_1")
    assert len(versions) == 2
    assert versions[0].version_number == 1
    assert versions[0].content == "initial"
    assert versions[1].version_number == 2
    assert versions[1].content == "second"


def test_restore_file_version_to_disk(tmp_path, isolated_file_service):
    """Verify restore_version writes previous content back to disk and snapshots state before restore."""
    test_file = tmp_path / "config.json"
    test_file.write_text('{"env": "v1"}', encoding="utf-8")
    v1 = isolated_file_service.capture_version(str(test_file), session_id="sess_1")

    # Update to v2
    test_file.write_text('{"env": "v2_broken"}', encoding="utf-8")
    isolated_file_service.capture_version(str(test_file), session_id="sess_1")

    # Restore v1
    success = isolated_file_service.restore_version(str(test_file), v1.id, session_id="sess_1")
    assert success is True
    assert test_file.read_text(encoding="utf-8") == '{"env": "v1"}'

    # Verify a new snapshot was taken before restore
    history = isolated_file_service.get_versions(str(test_file), session_id="sess_1")
    assert len(history) == 3


def test_generate_unified_diff(isolated_file_service):
    """Verify generate_diff outputs clean unified diff text."""
    old_c = "line 1\nline 2\nline 3\n"
    new_c = "line 1\nline 2 modified\nline 3\n"

    diff_str = isolated_file_service.generate_diff(old_c, new_c, "test.txt")
    assert "--- a/test.txt" in diff_str
    assert "+++ b/test.txt" in diff_str
    assert "-line 2" in diff_str
    assert "+line 2 modified" in diff_str
