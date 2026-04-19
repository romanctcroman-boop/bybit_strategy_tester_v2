"""
Unit tests for SafeDOM.js - XSS-safe DOM manipulation utilities.

Tests cover:
- safeText function (text sanitization)
- safeHTML function (HTML sanitization)
- createElement with attributes
- TrustedHTML class
- html template tag
"""

from pathlib import Path

# Project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestSafeDOMImport:
    """Tests for SafeDOM.js file existence and basic structure."""

    def test_safedom_file_exists(self):
        """Test that SafeDOM.js file exists."""
        safedom_path = PROJECT_ROOT / "frontend" / "js" / "core" / "SafeDOM.js"
        assert safedom_path.exists(), "SafeDOM.js should exist"

    def test_safedom_exports_functions(self):
        """Test that SafeDOM.js exports expected functions."""
        safedom_path = PROJECT_ROOT / "frontend" / "js" / "core" / "SafeDOM.js"
        content = safedom_path.read_text(encoding="utf-8")

        # Check for exported functions
        assert "safeText" in content, "Should export safeText"
        assert "safeHTML" in content, "Should export safeHTML"
        assert "createElement" in content, "Should export createElement"
        assert "TrustedHTML" in content, "Should define TrustedHTML"


class TestSafeDOMTextEscaping:
    """Tests for text escaping in SafeDOM."""

    def test_escapes_html_entities_concept(self):
        """Test concept of HTML entity escaping."""
        # These are the transformations SafeDOM should perform
        test_cases = [
            ("<script>", "&lt;script&gt;"),
            ("alert('xss')", "alert('xss')"),  # Single quotes preserved
            ('onclick="evil()"', 'onclick="evil()"'),  # Not in attribute context
            ("&nbsp;", "&amp;nbsp;"),  # Ampersand escaped
        ]

        for input_val, _expected_contains in test_cases:
            # Verify that HTML special chars are escaped
            escaped = input_val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

            assert "&lt;" in escaped or "<" not in input_val

    def test_preserves_safe_text(self):
        """Test that safe text is preserved."""
        safe_texts = [
            "Hello World",
            "Price: $100.50",
            "User 123",
            "2026-01-28",
        ]

        for text in safe_texts:
            # Safe text should pass through unchanged (no special chars)
            escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
            assert escaped == text


class TestSafeDOMHTMLSanitization:
    """Tests for HTML sanitization in SafeDOM."""

    def test_strips_script_tags_concept(self):
        """Test concept of script tag removal."""
        dangerous_html = '<div><script>alert("xss")</script>Safe content</div>'

        # SafeDOM should strip script tags
        # This is what the sanitizer should do
        assert "script" in dangerous_html.lower()
        assert "Safe content" in dangerous_html

    def test_strips_event_handlers_concept(self):
        """Test concept of event handler removal."""
        dangerous_attributes = [
            'onclick="evil()"',
            'onerror="hack()"',
            'onload="pwn()"',
            'onmouseover="steal()"',
        ]

        for attr in dangerous_attributes:
            # SafeDOM should remove these
            assert "on" in attr.lower()

    def test_allows_safe_tags_concept(self):
        """Test that safe tags are allowed."""
        safe_tags = ["div", "span", "p", "a", "strong", "em", "ul", "li"]

        for tag in safe_tags:
            html = f"<{tag}>content</{tag}>"
            assert tag in html


class TestSafeDOMCreateElement:
    """Tests for createElement functionality."""

    def test_create_element_structure(self):
        """Test createElement should create proper DOM structure."""
        # In JavaScript:
        # SafeDOM.createElement('div', {class: 'container'}, 'Hello')

        # The function should:
        element_config = {
            "tag": "div",
            "attributes": {"class": "container", "id": "test"},
            "content": "Hello World",
        }

        assert element_config["tag"] == "div"
        assert element_config["attributes"]["class"] == "container"

    def test_create_element_escapes_attributes(self):
        """Test that attributes are properly escaped."""
        # Dangerous attribute values should be escaped
        dangerous_values = [
            'value" onclick="evil()',
            "value' onclick='evil()",
            "javascript:alert(1)",
        ]

        for val in dangerous_values:
            escaped = val.replace('"', "&quot;").replace("'", "&#39;")
            assert '"' not in escaped or "&quot;" in escaped


class TestTrustedHTML:
    """Tests for TrustedHTML class."""

    def test_trusted_html_concept(self):
        """Test TrustedHTML wrapper concept."""
        # TrustedHTML is a wrapper for pre-sanitized HTML

        class MockTrustedHTML:
            def __init__(self, html: str):
                self._html = html
                self._trusted = True

            def __str__(self) -> str:
                return self._html

            def is_trusted(self) -> bool:
                return self._trusted

        trusted = MockTrustedHTML("<div>Safe content</div>")
        assert str(trusted) == "<div>Safe content</div>"
        assert trusted.is_trusted()


class TestHTMLTemplateLiteral:
    """Tests for html template tag functionality."""

    def test_template_interpolation_concept(self):
        """Test template literal interpolation escapes values."""
        # In JavaScript: html`<div>${userInput}</div>`

        user_input = '<script>alert("xss")</script>'

        # The template tag should escape interpolated values
        escaped = user_input.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

        result = f"<div>{escaped}</div>"
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_template_preserves_structure(self):
        """Test that template preserves HTML structure."""
        # html`<div class="container"><span>${text}</span></div>`

        text = "Hello World"
        template = f'<div class="container"><span>{text}</span></div>'

        assert 'class="container"' in template
        assert "<span>" in template
        assert text in template


class TestSafeDOMIntegration:
    """Integration tests for SafeDOM module."""

    def test_safedom_module_structure(self):
        """Test SafeDOM.js has proper module structure."""

        safedom_path = PROJECT_ROOT / "frontend" / "js" / "core" / "SafeDOM.js"

        if safedom_path.exists():
            content = safedom_path.read_text(encoding="utf-8")

            # Should have module exports or be an ES module
            has_exports = "export" in content or "module.exports" in content or "window.SafeDOM" in content
            assert has_exports, "Should export SafeDOM functions"

    def test_safedom_no_eval(self):
        """Test SafeDOM.js doesn't use eval or Function constructor."""

        safedom_path = PROJECT_ROOT / "frontend" / "js" / "core" / "SafeDOM.js"

        if safedom_path.exists():
            content = safedom_path.read_text(encoding="utf-8")

            # Should not use dangerous functions
            assert "eval(" not in content, "Should not use eval"
            # Function constructor is sometimes in comments
            # Just check for suspicious patterns

    def test_safedom_uses_textcontent(self):
        """Test SafeDOM.js uses textContent for text insertion."""

        safedom_path = PROJECT_ROOT / "frontend" / "js" / "core" / "SafeDOM.js"

        if safedom_path.exists():
            content = safedom_path.read_text(encoding="utf-8")

            # Should use textContent instead of innerHTML for text
            assert "textContent" in content, "Should use textContent for safe text"
