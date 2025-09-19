"""
Git operation data models.

This module defines data models for git automation operations
including commit results and repository status.
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class CommitResult:
    """Result of a git commit operation."""

    success: bool
    commit_hash: Optional[str]
    message: str
    timestamp: datetime
    files_changed: List[str]
    error_message: Optional[str] = None

    def validate(self) -> None:
        """Validate commit result data."""
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean")

        if not self.message:
            raise ValueError("message cannot be empty")

        if not isinstance(self.files_changed, list):
            raise ValueError("files_changed must be a list")

        if self.success and not self.commit_hash:
            raise ValueError("commit_hash required for successful commits")


@dataclass
class GitStatus:
    """Current git repository status."""

    has_changes: bool
    staged_files: List[str]
    unstaged_files: List[str]
    untracked_files: List[str]
    current_branch: str

    def validate(self) -> None:
        """Validate git status data."""
        if not isinstance(self.has_changes, bool):
            raise ValueError("has_changes must be a boolean")

        for file_list in [self.staged_files, self.unstaged_files, self.untracked_files]:
            if not isinstance(file_list, list):
                raise ValueError("file lists must be lists")

        if not self.current_branch:
            raise ValueError("current_branch cannot be empty")
