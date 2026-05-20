#!/usr/bin/env python3
"""
AI Training Script for Attack Patterns Database
Trains ML models on security attack patterns for classification, embeddings, and analysis.
"""

import os
import sys
import argparse
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd

# Database connectivity
import psycopg2
from psycopg2.extras import RealDictCursor

# ML/MLL imports
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.preprocessing import LabelEncoder
import joblib

# NLP imports
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AttackDataLoader:
    """Loads and preprocesses attack pattern data from database or backup file."""
    
    def __init__(self, db_config: Optional[Dict] = None, backup_file: Optional[str] = None):
        self.db_config = db_config or {
            'host': 'localhost',
            'port': 5432,
            'database': 'attack_db',
            'user': 'opsec',
            'password': 'opsec'
        }
        self.backup_file = backup_file
        self.conn = None
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))
        
    def connect_db(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            logger.info("Database connection established")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def load_from_database(self) -> pd.DataFrame:
        """Load attack patterns directly from PostgreSQL database."""
        if not self.connect_db():
            raise ConnectionError("Could not connect to database")
        
        query = """
        SELECT id, title, category, attack_type, scenario_description, 
               tools_used, attack_steps, target_type, vulnerability, 
               mitre_technique, impact, detection_method, solution, tags, source
        FROM attacks
        """
        
        try:
            df = pd.read_sql_query(query, self.conn)
            logger.info(f"Loaded {len(df)} attack patterns from database")
            return df
        except Exception as e:
            logger.error(f"Error loading from database: {e}")
            raise
        finally:
            if self.conn:
                self.conn.close()
    
    def load_from_backup(self) -> pd.DataFrame:
        """Load attack patterns from SQL backup file."""
        if not self.backup_file:
            raise ValueError("Backup file path not provided")
        
        logger.info(f"Loading data from backup file: {self.backup_file}")
        
        # Parse the backup file to extract attack data
        attacks_data = []
        in_copy_section = False
        
        with open(self.backup_file, 'r', encoding='utf-8') as f:
            for line in f:
                if 'COPY public.attacks' in line:
                    in_copy_section = True
                    continue
                elif in_copy_section and line.strip() == '\\.':
                    in_copy_section = False
                    break
                elif in_copy_section:
                    # Parse tab-separated values
                    values = line.strip().split('\t')
                    if len(values) == 15:
                        attacks_data.append({
                            'id': int(values[0]),
                            'title': values[1],
                            'category': values[2],
                            'attack_type': values[3],
                            'scenario_description': values[4],
                            'tools_used': values[5],
                            'attack_steps': values[6],
                            'target_type': values[7],
                            'vulnerability': values[8],
                            'mitre_technique': values[9],
                            'impact': values[10],
                            'detection_method': values[11],
                            'solution': values[12],
                            'tags': values[13],
                            'source': values[14]
                        })
        
        df = pd.DataFrame(attacks_data)
        logger.info(f"Loaded {len(df)} attack patterns from backup file")
        return df
    
    def preprocess_text(self, text: str) -> str:
        """Clean and preprocess text data."""
        if not isinstance(text, str):
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Tokenize
        tokens = word_tokenize(text)
        
        # Remove stopwords and lemmatize
        tokens = [
            self.lemmatizer.lemmatize(token) 
            for token in tokens 
            if token.isalpha() and token not in self.stop_words
        ]
        
        return ' '.join(tokens)
    
    def prepare_training_data(self, df: pd.DataFrame, target_column: str = 'category') -> Tuple:
        """Prepare data for ML training."""
        logger.info(f"Preparing training data with target: {target_column}")
        
        # Combine text fields for feature extraction
        df['combined_text'] = df['title'] + ' ' + df['scenario_description'] + ' ' + df['attack_steps']
        df['combined_text'] = df['combined_text'].apply(self.preprocess_text)
        
        # Remove rows with missing target
        df = df.dropna(subset=[target_column])
        
        # Extract features and labels
        X = df['combined_text']
        y = df[target_column]
        
        # Encode labels
        label_encoder = LabelEncoder()
        y_encoded = label_encoder.fit_transform(y)
        
        logger.info(f"Classes: {len(label_encoder.classes_)}")
        logger.info(f"Samples: {len(X)}")
        
        return X, y_encoded, label_encoder


class AttackClassifier:
    """Machine learning classifier for attack patterns."""
    
    def __init__(self, model_type: str = 'random_forest'):
        self.model_type = model_type
        self.model = None
        self.vectorizer = None
        self.label_encoder = None
        
    def create_model(self):
        """Create the ML model based on type."""
        models = {
            'random_forest': RandomForestClassifier(n_estimators=100, random_state=42),
            'logistic_regression': LogisticRegression(max_iter=1000, random_state=42),
            'svm': SVC(kernel='linear', random_state=42),
            'gradient_boosting': GradientBoostingClassifier(n_estimators=100, random_state=42)
        }
        
        if self.model_type not in models:
            raise ValueError(f"Unknown model type: {self.model_type}")
        
        self.model = models[self.model_type]
        logger.info(f"Created model: {self.model_type}")
        
    def train(self, X_train, y_train):
        """Train the classifier."""
        logger.info("Training classifier...")
        
        # Create TF-IDF features
        self.vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        X_train_tfidf = self.vectorizer.fit_transform(X_train)
        
        # Train model
        self.model.fit(X_train_tfidf, y_train)
        logger.info("Training completed")
        
    def evaluate(self, X_test, y_test):
        """Evaluate the classifier."""
        X_test_tfidf = self.vectorizer.transform(X_test)
        y_pred = self.model.predict(X_test_tfidf)
        
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, output_dict=True)
        
        logger.info(f"Accuracy: {accuracy:.4f}")
        logger.info(f"Classification Report:\n{classification_report(y_test, y_pred)}")
        
        return accuracy, report
    
    def predict(self, texts: List[str]) -> List:
        """Make predictions on new texts."""
        if not self.model or not self.vectorizer:
            raise ValueError("Model not trained")
        
        # Preprocess texts
        processed_texts = [self._preprocess_text(text) for text in texts]
        
        # Transform and predict
        X_tfidf = self.vectorizer.transform(processed_texts)
        predictions = self.model.predict(X_tfidf)
        
        # Decode labels
        if self.label_encoder:
            predictions = self.label_encoder.inverse_transform(predictions)
        
        return predictions
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess single text."""
        lemmatizer = WordNetLemmatizer()
        stop_words = set(stopwords.words('english'))
        
        text = str(text).lower()
        tokens = word_tokenize(text)
        tokens = [
            lemmatizer.lemmatize(token) 
            for token in tokens 
            if token.isalpha() and token not in stop_words
        ]
        
        return ' '.join(tokens)
    
    def save_model(self, path: str):
        """Save trained model and components."""
        model_data = {
            'model': self.model,
            'vectorizer': self.vectorizer,
            'label_encoder': self.label_encoder,
            'model_type': self.model_type
        }
        joblib.dump(model_data, path)
        logger.info(f"Model saved to {path}")
    
    def load_model(self, path: str):
        """Load trained model and components."""
        model_data = joblib.load(path)
        self.model = model_data['model']
        self.vectorizer = model_data['vectorizer']
        self.label_encoder = model_data['label_encoder']
        self.model_type = model_data['model_type']
        logger.info(f"Model loaded from {path}")


class EmbeddingGenerator:
    """Generate embeddings for semantic search and analysis."""
    
    def __init__(self, method: str = 'tfidf'):
        self.method = method
        self.embedder = None
        
    def fit_transform(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        logger.info(f"Generating {self.method} embeddings...")
        
        if self.method == 'tfidf':
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.embedder = TfidfVectorizer(max_features=1000, ngram_range=(1, 2))
            embeddings = self.embedder.fit_transform(texts).toarray()
            
        elif self.method == 'sentence_transformer':
            try:
                from sentence_transformers import SentenceTransformer
                self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
                embeddings = self.embedder.encode(texts, show_progress_bar=True)
            except ImportError:
                logger.warning("sentence_transformers not available, falling back to TF-IDF")
                return self.fit_transform(texts)
        
        logger.info(f"Generated embeddings shape: {embeddings.shape}")
        return embeddings
    
    def transform(self, texts: List[str]) -> np.ndarray:
        """Transform new texts to embeddings."""
        if self.method == 'tfidf':
            return self.embedder.transform(texts).toarray()
        elif self.method == 'sentence_transformer':
            return self.embedder.encode(texts, show_progress_bar=True)
        
    def save_embeddings(self, embeddings: np.ndarray, path: str):
        """Save embeddings to file."""
        np.save(path, embeddings)
        logger.info(f"Embeddings saved to {path}")
    
    def load_embeddings(self, path: str) -> np.ndarray:
        """Load embeddings from file."""
        embeddings = np.load(path)
        logger.info(f"Embeddings loaded from {path}, shape: {embeddings.shape}")
        return embeddings


class TrainingPipeline:
    """Complete training pipeline for attack pattern analysis."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.data_loader = AttackDataLoader(
            db_config=config.get('db_config'),
            backup_file=config.get('backup_file')
        )
        self.classifier = AttackClassifier(config.get('model_type', 'random_forest'))
        self.embedding_generator = EmbeddingGenerator(config.get('embedding_method', 'tfidf'))
        
    def run(self):
        """Execute the complete training pipeline."""
        logger.info("Starting AI training pipeline...")
        
        # Load data
        if self.config.get('use_backup', False):
            df = self.data_loader.load_from_backup()
        else:
            df = self.data_loader.load_from_database()
        
        # Prepare training data
        target_column = self.config.get('target_column', 'category')
        X, y, label_encoder = self.data_loader.prepare_training_data(df, target_column)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train classifier
        self.classifier.label_encoder = label_encoder
        self.classifier.create_model()
        self.classifier.train(X_train, y_train)
        
        # Evaluate classifier
        accuracy, report = self.classifier.evaluate(X_test, y_test)
        
        # Generate embeddings
        embeddings = self.embedding_generator.fit_transform(X_train.tolist())
        
        # Save models
        output_dir = self.config.get('output_dir', './models')
        os.makedirs(output_dir, exist_ok=True)
        
        model_path = os.path.join(output_dir, f"{target_column}_classifier.joblib")
        self.classifier.save_model(model_path)
        
        embedding_path = os.path.join(output_dir, f"{target_column}_embeddings.npy")
        self.embedding_generator.save_embeddings(embeddings, embedding_path)
        
        # Save training metadata
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'target_column': target_column,
            'model_type': self.classifier.model_type,
            'accuracy': accuracy,
            'num_classes': len(label_encoder.classes_),
            'num_samples': len(X),
            'embedding_method': self.embedding_generator.method,
            'classes': label_encoder.classes_.tolist()
        }
        
        metadata_path = os.path.join(output_dir, f"{target_column}_metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Training pipeline completed. Results saved to {output_dir}")
        logger.info(f"Final Accuracy: {accuracy:.4f}")
        
        return {
            'accuracy': accuracy,
            'report': report,
            'metadata': metadata
        }


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Train AI models on attack patterns')
    parser.add_argument('--backup-file', type=str, help='Path to SQL backup file')
    parser.add_argument('--target-column', type=str, default='category', 
                        help='Target column for classification (category, attack_type, etc.)')
    parser.add_argument('--model-type', type=str, default='random_forest',
                        choices=['random_forest', 'logistic_regression', 'svm', 'gradient_boosting'],
                        help='Type of ML model to train')
    parser.add_argument('--embedding-method', type=str, default='tfidf',
                        choices=['tfidf', 'sentence_transformer'],
                        help='Method for generating embeddings')
    parser.add_argument('--output-dir', type=str, default='./models',
                        help='Directory to save trained models')
    parser.add_argument('--use-backup', action='store_true',
                        help='Use backup file instead of database connection')
    
    args = parser.parse_args()
    
    # Configuration
    config = {
        'backup_file': args.backup_file,
        'target_column': args.target_column,
        'model_type': args.model_type,
        'embedding_method': args.embedding_method,
        'output_dir': args.output_dir,
        'use_backup': args.use_backup,
        'db_config': {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', 5432)),
            'database': os.getenv('POSTGRES_DB', 'attack_db'),
            'user': os.getenv('POSTGRES_USER', 'opsec'),
            'password': os.getenv('POSTGRES_PASSWORD', 'opsec')
        }
    }
    
    # Run training pipeline
    try:
        pipeline = TrainingPipeline(config)
        results = pipeline.run()
        
        print("\n" + "="*50)
        print("TRAINING RESULTS")
        print("="*50)
        print(f"Model Type: {config['model_type']}")
        print(f"Target Column: {config['target_column']}")
        print(f"Accuracy: {results['accuracy']:.4f}")
        print(f"Number of Classes: {results['metadata']['num_classes']}")
        print(f"Training Samples: {results['metadata']['num_samples']}")
        print(f"Models saved to: {config['output_dir']}")
        print("="*50)
        
    except Exception as e:
        logger.error(f"Training pipeline failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()