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

# Embedding model
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "all-MiniLM-L6-v2"          # fast, 384-dim, runs on CPU
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
