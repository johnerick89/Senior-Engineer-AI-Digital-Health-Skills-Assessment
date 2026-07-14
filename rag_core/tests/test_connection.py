"""Tests for rag_core.db.session."""

from unittest.mock import MagicMock, patch

from rag_core.core.config import Settings
from rag_core.db.session import check_connection, configure_engine


@patch("rag_core.db.session.create_engine")
def test_configure_engine_uses_psycopg_dialect(
    mock_create_engine: MagicMock,
    isolated_settings_env: None,
) -> None:
    mock_create_engine.return_value = MagicMock()
    settings = Settings(_env_file=None, database_url="postgresql://settings:5432/rag")

    configure_engine(settings=settings)

    mock_create_engine.assert_called_once()
    assert mock_create_engine.call_args.args[0] == "postgresql+psycopg://settings:5432/rag"


@patch("rag_core.db.session.get_engine")
def test_check_connection_returns_true_on_success(mock_get_engine: MagicMock) -> None:
    engine = MagicMock()
    session = MagicMock()
    session.scalar.return_value = 1
    session.__enter__.return_value = session
    session.__exit__.return_value = None

    with patch("rag_core.db.session.Session", return_value=session):
        mock_get_engine.return_value = engine
        assert check_connection("postgresql://example:5432/app") is True

    session.scalar.assert_called_once()


@patch("rag_core.db.session.get_engine", side_effect=RuntimeError("down"))
def test_check_connection_returns_false_on_error(_mock_get_engine: MagicMock) -> None:
    assert check_connection("postgresql://example:5432/app") is False
