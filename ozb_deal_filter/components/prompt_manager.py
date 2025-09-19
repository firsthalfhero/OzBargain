"""
Prompt management for LLM evaluation templates.

This module provides functionality for loading, validating, and managing
prompt templates used for deal evaluation.
"""

import os
import logging
from typing import Dict
from pathlib import Path


logger = logging.getLogger(__name__)


class PromptManager:
    """Manager for LLM prompt templates."""

    def __init__(self, prompts_directory: str = "prompts"):
        self.prompts_directory = Path(prompts_directory)
        self._templates: Dict[str, str] = {}
        self._ensure_prompts_directory()

    def _ensure_prompts_directory(self) -> None:
        """Ensure prompts directory exists."""
        if not self.prompts_directory.exists():
            logger.warning(f"Prompts directory {self.prompts_directory} does not exist")
            return

        if not self.prompts_directory.is_dir():
            raise ValueError(
                f"Prompts path {self.prompts_directory} is not a directory"
            )

    def load_template(self, template_path: str) -> str:
        """Load a prompt template from file."""
        # Check cache first
        if template_path in self._templates:
            return self._templates[template_path]

        # Resolve path relative to prompts directory
        if not os.path.isabs(template_path):
            full_path = self.prompts_directory / template_path
        else:
            full_path = Path(template_path)

        try:
            if not full_path.exists():
                raise FileNotFoundError(f"Prompt template not found: {full_path}")

            with open(full_path, "r", encoding="utf-8") as f:
                template_content = f.read().strip()

            if not template_content:
                raise ValueError(f"Prompt template is empty: {full_path}")

            # Validate template has required placeholders
            self._validate_template(template_content)

            # Cache the template
            self._templates[template_path] = template_content
            logger.info(f"Loaded prompt template: {template_path}")

            return template_content

        except Exception as e:
            logger.error(f"Failed to load prompt template {template_path}: {e}")
            raise RuntimeError(f"Failed to load prompt template: {e}")

    def _validate_template(self, template: str) -> None:
        """Validate that template contains required placeholders."""
        required_placeholders = ["{title}", "{description}", "{category}"]

        optional_placeholders = [
            "{price}",
            "{original_price}",
            "{discount_percentage}",
            "{url}",
            "{votes}",
            "{comments}",
            "{urgency_indicators}",
        ]

        # Check for required placeholders
        missing_required = []
        for placeholder in required_placeholders:
            if placeholder not in template:
                missing_required.append(placeholder)

        if missing_required:
            raise ValueError(
                f"Template missing required placeholders: {missing_required}"
            )

        # Log optional placeholders that are missing
        missing_optional = []
        for placeholder in optional_placeholders:
            if placeholder not in template:
                missing_optional.append(placeholder)

        if missing_optional:
            logger.info(f"Template missing optional placeholders: {missing_optional}")

    def reload_template(self, template_path: str) -> str:
        """Reload a template from file, bypassing cache."""
        # Remove from cache to force reload
        if template_path in self._templates:
            del self._templates[template_path]

        return self.load_template(template_path)

    def get_available_templates(self) -> list[str]:
        """Get list of available template files."""
        if not self.prompts_directory.exists():
            return []

        templates = []
        for file_path in self.prompts_directory.glob("*.txt"):
            templates.append(str(file_path.relative_to(self.prompts_directory)))

        return sorted(templates)

    def create_default_template(self, template_path: str) -> str:
        """Create a default prompt template if none exists."""
        full_path = self.prompts_directory / template_path

        # Create prompts directory if it doesn't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)

        default_template = (
            "You are an expert deal evaluator. Analyze the following deal "
            "and determine if it matches the user's interests.\n\n"
            "Deal Information:\n"
            "- Title: {title}\n"
            "- Description: {description}\n"
            "- Category: {category}\n"
            "- Price: {price}\n"
            "- Original Price: {original_price}\n"
            "- Discount: {discount_percentage}%\n"
            "- Community Votes: {votes}\n"
            "- Comments: {comments}\n"
            "- URL: {url}\n\n"
            "Instructions:\n"
            "1. Evaluate if this deal is relevant to someone interested in "
            "electronics, computing, or gaming products\n"
            "2. Consider the discount percentage, price point, and community "
            "engagement\n"
            '3. Respond with either "RELEVANT" or "NOT RELEVANT" followed '
            "by your reasoning\n\n"
            "Your evaluation:"
        )

        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(default_template)

            logger.info(f"Created default prompt template: {template_path}")
            return default_template

        except Exception as e:
            logger.error(f"Failed to create default template: {e}")
            raise RuntimeError(f"Failed to create default template: {e}")

    def validate_template_file(self, template_path: str) -> bool:
        """Validate a template file without loading it into cache."""
        try:
            # Temporarily load template for validation
            if not os.path.isabs(template_path):
                full_path = self.prompts_directory / template_path
            else:
                full_path = Path(template_path)

            if not full_path.exists():
                return False

            with open(full_path, "r", encoding="utf-8") as f:
                template_content = f.read().strip()

            if not template_content:
                return False

            self._validate_template(template_content)
            return True

        except Exception as e:
            logger.error(f"Template validation failed for {template_path}: {e}")
            return False

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._templates.clear()
        logger.info("Prompt template cache cleared")
