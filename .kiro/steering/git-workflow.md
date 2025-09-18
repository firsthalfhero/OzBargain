# Git Workflow & Commit Rules

## Task Completion Workflow

### Commit Requirements
- **MANDATORY**: Commit and publish changes at the completion of each task
- **NEVER** leave uncommitted changes after completing a task
- **ALWAYS** include meaningful commit messages that reference the task

### Commit Message Format
```
feat: [Task X.X] Brief description of changes

- Detailed description of what was implemented
- Reference to specific requirements addressed
- Any notable technical decisions or patterns used

Task: X.X Task Name from tasks.md
Requirements: Reference to specific requirements (e.g., Req 1.1, 2.3)
```

### Examples
```
feat: [Task 1.1] Set up project structure and core interfaces

- Created directory structure for models, services, repositories, and API components
- Defined protocol interfaces in interfaces.py for system boundaries
- Added type hints and validation patterns

Task: 1.1 Set up project structure and core interfaces
Requirements: 1.1, 2.1
```

```
feat: [Task 2.3] Implement Document model with relationships

- Added Document dataclass with relationship handling
- Implemented validation methods for data integrity
- Created unit tests for relationship management
- Added comprehensive type hints

Task: 2.3 Implement Document model with relationships
Requirements: 2.1, 3.3, 1.2
```

### Commit Process
1. **Complete the task** - Implement all required functionality
2. **Run quality checks** - Ensure code passes linting, typing, and tests
3. **Stage changes** - Add all relevant files to git staging
4. **Commit with proper message** - Use the format above
5. **Push to repository** - Publish changes immediately

### Quality Gates Before Commit
- All new code has appropriate type hints
- Code follows project formatting standards (black, flake8)
- All tests pass (pytest)
- Type checking passes (mypy)
- No syntax errors or import issues

### Commands to Execute
```bash
# Quality checks
black ozb_deal_filter/
flake8 ozb_deal_filter/
mypy ozb_deal_filter/
pytest

# Git workflow
git add .
git commit -m "feat: [Task X.X] Brief description"
git push origin main
```

## Branch Strategy
- Work directly on `main` branch for task execution
- Each task completion results in a commit to main
- No feature branches needed for spec task execution

## Documentation Updates
- Update README.md if task affects user-facing functionality
- Update configuration examples if new config options added
- Commit documentation changes with the task implementation