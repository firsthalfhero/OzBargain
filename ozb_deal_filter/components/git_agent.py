"""
Git automation component for automated commits and repository management.

This module provides the GitAgent class that handles automated git operations
including staging files, generating commit messages, and committing changes.
"""

import re
import subprocess
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from ..interfaces import IGitAgent
from ..models.git import CommitResult, GitStatus
from ..utils.logging import get_logger

logger = get_logger(__name__)


class GitAgent(IGitAgent):
    """
    Git automation agent for handling automated commits and repository operations.

    This class provides functionality to:
    - Stage and commit changes automatically
    - Generate meaningful commit messages
    - Check repository status
    - Handle git operation errors gracefully
    """

    def __init__(self, repo_path: Optional[str] = None):
        """
        Initialize GitAgent with repository path.

        Args:
            repo_path: Path to git repository. Defaults to current directory.
        """
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self._validate_git_repo()

    def _validate_git_repo(self) -> None:
        """Validate that the path contains a git repository."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            raise ValueError(f"No git repository found at {self.repo_path}")

    def _run_git_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """
        Run a git command and return the result.

        Args:
            command: Git command as list of strings

        Returns:
            CompletedProcess result
        """
        full_command = ["git"] + command
        logger.debug(f"Running git command: {' '.join(full_command)}")

        try:
            result = subprocess.run(
                full_command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result
        except subprocess.TimeoutExpired:
            logger.error("Git command timed out")
            raise
        except Exception as e:
            logger.error(f"Error running git command: {e}")
            raise

    def get_status(self) -> GitStatus:
        """
        Get current git repository status.

        Returns:
            GitStatus object with current repository state
        """
        try:
            # Get current branch
            branch_result = self._run_git_command(["branch", "--show-current"])
            current_branch = branch_result.stdout.strip() or "HEAD"

            # Get status
            status_result = self._run_git_command(["status", "--porcelain"])

            staged_files = []
            unstaged_files = []
            untracked_files = []

            for line in status_result.stdout.splitlines():
                if len(line) < 3:
                    continue

                status_code = line[:2]
                filename = line[3:]

                # Staged changes (first character)
                if status_code[0] in ["A", "M", "D", "R", "C"]:
                    staged_files.append(filename)

                # Unstaged changes (second character)
                if status_code[1] in ["M", "D"]:
                    unstaged_files.append(filename)

                # Untracked files
                if status_code == "??":
                    untracked_files.append(filename)

            has_changes = bool(staged_files or unstaged_files or untracked_files)

            return GitStatus(
                has_changes=has_changes,
                staged_files=staged_files,
                unstaged_files=unstaged_files,
                untracked_files=untracked_files,
                current_branch=current_branch,
            )

        except Exception as e:
            logger.error(f"Error getting git status: {e}")
            raise

    def stage_files(self, files: Optional[List[str]] = None) -> bool:
        """
        Stage files for commit.

        Args:
            files: List of files to stage. If None, stages all changes.

        Returns:
            True if staging successful, False otherwise
        """
        try:
            if files is None:
                # Stage all changes
                result = self._run_git_command(["add", "."])
            else:
                # Stage specific files
                result = self._run_git_command(["add"] + files)

            if result.returncode == 0:
                logger.info(f"Successfully staged files: {files or 'all changes'}")
                return True
            else:
                logger.error(f"Failed to stage files: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error staging files: {e}")
            return False

    def generate_commit_message(self, task_description: str) -> str:
        """
        Generate a meaningful commit message for a task.

        Args:
            task_description: Description of the task being committed

        Returns:
            Formatted commit message following conventional commit format
        """
        # Extract task number if present (only first two parts for decimal numbers)
        task_match = re.search(r"(\d+(?:\.\d+)?)", task_description)
        if task_match:
            task_number = task_match.group(1)
            # If there are more than 2 parts (e.g., 4.2.1), keep only first two
            parts = task_number.split(".")
            if len(parts) > 2:
                task_number = f"{parts[0]}.{parts[1]}"
        else:
            task_number = "X.X"

        # Determine commit type based on task description
        commit_type = "feat"
        if any(word in task_description.lower() for word in ["test", "testing"]):
            commit_type = "test"
        elif any(word in task_description.lower() for word in ["fix", "bug", "error"]):
            commit_type = "fix"
        elif any(word in task_description.lower() for word in ["doc", "documentation"]):
            commit_type = "docs"
        elif any(
            word in task_description.lower() for word in ["refactor", "restructure"]
        ):
            commit_type = "refactor"

        # Clean up task description for commit message
        clean_description = re.sub(r"^\d+(?:\.\d+)*\s*", "", task_description)
        clean_description = clean_description.strip()

        # Capitalize first letter
        if clean_description:
            clean_description = clean_description[0].upper() + clean_description[1:]

        return f"{commit_type}: [Task {task_number}] {clean_description}"

    def commit_changes(self, message: str) -> bool:
        """
        Commit current staged changes with the specified message.

        Args:
            message: Commit message

        Returns:
            True if commit successful, False otherwise
        """
        try:
            # Check if there are staged changes
            status = self.get_status()
            if not status.staged_files:
                logger.warning("No staged changes to commit")
                return False

            # Commit changes
            result = self._run_git_command(["commit", "-m", message])

            if result.returncode == 0:
                logger.info(f"Successfully committed changes: {message}")
                return True
            else:
                logger.error(f"Failed to commit changes: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error committing changes: {e}")
            return False

    def commit_with_details(
        self, message: str, files: Optional[List[str]] = None
    ) -> CommitResult:
        """
        Commit changes and return detailed result information.

        Args:
            message: Commit message
            files: Optional list of specific files to stage and commit

        Returns:
            CommitResult with detailed operation information
        """
        timestamp = datetime.now()

        try:
            # Stage files if specified
            if files is not None:
                if not self.stage_files(files):
                    return CommitResult(
                        success=False,
                        commit_hash=None,
                        message=message,
                        timestamp=timestamp,
                        files_changed=[],
                        error_message="Failed to stage files",
                    )

            # Get status before commit
            status = self.get_status()
            staged_files = status.staged_files.copy()

            if not staged_files:
                return CommitResult(
                    success=False,
                    commit_hash=None,
                    message=message,
                    timestamp=timestamp,
                    files_changed=[],
                    error_message="No staged changes to commit",
                )

            # Commit changes
            commit_result = self._run_git_command(["commit", "-m", message])

            if commit_result.returncode == 0:
                # Get commit hash
                hash_result = self._run_git_command(["rev-parse", "HEAD"])
                commit_hash = (
                    hash_result.stdout.strip() if hash_result.returncode == 0 else None
                )

                return CommitResult(
                    success=True,
                    commit_hash=commit_hash,
                    message=message,
                    timestamp=timestamp,
                    files_changed=staged_files,
                )
            else:
                return CommitResult(
                    success=False,
                    commit_hash=None,
                    message=message,
                    timestamp=timestamp,
                    files_changed=staged_files,
                    error_message=commit_result.stderr.strip(),
                )

        except Exception as e:
            return CommitResult(
                success=False,
                commit_hash=None,
                message=message,
                timestamp=timestamp,
                files_changed=[],
                error_message=str(e),
            )

    def auto_commit_task(
        self, task_description: str, files: Optional[List[str]] = None
    ) -> CommitResult:
        """
        Automatically stage, generate commit message, and commit for a task.

        Args:
            task_description: Description of the completed task
            files: Optional list of specific files to commit

        Returns:
            CommitResult with operation details
        """
        try:
            # Stage all changes if no specific files provided
            if files is None:
                if not self.stage_files():
                    return CommitResult(
                        success=False,
                        commit_hash=None,
                        message="",
                        timestamp=datetime.now(),
                        files_changed=[],
                        error_message="Failed to stage changes",
                    )

            # Generate commit message
            commit_message = self.generate_commit_message(task_description)

            # Commit with details
            return self.commit_with_details(commit_message, files)

        except Exception as e:
            logger.error(f"Error in auto_commit_task: {e}")
            return CommitResult(
                success=False,
                commit_hash=None,
                message="",
                timestamp=datetime.now(),
                files_changed=[],
                error_message=str(e),
            )
