"""
Unit tests for prompt management components.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from ozb_deal_filter.components.prompt_manager import PromptManager


@pytest.fixture
def temp_prompts_dir():
    """Create a temporary directory for prompt templates."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_template():
    """Sample prompt template content."""
    return """You are a deal evaluator. Analyze this deal:

Title: {title}
Description: {description}
Category: {category}
Price: {price}
Original Price: {original_price}
Discount: {discount_percentage}%

Respond with RELEVANT or NOT RELEVANT."""


@pytest.fixture
def minimal_template():
    """Minimal valid template with only required placeholders."""
    return "Evaluate: {title} - {description} - {category}"


@pytest.fixture
def invalid_template():
    """Invalid template missing required placeholders."""
    return "This template is missing required placeholders: {price}"


class TestPromptManager:
    """Test cases for PromptManager."""

    def test_init_with_existing_directory(self, temp_prompts_dir):
        """Test initialization with existing prompts directory."""
        manager = PromptManager(temp_prompts_dir)

        assert manager.prompts_directory == Path(temp_prompts_dir)
        assert manager._templates == {}

    def test_init_with_nonexistent_directory(self):
        """Test initialization with non-existent directory."""
        manager = PromptManager("nonexistent_dir")

        assert manager.prompts_directory == Path("nonexistent_dir")
        assert manager._templates == {}

    def test_init_with_file_instead_of_directory(self, temp_prompts_dir):
        """Test initialization when prompts path is a file."""
        file_path = os.path.join(temp_prompts_dir, "not_a_directory.txt")
        with open(file_path, "w") as f:
            f.write("test")

        with pytest.raises(ValueError, match="is not a directory"):
            PromptManager(file_path)

    def test_load_template_success(self, temp_prompts_dir, sample_template):
        """Test successful template loading."""
        template_path = "test_template.txt"
        full_path = os.path.join(temp_prompts_dir, template_path)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(sample_template)

        manager = PromptManager(temp_prompts_dir)
        result = manager.load_template(template_path)

        assert result == sample_template
        assert template_path in manager._templates
        assert manager._templates[template_path] == sample_template

    def test_load_template_from_cache(self, temp_prompts_dir, sample_template):
        """Test loading template from cache on second call."""
        template_path = "test_template.txt"
        full_path = os.path.join(temp_prompts_dir, template_path)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(sample_template)

        manager = PromptManager(temp_prompts_dir)

        # First load
        result1 = manager.load_template(template_path)

        # Modify file after first load
        with open(full_path, "w", encoding="utf-8") as f:
            f.write("Modified content")

        # Second load should return cached version
        result2 = manager.load_template(template_path)

        assert result1 == result2 == sample_template

    def test_load_template_absolute_path(self, temp_prompts_dir, sample_template):
        """Test loading template with absolute path."""
        template_file = os.path.join(temp_prompts_dir, "absolute_template.txt")

        with open(template_file, "w", encoding="utf-8") as f:
            f.write(sample_template)

        manager = PromptManager(temp_prompts_dir)
        result = manager.load_template(template_file)

        assert result == sample_template

    def test_load_template_file_not_found(self, temp_prompts_dir):
        """Test loading non-existent template file."""
        manager = PromptManager(temp_prompts_dir)

        with pytest.raises(RuntimeError, match="Failed to load prompt template"):
            manager.load_template("nonexistent.txt")

    def test_load_template_empty_file(self, temp_prompts_dir):
        """Test loading empty template file."""
        template_path = "empty_template.txt"
        full_path = os.path.join(temp_prompts_dir, template_path)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write("")

        manager = PromptManager(temp_prompts_dir)

        with pytest.raises(RuntimeError, match="Failed to load prompt template"):
            manager.load_template(template_path)

    def test_load_template_missing_required_placeholders(
        self, temp_prompts_dir, invalid_template
    ):
        """Test loading template with missing required placeholders."""
        template_path = "invalid_template.txt"
        full_path = os.path.join(temp_prompts_dir, template_path)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(invalid_template)

        manager = PromptManager(temp_prompts_dir)

        with pytest.raises(RuntimeError, match="Failed to load prompt template"):
            manager.load_template(template_path)

    def test_validate_template_success(self, sample_template):
        """Test successful template validation."""
        manager = PromptManager()

        # Should not raise exception
        manager._validate_template(sample_template)

    def test_validate_template_missing_required(self):
        """Test template validation with missing required placeholders."""
        manager = PromptManager()
        template = "Missing required: {price} only"

        with pytest.raises(ValueError, match="missing required placeholders"):
            manager._validate_template(template)

    def test_validate_template_minimal_valid(self, minimal_template):
        """Test validation of minimal valid template."""
        manager = PromptManager()

        # Should not raise exception
        manager._validate_template(minimal_template)

    def test_reload_template(self, temp_prompts_dir):
        """Test reloading template bypassing cache."""
        template_path = "reload_template.txt"
        full_path = os.path.join(temp_prompts_dir, template_path)

        # Create initial template
        initial_content = "Initial: {title} {description} {category}"
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(initial_content)

        manager = PromptManager(temp_prompts_dir)

        # Load initial template
        result1 = manager.load_template(template_path)
        assert result1 == initial_content

        # Modify template file
        updated_content = "Updated: {title} {description} {category}"
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        # Reload should get updated content
        result2 = manager.reload_template(template_path)
        assert result2 == updated_content
        assert result2 != result1

    def test_get_available_templates(self, temp_prompts_dir):
        """Test getting list of available templates."""
        # Create some template files
        templates = ["template1.txt", "template2.txt", "template3.txt"]
        for template in templates:
            full_path = os.path.join(temp_prompts_dir, template)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write("Test: {title} {description} {category}")

        # Create a non-txt file (should be ignored)
        with open(os.path.join(temp_prompts_dir, "config.yaml"), "w") as f:
            f.write("config: value")

        manager = PromptManager(temp_prompts_dir)
        available = manager.get_available_templates()

        assert len(available) == 3
        assert all(template in available for template in templates)
        assert "config.yaml" not in available
        assert available == sorted(templates)  # Should be sorted

    def test_get_available_templates_empty_directory(self, temp_prompts_dir):
        """Test getting templates from empty directory."""
        manager = PromptManager(temp_prompts_dir)
        available = manager.get_available_templates()

        assert available == []

    def test_get_available_templates_nonexistent_directory(self):
        """Test getting templates from non-existent directory."""
        manager = PromptManager("nonexistent_dir")
        available = manager.get_available_templates()

        assert available == []

    def test_create_default_template(self, temp_prompts_dir):
        """Test creating default template."""
        template_path = "default_template.txt"

        manager = PromptManager(temp_prompts_dir)
        result = manager.create_default_template(template_path)

        # Check that template was created
        full_path = os.path.join(temp_prompts_dir, template_path)
        assert os.path.exists(full_path)

        # Check content
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert result == content
        assert "{title}" in content
        assert "{description}" in content
        assert "{category}" in content
        assert "RELEVANT" in content
        assert "NOT RELEVANT" in content

    def test_create_default_template_with_subdirectory(self, temp_prompts_dir):
        """Test creating default template in subdirectory."""
        template_path = "subdir/default_template.txt"

        manager = PromptManager(temp_prompts_dir)
        result = manager.create_default_template(template_path)

        # Check that subdirectory and template were created
        full_path = os.path.join(temp_prompts_dir, template_path)
        assert os.path.exists(full_path)
        assert os.path.exists(os.path.dirname(full_path))

    def test_create_default_template_write_error(self, temp_prompts_dir):
        """Test creating default template with write error."""
        template_path = "readonly/template.txt"

        manager = PromptManager(temp_prompts_dir)

        # Mock open to raise an exception
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(RuntimeError, match="Failed to create default template"):
                manager.create_default_template(template_path)

    def test_validate_template_file_success(self, temp_prompts_dir, sample_template):
        """Test successful template file validation."""
        template_path = "valid_template.txt"
        full_path = os.path.join(temp_prompts_dir, template_path)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(sample_template)

        manager = PromptManager(temp_prompts_dir)
        result = manager.validate_template_file(template_path)

        assert result is True

    def test_validate_template_file_not_found(self, temp_prompts_dir):
        """Test validation of non-existent template file."""
        manager = PromptManager(temp_prompts_dir)
        result = manager.validate_template_file("nonexistent.txt")

        assert result is False

    def test_validate_template_file_empty(self, temp_prompts_dir):
        """Test validation of empty template file."""
        template_path = "empty_template.txt"
        full_path = os.path.join(temp_prompts_dir, template_path)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write("")

        manager = PromptManager(temp_prompts_dir)
        result = manager.validate_template_file(template_path)

        assert result is False

    def test_validate_template_file_invalid(self, temp_prompts_dir, invalid_template):
        """Test validation of invalid template file."""
        template_path = "invalid_template.txt"
        full_path = os.path.join(temp_prompts_dir, template_path)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(invalid_template)

        manager = PromptManager(temp_prompts_dir)
        result = manager.validate_template_file(template_path)

        assert result is False

    def test_validate_template_file_absolute_path(
        self, temp_prompts_dir, sample_template
    ):
        """Test validation with absolute path."""
        template_file = os.path.join(temp_prompts_dir, "absolute_template.txt")

        with open(template_file, "w", encoding="utf-8") as f:
            f.write(sample_template)

        manager = PromptManager(temp_prompts_dir)
        result = manager.validate_template_file(template_file)

        assert result is True

    def test_clear_cache(self, temp_prompts_dir, sample_template):
        """Test clearing template cache."""
        template_path = "cached_template.txt"
        full_path = os.path.join(temp_prompts_dir, template_path)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(sample_template)

        manager = PromptManager(temp_prompts_dir)

        # Load template to cache it
        manager.load_template(template_path)
        assert template_path in manager._templates

        # Clear cache
        manager.clear_cache()
        assert manager._templates == {}

    def test_load_template_with_unicode(self, temp_prompts_dir):
        """Test loading template with unicode characters."""
        template_content = "Evaluate: {title} 🔥 {description} 💰 {category}"
        template_path = "unicode_template.txt"
        full_path = os.path.join(temp_prompts_dir, template_path)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(template_content)

        manager = PromptManager(temp_prompts_dir)
        result = manager.load_template(template_path)

        assert result == template_content
        assert "🔥" in result
        assert "💰" in result
