# Contributing to Investment Agent

Thanks for your interest in contributing! This project was built with AI-assisted development, and we encourage contributors to use AI coding tools (Claude Code, Copilot, Cursor, etc.) to work on issues.

## Getting Started

```bash
git clone https://github.com/FredHuFuture/investment_agent.git
cd investment_agent
python -m pip install -e ".[dev]"
python -m pytest tests/ -q  # Make sure everything passes
```

For frontend:
```bash
cd frontend
npm install
npm run dev
```

## Development Workflow

1. Pick an issue from [GitHub Issues](https://github.com/FredHuFuture/investment_agent/issues)
2. Fork the repo and create a branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `python -m pytest tests/ -q`
5. For frontend changes: `cd frontend && npx tsc --noEmit`
6. Submit a PR

## Project Structure

- `agents/` -- Analysis agents (technical, fundamental, macro, crypto, summary)
- `engine/` -- Signal aggregation, pipeline, drift analysis
- `portfolio/` -- Position management and thesis tracking
- `api/` -- FastAPI REST endpoints
- `frontend/` -- React + TypeScript dashboard
- `tests/` -- pytest test suite (216+ tests)

## Code Style

- Python: Standard library conventions, type hints, async/await
- TypeScript: Strict mode, functional components, Tailwind for styling
- Tests: One test file per module (`tests/test_NNN_name.py`)
- Keep it simple: No over-engineering, no premature abstractions

## Writing Tests

Every PR should include tests. Follow the existing pattern:

```python
# tests/test_NNN_feature.py
import pytest
from your_module import YourClass

@pytest.fixture
async def setup():
    db_path = ":memory:"
    # setup...
    yield db_path

async def test_your_feature(setup):
    # test...
    assert result == expected
```

## Areas We Need Help

- **New indicators**: Add technical indicators to `agents/technical.py`
- **Data providers**: Integrate new data sources in `data_providers/`
- **Frontend**: UI improvements, new chart types, mobile responsiveness
- **Documentation**: Code examples, API docs, tutorials
- **Testing**: Improve coverage, add integration tests

## AI-Assisted Development Tips

This project was built almost entirely with AI coding assistants. If you're using one:

1. Start by reading the relevant source files -- give the AI context
2. Look at existing tests for patterns -- AI tools are great at following established patterns
3. Run tests frequently -- catch issues early
4. Review AI output carefully -- especially for edge cases and error handling

## Questions?

Open an issue or start a discussion. We're happy to help!
