# Knowledge Engine Test Suite

Comprehensive pytest-based test suite for the Knowledge Engine service.

## Test Structure

```
tests/
├── conftest.py                 # Pytest fixtures and configuration
├── fixtures/
│   ├── __init__.py
│   └── test_data.py            # Sample test data
├── test_api.py                 # FastAPI endpoint tests (priority)
├── test_searcher.py            # Search functionality tests
├── test_attack_chainer.py      # Attack chain building tests
├── test_ml_service.py          # ML service tests
├── test_opsec_audit.py         # OpSec audit engine tests
├── test_ingestor.py            # Data ingestion tests
├── test_claude_analyst.py      # AI analysis tests
├── test_models.py              # Pydantic model validation tests
└── test_config.py              # Configuration tests
```

## Prerequisites

Before running tests, ensure the following services are running:

- **PostgreSQL** (default: localhost:5432)
- **Qdrant** (default: localhost:6333)

### Environment Variables

Set the following environment variables in `.env`:

```bash
# Database
POSTGRES_DSN=postgresql://opsec:opsec@localhost:5432/attack_db

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=attacks

# API Keys (optional, for AI features)
OPENROUTER_API_KEY=your_openrouter_key
SERVICE_API_KEY_ORCHESTRATOR=your_service_key
```

## Installation

Install test dependencies:

```bash
pip install -r requirements.txt
```

## Running Tests

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test File

```bash
pytest tests/test_api.py
```

### Run Specific Test Function

```bash
pytest tests/test_api.py::test_login_success
```

### Run Tests by Marker

```bash
# Run only unit tests (no external services)
pytest tests/ -m unit

# Run only integration tests (require external services)
pytest tests/ -m integration

# Skip slow tests
pytest tests/ -m "not slow"
```

### Run with Coverage

```bash
# Generate coverage report
pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

# View HTML coverage report
open htmlcov/index.html
```

### Run with Verbose Output

```bash
pytest tests/ -v
```

### Run with Specific Verbosity

```bash
# Very verbose (show print statements)
pytest tests/ -vv -s
```

## Test Categories

### Priority Tests (API Endpoints)

- `test_api.py` - All FastAPI endpoints
  - Authentication (login, refresh, user management)
  - Search endpoints (semantic, keyword, MITRE, categories)
  - Attack vector builder
  - OpSec endpoints
  - AI endpoints
  - ML service endpoints

### Core Functionality Tests

- `test_searcher.py` - Semantic and structured search
- `test_attack_chainer.py` - Attack chain building and ML enhancement
- `test_ml_service.py` - ML model predictions
- `test_opsec_audit.py` - OpSec risk assessment

### Data Pipeline Tests

- `test_ingestor.py` - CSV ingestion to PostgreSQL and Qdrant
- `test_claude_analyst.py` - AI analysis and chat functionality

### Validation Tests

- `test_models.py` - Pydantic model validation
- `test_config.py` - Configuration and environment variables

## Test Markers

- `@pytest.mark.integration` - Tests requiring external services (PostgreSQL, Qdrant)
- `@pytest.mark.unit` - Tests that can run without external services
- `@pytest.mark.slow` - Tests that take longer to run (e.g., real API calls)

## Fixtures

Key fixtures defined in `conftest.py`:

- `client` - FastAPI TestClient for API testing
- `searcher` - AttackSearcher instance
- `chainer` - AttackChainer instance
- `ml_service` - ML service instance
- `opsec_engine` - OpSec audit engine instance
- `pg_connection` - PostgreSQL connection
- `qdrant_client` - Qdrant client
- `insert_test_records` - Inserts sample test data
- `admin_token` - Admin authentication token
- `service_auth_headers` - Service authentication headers

## Test Data

Sample test data is provided in `fixtures/test_data.py`:

- Sample attack records covering various categories
- Sample users for authentication tests
- Sample attack vector requests
- Sample OpSec audit requests

## Troubleshooting

### Tests Fail with Database Connection Error

Ensure PostgreSQL is running:
```bash
# Check PostgreSQL status
brew services list  # macOS
systemctl status postgresql  # Linux

# Start PostgreSQL
brew services start postgresql  # macOS
systemctl start postgresql  # Linux
```

### Tests Fail with Qdrant Connection Error

Ensure Qdrant is running:
```bash
# Using Docker
docker run -p 6333:6333 qdrant/qdrant

# Or using Docker Compose (from project root)
docker compose up -d qdrant
```

### Tests Fail with Authentication Errors

Ensure service API keys are configured in `.env`:
```bash
SERVICE_API_KEY_ORCHESTRATOR=your_service_key
```

### ML Tests Are Skipped

ML tests will be skipped if:
- ML models are not available in `ml_models/` or `models/` directory
- NLTK data is not downloaded (will be downloaded automatically on first run)

### AI Tests Are Skipped

AI tests will be skipped if:
- `OPENROUTER_API_KEY` is not configured in `.env`
- OpenRouter API is unreachable

## Best Practices

1. **Run tests before committing** - Ensure all tests pass before pushing code
2. **Use markers appropriately** - Mark integration tests to separate them from unit tests
3. **Keep tests isolated** - Each test should be independent and not rely on other tests
4. **Clean up resources** - Use fixtures to ensure proper cleanup after tests
5. **Mock external services** - Use mocks for tests that don't need real external services
6. **Test edge cases** - Include tests for error conditions and edge cases

## Adding New Tests

1. Create a new test file in `tests/` directory (e.g., `test_new_feature.py`)
2. Import necessary modules and fixtures
3. Write test functions following the naming convention `test_*`
4. Use appropriate markers (`@pytest.mark.integration`, `@pytest.mark.unit`)
5. Run the new tests to verify they work

Example:

```python
import pytest
from searcher import AttackSearcher

@pytest.mark.integration
def test_new_feature(searcher):
    """Test new feature."""
    result = searcher.new_feature()
    assert result is not None
```

## Continuous Integration

These tests are designed to run in CI/CD pipelines. Example CI configuration:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pytest tests/ -m unit  # Run unit tests first
    pytest tests/ -m integration  # Then run integration tests
```

## Coverage Goals

- **Overall coverage**: Target > 80%
- **API endpoints**: 100% coverage (priority)
- **Core functionality**: > 90% coverage
- **Data pipeline**: > 85% coverage

## Support

For issues or questions about the test suite:
1. Check the troubleshooting section above
2. Review pytest documentation: https://docs.pytest.org/
3. Check project documentation in [AGENTS.md](../guides/AGENTS.md)