import os
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL
POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://opsec:opsec@localhost:5432/attack_db"
)

# Qdrant
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "attacks")

# Embedding model (fastembed / ONNX — fast, 384-dim, CPU-only)
# Options: BAAI/bge-small-en-v1.5 (default, fast), all-MiniLM-L6-v2 (higher quality)
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "BAAI/bge-small-en-v1.5"  # Enabled - fast embedding model
)
EMBEDDING_DIM = 384

# Dataset
DATASET_PATH = os.getenv(
    "DATASET_PATH",
    "/Users/adminuser/attack-dataset/Attack_Dataset.csv"
)

# API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Jailbreak AI
JAILBREAK_API_KEY = os.getenv("JAILBREAK_API_KEY", "")
JAILBREAK_MODEL = os.getenv("JAILBREAK_MODEL", "jailbreak-ai")
JAILBREAK_BASE_URL = "https://jail-break.chat/v1"

# Integration Hub
INTEGRATION_HUB_URL = os.getenv("INTEGRATION_HUB_URL", "http://localhost:8500")
SERVICE_API_KEY_INTEGRATION_HUB = os.getenv("SERVICE_API_KEY_INTEGRATION_HUB", "")
