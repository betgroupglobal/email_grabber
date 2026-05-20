# OpsecAI Test Suite

Welcome to the comprehensive test suite for the OpsecAI platform. This directory contains all test files organized by component and service.

## 📚 Test Structure

### 🧪 Integration Tests (`integrations/`)
Tests for the Integration Hub and plugin system.

- **test_jailbreak_ai.py** - Jailbreak AI integration tests
- **test_jailbreak_integration.py** - Integration workflow tests
- **test_jailbreak_offensive.py** - Offensive operation tests
- **test_plugin_system.py** - Plugin system core functionality
- **test_redteam_automation.py** - Red team automation tests

### 🧠 Knowledge Engine Tests (`knowledge-engine/`)
Tests for the Knowledge Engine service including semantic search, attack chain building, and ML integration.

- **test_api.py** - API endpoint tests
- **test_attack_chainer.py** - Attack chain building logic
- **test_claude_analyst.py** - AI analyst functionality
- **test_config.py** - Configuration management
- **test_ingestor.py** - Data ingestion pipeline
- **test_ml_service.py** - ML model integration
- **test_models.py** - Database model tests
- **test_opsec_audit.py** - OpSec assessment logic
- **test_searcher.py** - Semantic search functionality
- **conftest.py** - Pytest configuration and fixtures
- **__init__.py** - Test module initialization

### 🔧 Shared Backend Tests (`shared/`)
Shared backend utilities and robustness tests.

- **test_robustness_synergy.py** - Robustness feature synergy tests

### 🎨 Frontend Tests (`frontend/`)
Frontend React component tests.

- **App.test.tsx** - Main App component tests

### 🌐 End-to-End Tests (`e2e/`)
System-level integration tests and endpoint validation.

- **test_all_endpoints.py** - Original endpoint test suite
- **test_all_endpoints_corrected.py** - Corrected endpoint test suite
- **test_enhanced_menu.py** - Enhanced menu system tests
- **test_enhanced_monitoring.py** - Enhanced monitoring tests
- **test_kill_functionality.py** - Kill switch functionality tests
- **test_menu_system.py** - Menu system tests

### 📊 Test Fixtures (`fixtures/`)
Shared test data and fixtures.

- **__init__.py** - Fixtures module initialization
- **test_data.py** - Test data fixtures

### ⚙️ Test Configuration

- **pytest.ini** - Pytest configuration for Knowledge Engine tests

## 🚀 Running Tests

### Run All Tests
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=backend --cov-report=html
```

### Run Specific Test Categories
```bash
# Integration tests
pytest tests/integrations/

# Knowledge Engine tests
pytest tests/knowledge-engine/

# Shared tests
pytest tests/shared/

# Frontend tests
cd frontend/dashboard
npm test

# E2E tests
pytest tests/e2e/
```

### Run Individual Test Files
```bash
# Specific test file
pytest tests/integrations/test_plugin_system.py

# Specific test function
pytest tests/knowledge-engine/test_api.py::test_search_endpoint
```

### Run with Verbose Output
```bash
pytest tests/ -v
```

### Run with Detailed Output
```bash
pytest tests/ -vv -s
```

## 📋 Test Coverage

### Integration Hub
- Plugin system functionality
- API integration workflows
- Red team automation
- Offensive operations
- Jailbreak AI integration

### Knowledge Engine
- Semantic search accuracy
- Attack chain building
- ML model predictions
- API endpoint functionality
- Data ingestion pipeline
- OpSec assessment logic
- Configuration management

### Shared Components
- Robustness features (retry logic, circuit breakers)
- Error handling
- Configuration validation
- Health checks

### Frontend
- Component rendering
- User interactions
- State management
- Navigation

### End-to-End
- Service-to-service communication
- API endpoint validation
- System integration
- Error scenarios
- Performance under load

## 🔍 Test Results

### Recent Test Runs
- **Endpoint Tests**: 21/21 passing (100%) - [FINAL_TEST_RESULTS.md](../docs/testing/FINAL_TEST_RESULTS.md)
- **Robustness Synergy Tests**: 7/7 passing (100%) - [ROBUSTNESS_SYNERGY_TEST_RESULTS.md](../docs/testing/ROBUSTNESS_SYNERGY_TEST_RESULTS.md)
- **Knowledge Engine Tests**: Comprehensive coverage documented in [knowledge-engine-tests.md](../docs/testing/knowledge-engine-tests.md)

## 🛠️ Test Development Guidelines

### Writing New Tests
1. Place test files in the appropriate category directory
2. Follow naming convention: `test_<feature>.py`
3. Use descriptive test function names: `test_<specific_behavior>`
4. Include docstrings explaining what is being tested
5. Use fixtures from `fixtures/` for shared test data

### Test Structure
```python
def test_<feature>_<behavior>():
    """Test that <feature> does <behavior> under <conditions>."""
    # Arrange
    # Set up test data and conditions
    
    # Act
    # Execute the code being tested
    
    # Assert
    # Verify the expected outcome
    assert expected_result == actual_result
```

### Best Practices
- Keep tests independent and isolated
- Use descriptive assertion messages
- Mock external dependencies (APIs, databases)
- Test both success and failure scenarios
- Maintain high test coverage (>80%)
- Run tests locally before committing

## 🐛 Debugging Tests

### Run with Debugger
```bash
# Run with pdb debugger
pytest tests/ --pdb

# Run with ipdb debugger
pytest tests/ --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb
```

### Stop at First Failure
```bash
pytest tests/ -x
```

### Run Specific Test Pattern
```bash
# Run tests matching pattern
pytest tests/ -k "test_search"
```

### Show Print Statements
```bash
pytest tests/ -s
```

## 📊 Continuous Integration

Tests are automatically run on:
- Pull request creation
- Code commits to main branch
- Scheduled nightly runs

Test results are reported in:
- GitHub Actions logs
- Test coverage reports
- Quality dashboards

## 🔗 Related Documentation

- [Testing Documentation](../docs/testing/) - Detailed testing guides and results
- [Architecture](../docs/architecture/) - System architecture for context
- [API Reference](../docs/guides/AGENTS.md) - API endpoint documentation
- [Enhancement Roadmap](../docs/architecture/MAJOR_ENHANCEMENT_PLAN.md) - Testing improvements planned

## 📝 Contributing

When adding new tests:
1. Place files in appropriate category directory
2. Update this README with new test descriptions
3. Ensure tests pass locally
4. Update test coverage documentation
5. Follow existing naming and structure conventions

## 🆘 Support

For test-related issues:
1. Check test logs and error messages
2. Review debugging section above
3. Consult service-specific documentation
4. Check [AGENTS.md](../docs/guides/AGENTS.md) for architecture context

---

**Last Updated:** 2026-05-18  
**Test Suite Version:** 2.0  
**Total Test Files:** 24+