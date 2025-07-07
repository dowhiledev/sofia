from enum import Enum

from nomos.utils.misc import join_urls
from nomos.utils.utils import create_base_model, create_enum


def test_create_base_model_no_description():
    Model = create_base_model("TestModel", {"a": {"type": int, "description": ""}})
    assert Model.model_fields["a"].description is None


def test_create_base_model_missing_description():
    Model = create_base_model("TestModel", {"a": {"type": int}})
    assert Model.model_fields["a"].description is None


def test_create_enum_basic():
    Color = create_enum("Color", {"RED": 1, "BLUE": 2})
    assert issubclass(Color, Enum)
    assert Color.RED.value == 1
    assert [member.name for member in Color] == ["RED", "BLUE"]


class TestJoinUrls:
    """Test the join_urls utility function."""

    def test_join_two_urls(self):
        """Test joining two URL components."""
        result = join_urls("https://example.com", "api/v1")
        assert result == "https://example.com/api/v1"

    def test_join_with_leading_slashes(self):
        """Test joining URLs with leading slashes."""
        result = join_urls("https://example.com/", "/api/v1")
        assert result == "https://example.com/api/v1"

    def test_join_with_trailing_slashes(self):
        """Test joining URLs with trailing slashes."""
        result = join_urls("https://example.com/", "api/v1/")
        assert result == "https://example.com/api/v1"

    def test_join_multiple_components(self):
        """Test joining multiple URL components."""
        result = join_urls("https://example.com", "api", "v1", "tools")
        assert result == "https://example.com/api/v1/tools"
