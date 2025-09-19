"""
Unit tests for GitAgent component.

This module tests the git automation functionality including
commit message generation, file staging, and commit operations.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from pathlib import Path
import subprocess

from ozb_deal_filter.components.git_agent import GitAgent
from ozb_deal_filter.models.git import CommitResult, GitStatus


class TestGitAgent:
    """Test cases for GitAgent class."""

    @pytest.fixture
    def mock_git_repo(self, tmp_path: Path) -> Path:
        """Create a mock git repository for testing."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        return tmp_path

    @pytest.fixture
    def git_agent(self, mock_git_repo: Path) -> GitAgent:
        """Create GitAgent instance for testing."""
        return GitAgent(str(mock_git_repo))

    def test_init_valid_repo(self, mock_git_repo: Path) -> None:
        """Test GitAgent initialization with valid repository."""
        agent = GitAgent(str(mock_git_repo))
        assert agent.repo_path == mock_git_repo

    def test_init_invalid_repo(self, tmp_path: Path) -> None:
        """Test GitAgent initialization with invalid repository."""
        invalid_path = tmp_path / "not_a_repo"
        invalid_path.mkdir()

        with pytest.raises(ValueError, match="No git repository found"):
            GitAgent(str(invalid_path))

    def test_init_default_path(self) -> None:
        """Test GitAgent initialization with default path."""
        with patch("pathlib.Path.cwd") as mock_cwd, patch.object(
            Path, "exists", return_value=True
        ):
            mock_cwd.return_value = Path("/fake/repo")
            agent = GitAgent()
            assert agent.repo_path == Path("/fake/repo")

    @patch("subprocess.run")
    def test_run_git_command_success(self, mock_run: Mock, git_agent: GitAgent) -> None:
        """Test successful git command execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "success output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = git_agent._run_git_command(["status"])

        mock_run.assert_called_once_with(
            ["git", "status"],
            cwd=git_agent.repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result == mock_result

    @patch("subprocess.run")
    def test_run_git_command_timeout(self, mock_run: Mock, git_agent: GitAgent) -> None:
        """Test git command timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 30)

        with pytest.raises(subprocess.TimeoutExpired):
            git_agent._run_git_command(["status"])

    @patch("subprocess.run")
    def test_get_status_success(self, mock_run: Mock, git_agent: GitAgent) -> None:
        """Test successful git status retrieval."""
        # Mock branch command
        branch_result = Mock()
        branch_result.returncode = 0
        branch_result.stdout = "main\n"

        # Mock status command
        status_result = Mock()
        status_result.returncode = 0
        status_result.stdout = (
            " M modified_file.py\nA  new_file.py\n?? untracked_file.py\n"
        )

        mock_run.side_effect = [branch_result, status_result]

        status = git_agent.get_status()

        assert status.current_branch == "main"
        assert status.has_changes is True
        assert "new_file.py" in status.staged_files
        assert "modified_file.py" in status.unstaged_files
        assert "untracked_file.py" in status.untracked_files

    @patch("subprocess.run")
    def test_get_status_no_changes(self, mock_run: Mock, git_agent: GitAgent) -> None:
        """Test git status with no changes."""
        # Mock branch command
        branch_result = Mock()
        branch_result.returncode = 0
        branch_result.stdout = "main\n"

        # Mock status command
        status_result = Mock()
        status_result.returncode = 0
        status_result.stdout = ""

        mock_run.side_effect = [branch_result, status_result]

        status = git_agent.get_status()

        assert status.has_changes is False
        assert len(status.staged_files) == 0
        assert len(status.unstaged_files) == 0
        assert len(status.untracked_files) == 0

    @patch("subprocess.run")
    def test_stage_files_all(self, mock_run: Mock, git_agent: GitAgent) -> None:
        """Test staging all files."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = git_agent.stage_files()

        mock_run.assert_called_once_with(
            ["git", "add", "."],
            cwd=git_agent.repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result is True

    @patch("subprocess.run")
    def test_stage_files_specific(self, mock_run: Mock, git_agent: GitAgent) -> None:
        """Test staging specific files."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        files = ["file1.py", "file2.py"]
        result = git_agent.stage_files(files)

        mock_run.assert_called_once_with(
            ["git", "add", "file1.py", "file2.py"],
            cwd=git_agent.repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result is True

    @patch("subprocess.run")
    def test_stage_files_failure(self, mock_run: Mock, git_agent: GitAgent) -> None:
        """Test staging files failure."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "error staging files"
        mock_run.return_value = mock_result

        result = git_agent.stage_files()
        assert result is False

    def test_generate_commit_message_basic(self, git_agent: GitAgent) -> None:
        """Test basic commit message generation."""
        task_desc = "1.1 Create basic functionality"
        message = git_agent.generate_commit_message(task_desc)

        assert message == "feat: [Task 1.1] Create basic functionality"

    def test_generate_commit_message_test_task(self, git_agent: GitAgent) -> None:
        """Test commit message generation for test task."""
        task_desc = "2.3 Write unit tests for parser"
        message = git_agent.generate_commit_message(task_desc)

        assert message == "test: [Task 2.3] Write unit tests for parser"

    def test_generate_commit_message_fix_task(self, git_agent: GitAgent) -> None:
        """Test commit message generation for fix task."""
        task_desc = "3.1 Fix bug in validation logic"
        message = git_agent.generate_commit_message(task_desc)

        assert message == "fix: [Task 3.1] Fix bug in validation logic"

    def test_generate_commit_message_no_number(self, git_agent: GitAgent) -> None:
        """Test commit message generation without task number."""
        task_desc = "Implement new feature"
        message = git_agent.generate_commit_message(task_desc)

        assert message == "feat: [Task X.X] Implement new feature"

    def test_generate_commit_message_decimal_number(self, git_agent: GitAgent) -> None:
        """Test commit message generation with decimal task number."""
        task_desc = "4.2.1 Add validation method"
        message = git_agent.generate_commit_message(task_desc)

        assert message == "feat: [Task 4.2] Add validation method"

    @patch.object(GitAgent, "get_status")
    @patch("subprocess.run")
    def test_commit_changes_success(self, mock_run: Mock, mock_get_status: Mock, git_agent: GitAgent) -> None:
        """Test successful commit operation."""
        # Mock status with staged files
        mock_status = GitStatus(
            has_changes=True,
            staged_files=["file1.py"],
            unstaged_files=[],
            untracked_files=[],
            current_branch="main",
        )
        mock_get_status.return_value = mock_status

        # Mock successful commit
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = git_agent.commit_changes("test commit message")

        mock_run.assert_called_once_with(
            ["git", "commit", "-m", "test commit message"],
            cwd=git_agent.repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result is True

    @patch.object(GitAgent, "get_status")
    def test_commit_changes_no_staged_files(self, mock_get_status: Mock, git_agent: GitAgent) -> None:
        """Test commit with no staged files."""
        # Mock status with no staged files
        mock_status = GitStatus(
            has_changes=False,
            staged_files=[],
            unstaged_files=[],
            untracked_files=[],
            current_branch="main",
        )
        mock_get_status.return_value = mock_status

        result = git_agent.commit_changes("test commit message")
        assert result is False

    @patch.object(GitAgent, "get_status")
    @patch("subprocess.run")
    def test_commit_changes_failure(self, mock_run: Mock, mock_get_status: Mock, git_agent: GitAgent) -> None:
        """Test failed commit operation."""
        # Mock status with staged files
        mock_status = GitStatus(
            has_changes=True,
            staged_files=["file1.py"],
            unstaged_files=[],
            untracked_files=[],
            current_branch="main",
        )
        mock_get_status.return_value = mock_status

        # Mock failed commit
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "commit failed"
        mock_run.return_value = mock_result

        result = git_agent.commit_changes("test commit message")
        assert result is False

    @patch.object(GitAgent, "get_status")
    @patch("subprocess.run")
    def test_commit_with_details_success(self, mock_run: Mock, mock_get_status: Mock, git_agent: GitAgent) -> None:
        """Test detailed commit operation success."""
        # Mock status with staged files
        mock_status = GitStatus(
            has_changes=True,
            staged_files=["file1.py", "file2.py"],
            unstaged_files=[],
            untracked_files=[],
            current_branch="main",
        )
        mock_get_status.return_value = mock_status

        # Mock successful commit and hash retrieval
        commit_result = Mock()
        commit_result.returncode = 0

        hash_result = Mock()
        hash_result.returncode = 0
        hash_result.stdout = "abc123def456\n"

        mock_run.side_effect = [commit_result, hash_result]

        result = git_agent.commit_with_details("test commit")

        assert result.success is True
        assert result.commit_hash == "abc123def456"
        assert result.message == "test commit"
        assert result.files_changed == ["file1.py", "file2.py"]
        assert result.error_message is None

    @patch.object(GitAgent, "get_status")
    def test_commit_with_details_no_staged_files(self, mock_get_status: Mock, git_agent: GitAgent) -> None:
        """Test detailed commit with no staged files."""
        # Mock status with no staged files
        mock_status = GitStatus(
            has_changes=False,
            staged_files=[],
            unstaged_files=[],
            untracked_files=[],
            current_branch="main",
        )
        mock_get_status.return_value = mock_status

        result = git_agent.commit_with_details("test commit")

        assert result.success is False
        assert result.error_message == "No staged changes to commit"

    @patch.object(GitAgent, "stage_files")
    @patch.object(GitAgent, "commit_with_details")
    def test_auto_commit_task_success(self, mock_commit: Mock, mock_stage: Mock, git_agent: GitAgent) -> None:
        """Test successful auto commit task."""
        mock_stage.return_value = True

        expected_result = CommitResult(
            success=True,
            commit_hash="abc123",
            message="feat: [Task 1.1] Create basic functionality",
            timestamp=datetime.now(),
            files_changed=["file1.py"],
        )
        mock_commit.return_value = expected_result

        result = git_agent.auto_commit_task("1.1 Create basic functionality")

        mock_stage.assert_called_once_with()
        mock_commit.assert_called_once_with(
            "feat: [Task 1.1] Create basic functionality", None
        )
        assert result == expected_result

    @patch.object(GitAgent, "stage_files")
    def test_auto_commit_task_staging_failure(self, mock_stage: Mock, git_agent: GitAgent) -> None:
        """Test auto commit task with staging failure."""
        mock_stage.return_value = False

        result = git_agent.auto_commit_task("1.1 Create basic functionality")

        assert result.success is False
        assert result.error_message == "Failed to stage changes"

    @patch.object(GitAgent, "commit_with_details")
    def test_auto_commit_task_with_specific_files(self, mock_commit: Mock, git_agent: GitAgent) -> None:
        """Test auto commit task with specific files."""
        expected_result = CommitResult(
            success=True,
            commit_hash="abc123",
            message="feat: [Task 2.1] Update specific files",
            timestamp=datetime.now(),
            files_changed=["file1.py", "file2.py"],
        )
        mock_commit.return_value = expected_result

        files = ["file1.py", "file2.py"]
        result = git_agent.auto_commit_task("2.1 Update specific files", files)

        mock_commit.assert_called_once_with(
            "feat: [Task 2.1] Update specific files", files
        )
        assert result == expected_result


class TestCommitResult:
    """Test cases for CommitResult data model."""

    def test_valid_commit_result(self) -> None:
        """Test valid commit result creation."""
        result = CommitResult(
            success=True,
            commit_hash="abc123",
            message="test commit",
            timestamp=datetime.now(),
            files_changed=["file1.py"],
        )

        result.validate()  # Should not raise

    def test_invalid_success_type(self) -> None:
        """Test commit result with invalid success type."""
        result = CommitResult(
            success=True,  # Fixed: should be boolean
            commit_hash="abc123",
            message="test commit",
            timestamp=datetime.now(),
            files_changed=["file1.py"],
        )
        # Create invalid result by directly setting attribute
        result.success = "true"  # type: ignore

        with pytest.raises(ValueError, match="success must be a boolean"):
            result.validate()

    def test_empty_message(self) -> None:
        """Test commit result with empty message."""
        result = CommitResult(
            success=True,
            commit_hash="abc123",
            message="",  # Empty message
            timestamp=datetime.now(),
            files_changed=["file1.py"],
        )

        with pytest.raises(ValueError, match="message cannot be empty"):
            result.validate()

    def test_invalid_files_changed_type(self) -> None:
        """Test commit result with invalid files_changed type."""
        result = CommitResult(
            success=True,
            commit_hash="abc123",
            message="test commit",
            timestamp=datetime.now(),
            files_changed=["file1.py"],
        )
        # Create invalid result by directly setting attribute
        result.files_changed = "file1.py"  # type: ignore

        with pytest.raises(ValueError, match="files_changed must be a list"):
            result.validate()

    def test_successful_commit_without_hash(self) -> None:
        """Test successful commit result without commit hash."""
        result = CommitResult(
            success=True,
            commit_hash=None,  # Missing hash for successful commit
            message="test commit",
            timestamp=datetime.now(),
            files_changed=["file1.py"],
        )

        with pytest.raises(
            ValueError, match="commit_hash required for successful commits"
        ):
            result.validate()


class TestGitStatus:
    """Test cases for GitStatus data model."""

    def test_valid_git_status(self) -> None:
        """Test valid git status creation."""
        status = GitStatus(
            has_changes=True,
            staged_files=["file1.py"],
            unstaged_files=["file2.py"],
            untracked_files=["file3.py"],
            current_branch="main",
        )

        status.validate()  # Should not raise

    def test_invalid_has_changes_type(self) -> None:
        """Test git status with invalid has_changes type."""
        status = GitStatus(
            has_changes=True,
            staged_files=["file1.py"],
            unstaged_files=["file2.py"],
            untracked_files=["file3.py"],
            current_branch="main",
        )
        # Create invalid status by directly setting attribute
        status.has_changes = "true"  # type: ignore

        with pytest.raises(ValueError, match="has_changes must be a boolean"):
            status.validate()

    def test_invalid_file_list_type(self) -> None:
        """Test git status with invalid file list type."""
        status = GitStatus(
            has_changes=True,
            staged_files=["file1.py"],
            unstaged_files=["file2.py"],
            untracked_files=["file3.py"],
            current_branch="main",
        )
        # Create invalid status by directly setting attribute
        status.staged_files = "file1.py"  # type: ignore

        with pytest.raises(ValueError, match="file lists must be lists"):
            status.validate()

    def test_empty_current_branch(self) -> None:
        """Test git status with empty current branch."""
        status = GitStatus(
            has_changes=True,
            staged_files=["file1.py"],
            unstaged_files=["file2.py"],
            untracked_files=["file3.py"],
            current_branch="",  # Empty branch name
        )

        with pytest.raises(ValueError, match="current_branch cannot be empty"):
            status.validate()
