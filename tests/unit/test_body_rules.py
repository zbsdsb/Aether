from src.api.handlers.base.request_builder import apply_body_rules


class TestApplyBodyRulesNestedPaths:
    def test_set_nested_value(self) -> None:
        body = {"a": 1}
        result = apply_body_rules(
            body,
            [
                {"action": "set", "path": "b.c.d", "value": 42},
            ],
        )
        assert result == {"a": 1, "b": {"c": {"d": 42}}}

    def test_drop_nested_value(self) -> None:
        body = {"a": {"b": {"c": 1, "d": 2}}}
        result = apply_body_rules(
            body,
            [
                {"action": "drop", "path": "a.b.c"},
            ],
        )
        assert result == {"a": {"b": {"d": 2}}}

    def test_rename_nested_value(self) -> None:
        body = {"old": {"nested": "value"}}
        result = apply_body_rules(
            body,
            [
                {"action": "rename", "from": "old.nested", "to": "new.path"},
            ],
        )
        assert result == {"old": {}, "new": {"path": "value"}}

    def test_protected_top_level_key(self) -> None:
        body = {"model": "gpt-4", "extra": {"model": "ignored"}}
        result = apply_body_rules(
            body,
            [
                {"action": "set", "path": "model.sub", "value": "x"},  # 应被忽略
                {"action": "set", "path": "extra.model", "value": "y"},  # 应生效
            ],
        )
        assert result["model"] == "gpt-4"  # 顶层受保护，不变
        assert result["extra"]["model"] == "y"  # extra 不受保护

    def test_escaped_dot(self) -> None:
        body = {}
        result = apply_body_rules(
            body,
            [
                {"action": "set", "path": "config\\.v1.enabled", "value": True},
            ],
        )
        assert result == {"config.v1": {"enabled": True}}

    def test_invalid_paths_are_ignored(self) -> None:
        body = {"a": 1}
        result = apply_body_rules(
            body,
            [
                {"action": "set", "path": ".b", "value": 2},
                {"action": "set", "path": "c..d", "value": 3},
                {"action": "drop", "path": "e.", "value": None},
                {"action": "rename", "from": "x..y", "to": "z", "value": None},
            ],
        )
        assert result == {"a": 1}

    def test_non_dict_intermediate_is_overwritten(self) -> None:
        body = {"a": 1}
        result = apply_body_rules(
            body,
            [
                {"action": "set", "path": "a.b", "value": 2},
            ],
        )
        assert result == {"a": {"b": 2}}

    def test_set_complex_value(self) -> None:
        body = {}
        result = apply_body_rules(
            body,
            [
                {"action": "set", "path": "metadata.tags", "value": [1, 2]},
                {"action": "set", "path": "metadata.obj", "value": {"a": 1}},
            ],
        )
        assert result == {"metadata": {"tags": [1, 2], "obj": {"a": 1}}}

    def test_does_not_mutate_original_body(self) -> None:
        body = {"a": {"b": 1}}
        result = apply_body_rules(body, [{"action": "set", "path": "a.c", "value": 2}])
        assert result == {"a": {"b": 1, "c": 2}}
        assert body == {"a": {"b": 1}}
