import pytest
from pydantic import ValidationError

from src.models.admin_requests import ProxyConfig


class TestProxyConfig:
    def test_enabled_requires_url_or_node_id(self) -> None:
        with pytest.raises(ValidationError):
            ProxyConfig.model_validate({"enabled": True})

    def test_enabled_rejects_both_url_and_node_id(self) -> None:
        with pytest.raises(ValidationError):
            ProxyConfig.model_validate(
                {"enabled": True, "url": "http://127.0.0.1:8080", "node_id": "n1"}
            )

    def test_disabled_allows_empty(self) -> None:
        cfg = ProxyConfig.model_validate({"enabled": False})
        assert cfg.url is None
        assert cfg.node_id is None

    def test_url_mode_ok(self) -> None:
        cfg = ProxyConfig.model_validate({"enabled": True, "url": "http://127.0.0.1:8080"})
        assert cfg.url == "http://127.0.0.1:8080"
        assert cfg.node_id is None

    def test_url_rejects_inline_auth(self) -> None:
        with pytest.raises(ValidationError):
            ProxyConfig.model_validate({"enabled": True, "url": "http://u:p@127.0.0.1:8080"})

    def test_node_id_mode_ok_and_strips(self) -> None:
        cfg = ProxyConfig.model_validate({"enabled": True, "node_id": "  node-1  "})
        assert cfg.node_id == "node-1"
        assert cfg.url is None
