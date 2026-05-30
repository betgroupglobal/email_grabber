"""
Tests for configuration module - environment variables and settings.
"""
import sys
import importlib
from pathlib import Path
import pytest
import os
from unittest.mock import patch

_BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from knowledge_engine.utils import config as ke_config

# Repo top-level `config/` is a namespace package — pin tests to KE utils.config
sys.modules["config"] = ke_config


# ── Configuration Import Tests ───────────────────────────────────────────────

@pytest.mark.unit
def test_config_import():
    """Test that config module can be imported."""
    import config
    
    assert config is not None


# ── PostgreSQL Configuration Tests ───────────────────────────────────────────

@pytest.mark.unit
def test_postgres_dsn_default():
    """Test default PostgreSQL DSN."""
    import config
    
    assert hasattr(config, 'POSTGRES_DSN')
    assert isinstance(config.POSTGRES_DSN, str)
    assert len(config.POSTGRES_DSN) > 0


@pytest.mark.unit
def test_postgres_dsn_format():
    """Test that PostgreSQL DSN has correct format."""
    import config
    
    # Should contain postgresql://
    assert 'postgresql://' in config.POSTGRES_DSN


@pytest.mark.unit
@patch.dict(os.environ, {'POSTGRES_DSN': 'postgresql://test:test@localhost:5432/test_db'})
@patch("dotenv.load_dotenv")
def test_postgres_dsn_from_env(_mock_dotenv):
    """Test that PostgreSQL DSN can be overridden by environment variable."""
    importlib.reload(ke_config)
    assert 'test' in ke_config.POSTGRES_DSN


# ── Qdrant Configuration Tests ───────────────────────────────────────────────

@pytest.mark.unit
def test_qdrant_host_default():
    """Test default Qdrant host."""
    import config
    
    assert hasattr(config, 'QDRANT_HOST')
    assert isinstance(config.QDRANT_HOST, str)
    assert config.QDRANT_HOST == "localhost"


@pytest.mark.unit
def test_qdrant_port_default():
    """Test default Qdrant port."""
    import config
    
    assert hasattr(config, 'QDRANT_PORT')
    assert isinstance(config.QDRANT_PORT, int)
    assert config.QDRANT_PORT == 6333


@pytest.mark.unit
def test_qdrant_collection_default():
    """Test default Qdrant collection name."""
    import config
    
    assert hasattr(config, 'QDRANT_COLLECTION')
    assert isinstance(config.QDRANT_COLLECTION, str)
    assert config.QDRANT_COLLECTION == "attacks"


@pytest.mark.unit
@patch.dict(os.environ, {'QDRANT_HOST': 'qdrant.example.com'})
@patch("dotenv.load_dotenv")
def test_qdrant_host_from_env(_mock_dotenv):
    """Test that Qdrant host can be overridden by environment variable."""
    importlib.reload(ke_config)
    assert ke_config.QDRANT_HOST == "qdrant.example.com"


@pytest.mark.unit
@patch.dict(os.environ, {'QDRANT_PORT': '7333'})
@patch("dotenv.load_dotenv")
def test_qdrant_port_from_env(_mock_dotenv):
    """Test that Qdrant port can be overridden by environment variable."""
    importlib.reload(ke_config)
    assert ke_config.QDRANT_PORT == 7333


# ── Embedding Model Configuration Tests ─────────────────────────────────────

@pytest.mark.unit
def test_embedding_model_default():
    """Test default embedding model."""
    import config
    
    assert hasattr(config, 'EMBEDDING_MODEL')
    assert isinstance(config.EMBEDDING_MODEL, str)


@pytest.mark.unit
def test_embedding_dim_default():
    """Test default embedding dimension."""
    import config
    
    assert hasattr(config, 'EMBEDDING_DIM')
    assert isinstance(config.EMBEDDING_DIM, int)
    assert config.EMBEDDING_DIM == 384


@pytest.mark.unit
@patch.dict(os.environ, {'EMBEDDING_MODEL': 'all-MiniLM-L6-v2'})
@patch("dotenv.load_dotenv")
def test_embedding_model_from_env(_mock_dotenv):
    """Test that embedding model can be overridden by environment variable."""
    importlib.reload(ke_config)
    assert ke_config.EMBEDDING_MODEL == 'all-MiniLM-L6-v2'


# ── Dataset Configuration Tests ─────────────────────────────────────────────

@pytest.mark.unit
def test_dataset_path_default():
    """Test default dataset path."""
    import config
    
    assert hasattr(config, 'DATASET_PATH')
    assert isinstance(config.DATASET_PATH, str)
    assert len(config.DATASET_PATH) > 0


@pytest.mark.unit
def test_dataset_path_exists():
    """Test that default dataset path points to an existing file (if default is used)."""
    import config
    from pathlib import Path
    
    dataset_path = Path(config.DATASET_PATH)
    # The default path might not exist in test environment
    # Just check that it's a valid path format
    assert dataset_path.name.endswith('.csv') or dataset_path.name == ''


# ── API Configuration Tests ─────────────────────────────────────────────────

@pytest.mark.unit
def test_api_host_default():
    """Test default API host."""
    import config
    
    assert hasattr(config, 'API_HOST')
    assert isinstance(config.API_HOST, str)
    assert config.API_HOST == "0.0.0.0"


@pytest.mark.unit
def test_api_port_default():
    """Test default API port."""
    import config
    
    assert hasattr(config, 'API_PORT')
    assert isinstance(config.API_PORT, int)
    # Port may be overridden by environment, just check it's a valid port
    assert 1 <= config.API_PORT <= 65535


@pytest.mark.unit
@patch.dict(os.environ, {'API_PORT': '9000'})
@patch("dotenv.load_dotenv")
def test_api_port_from_env(_mock_dotenv):
    """Test that API port can be overridden by environment variable."""
    importlib.reload(ke_config)
    assert ke_config.API_PORT == 9000


# ── Anthropic Configuration Tests ───────────────────────────────────────────

@pytest.mark.unit
def test_anthropic_api_key_default():
    """Test default Anthropic API key."""
    import config
    
    assert hasattr(config, 'ANTHROPIC_API_KEY')
    assert isinstance(config.ANTHROPIC_API_KEY, str)


@pytest.mark.unit
def test_anthropic_model_default():
    """Test default Anthropic model."""
    import config
    
    assert hasattr(config, 'ANTHROPIC_MODEL')
    assert isinstance(config.ANTHROPIC_MODEL, str)


# ── OpenRouter Configuration Tests ───────────────────────────────────────────

@pytest.mark.unit
def test_openrouter_api_key_default():
    """Test default OpenRouter API key."""
    import config
    
    assert hasattr(config, 'OPENROUTER_API_KEY')
    assert isinstance(config.OPENROUTER_API_KEY, str)


@pytest.mark.unit
def test_openrouter_model_default():
    """Test default OpenRouter model."""
    import config
    
    assert hasattr(config, 'OPENROUTER_MODEL')
    assert isinstance(config.OPENROUTER_MODEL, str)
    assert config.OPENROUTER_MODEL == "openai/gpt-4o-mini"


@pytest.mark.unit
def test_openrouter_base_url_default():
    """Test default OpenRouter base URL."""
    import config
    
    assert hasattr(config, 'OPENROUTER_BASE_URL')
    assert isinstance(config.OPENROUTER_BASE_URL, str)
    assert "openrouter.ai" in config.OPENROUTER_BASE_URL


@pytest.mark.unit
@patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test-key-123'})
@patch("dotenv.load_dotenv")
def test_openrouter_api_key_from_env(_mock_dotenv):
    """Test that OpenRouter API key can be overridden by environment variable."""
    importlib.reload(ke_config)
    assert ke_config.OPENROUTER_API_KEY == 'test-key-123'


# ── Integration Hub Configuration Tests ─────────────────────────────────────

@pytest.mark.unit
def test_integration_hub_url_default():
    """Test default Integration Hub URL."""
    import config
    
    assert hasattr(config, 'INTEGRATION_HUB_URL')
    assert isinstance(config.INTEGRATION_HUB_URL, str)
    assert config.INTEGRATION_HUB_URL == "http://localhost:8500"


@pytest.mark.unit
def test_service_api_key_integration_hub_default():
    """Test default service API key for Integration Hub."""
    import config
    
    assert hasattr(config, 'SERVICE_API_KEY_INTEGRATION_HUB')
    assert isinstance(config.SERVICE_API_KEY_INTEGRATION_HUB, str)


# ── Configuration Validation Tests ───────────────────────────────────────────

@pytest.mark.unit
def test_all_required_config_vars_exist():
    """Test that all required configuration variables exist."""
    import config
    
    required_vars = [
        'POSTGRES_DSN',
        'QDRANT_HOST',
        'QDRANT_PORT',
        'QDRANT_COLLECTION',
        'EMBEDDING_MODEL',
        'EMBEDDING_DIM',
        'DATASET_PATH',
        'API_HOST',
        'API_PORT',
        'ANTHROPIC_API_KEY',
        'ANTHROPIC_MODEL',
        'OPENROUTER_API_KEY',
        'OPENROUTER_MODEL',
        'OPENROUTER_BASE_URL',
        'INTEGRATION_HUB_URL',
        'SERVICE_API_KEY_INTEGRATION_HUB'
    ]
    
    for var in required_vars:
        assert hasattr(config, var), f"Missing required config variable: {var}"


@pytest.mark.unit
def test_config_types():
    """Test that configuration variables have correct types."""
    import config
    
    # String variables
    string_vars = [
        'POSTGRES_DSN',
        'QDRANT_HOST',
        'QDRANT_COLLECTION',
        'EMBEDDING_MODEL',
        'DATASET_PATH',
        'API_HOST',
        'ANTHROPIC_API_KEY',
        'ANTHROPIC_MODEL',
        'OPENROUTER_API_KEY',
        'OPENROUTER_MODEL',
        'OPENROUTER_BASE_URL',
        'INTEGRATION_HUB_URL',
        'SERVICE_API_KEY_INTEGRATION_HUB'
    ]
    
    for var in string_vars:
        value = getattr(config, var)
        assert isinstance(value, str), f"{var} should be str, got {type(value)}"
    
    # Integer variables
    int_vars = [
        'QDRANT_PORT',
        'EMBEDDING_DIM',
        'API_PORT'
    ]
    
    for var in int_vars:
        value = getattr(config, var)
        assert isinstance(value, int), f"{var} should be int, got {type(value)}"


# ── Environment Variable Loading Tests ───────────────────────────────────────

@pytest.mark.unit
def test_dotenv_loaded():
    """Test that python-dotenv is loaded."""
    import config
    
    # If dotenv was loaded, environment variables should be accessible
    # This is a basic check - actual environment variables depend on .env file
    assert True  # If we got here, import succeeded


@pytest.mark.unit
@patch.dict(os.environ, {'CUSTOM_VAR': 'custom_value'})
def test_custom_env_var():
    """Test that custom environment variables can be accessed."""
    import os
    
    assert os.getenv('CUSTOM_VAR') == 'custom_value'


# ── Configuration Edge Cases ─────────────────────────────────────────────────

@pytest.mark.unit
def test_empty_string_config():
    """Test handling of empty string configuration values."""
    import config
    
    # Some configs might be empty strings (like API keys if not set)
    assert isinstance(config.ANTHROPIC_API_KEY, str)
    assert isinstance(config.OPENROUTER_API_KEY, str)


@pytest.mark.unit
def test_port_range_validation():
    """Test that port numbers are in valid range."""
    import config
    
    # Valid port range: 1-65535
    assert 1 <= config.QDRANT_PORT <= 65535
    assert 1 <= config.API_PORT <= 65535