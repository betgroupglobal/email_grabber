"""
ML Model Service for Attack Pattern Classification
Integrates trained ML models into the knowledge engine API.
"""

import os
import logging
import joblib
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path

import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MLModelService:
    """Service for loading and using trained ML models."""
    
    def __init__(self, models_dir: str = "./ml_models"):
        """Initialize the ML model service."""
        self.models_dir = Path(models_dir)
        self.models = {}
        
        # Initialize NLP components only if NLTK data is available
        try:
            self.lemmatizer = WordNetLemmatizer()
            self.stop_words = set(stopwords.words('english'))
            self.nltk_available = True
        except Exception as e:
            logger.warning(f"NLTK data not available, using basic preprocessing: {e}")
            self.lemmatizer = None
            self.stop_words = set()
            self.nltk_available = False
        
        # Ensure NLTK data is available
        self._ensure_nltk_data()
        
        # Load available models
        self._load_available_models()
        
    def _ensure_nltk_data(self):
        """Download required NLTK data."""
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            try:
                logger.info("Downloading NLTK punkt_tab data...")
                nltk.download('punkt_tab', quiet=True)
            except Exception as e:
                logger.warning(f"Failed to download punkt_tab: {e}")
        
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            try:
                logger.info("Downloading NLTK stopwords data...")
                nltk.download('stopwords', quiet=True)
            except Exception as e:
                logger.warning(f"Failed to download stopwords: {e}")
            
        try:
            nltk.data.find('corpora/wordnet')
        except LookupError:
            try:
                logger.info("Downloading NLTK wordnet data...")
                nltk.download('wordnet', quiet=True)
            except Exception as e:
                logger.warning(f"Failed to download wordnet: {e}")
    
    def _load_available_models(self):
        """Load all available trained models from the models directory."""
        if not self.models_dir.exists():
            logger.warning(f"Models directory {self.models_dir} does not exist")
            return
        
        # Load all .joblib files
        for model_file in self.models_dir.glob("*_classifier.joblib"):
            target_name = model_file.stem.replace("_classifier", "")
            try:
                self.load_model(target_name, str(model_file))
                logger.info(f"Loaded model: {target_name}")
            except Exception as e:
                logger.error(f"Failed to load model {target_name}: {e}")
    
    def load_model(self, target_name: str, model_path: str):
        """Load a specific trained model."""
        model_data = joblib.load(model_path)
        
        self.models[target_name] = {
            'model': model_data['model'],
            'vectorizer': model_data['vectorizer'],
            'label_encoder': model_data['label_encoder'],
            'model_type': model_data['model_type'],
            'metadata': self._load_metadata(target_name)
        }
        
        logger.info(f"Model '{target_name}' loaded successfully")
    
    def _load_metadata(self, target_name: str) -> Optional[Dict]:
        """Load metadata for a specific model."""
        metadata_file = self.models_dir / f"{target_name}_metadata.json"
        if metadata_file.exists():
            import json
            with open(metadata_file, 'r') as f:
                return json.load(f)
        return None
    
    def preprocess_text(self, text: str) -> str:
        """Preprocess text for ML prediction."""
        if not isinstance(text, str):
            return ""
        
        # Use basic preprocessing if NLTK is not available
        if not self.nltk_available:
            text = str(text).lower()
            return ' '.join([t for t in text.split() if t.isalpha()])
        
        try:
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
        except Exception as e:
            logger.warning(f"Text preprocessing failed: {e}, using basic preprocessing")
            # Fallback to basic preprocessing
            text = str(text).lower()
            return ' '.join([t for t in text.split() if t.isalpha()])
    
    def predict(
        self, 
        target_name: str, 
        text: str, 
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Make predictions using a trained model.
        
        Args:
            target_name: Name of the target/model (e.g., 'category', 'attack_type')
            text: Input text to classify
            top_k: Number of top predictions to return
            
        Returns:
            List of predictions with labels and confidence scores
        """
        if target_name not in self.models:
            raise ValueError(f"Model '{target_name}' not found. Available models: {list(self.models.keys())}")
        
        model_data = self.models[target_name]
        model = model_data['model']
        vectorizer = model_data['vectorizer']
        label_encoder = model_data['label_encoder']
        
        # Preprocess text
        processed_text = self.preprocess_text(text)
        
        # Transform text
        text_tfidf = vectorizer.transform([processed_text])
        
        # Get predictions
        if hasattr(model, 'predict_proba'):
            probabilities = model.predict_proba(text_tfidf)[0]
            top_indices = probabilities.argsort()[-top_k:][::-1]
            
            predictions = []
            for idx in top_indices:
                label = label_encoder.inverse_transform([idx])[0]
                confidence = float(probabilities[idx])
                predictions.append({
                    'label': label,
                    'confidence': confidence,
                    'rank': len(predictions) + 1
                })
            
            return predictions
        else:
            # Fallback to single prediction
            prediction = model.predict(text_tfidf)[0]
            label = label_encoder.inverse_transform([prediction])[0]
            return [{
                'label': label,
                'confidence': 1.0,
                'rank': 1
            }]
    
    def batch_predict(
        self, 
        target_name: str, 
        texts: List[str], 
        top_k: int = 3
    ) -> List[List[Dict[str, Any]]]:
        """Make batch predictions on multiple texts."""
        return [self.predict(target_name, text, top_k) for text in texts]
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get information about available models."""
        models_info = []
        for target_name, model_data in self.models.items():
            metadata = model_data['metadata']
            models_info.append({
                'target': target_name,
                'model_type': model_data['model_type'],
                'num_classes': len(model_data['label_encoder'].classes_),
                'accuracy': metadata.get('accuracy') if metadata else None,
                'num_samples': metadata.get('num_samples') if metadata else None,
                'classes': model_data['label_encoder'].classes_.tolist()[:10],  # First 10 classes
                'total_classes': len(model_data['label_encoder'].classes_)
            })
        return models_info
    
    def get_model_info(self, target_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific model."""
        if target_name not in self.models:
            return None
        
        model_data = self.models[target_name]
        metadata = model_data['metadata']
        
        return {
            'target': target_name,
            'model_type': model_data['model_type'],
            'num_classes': len(model_data['label_encoder'].classes_),
            'classes': model_data['label_encoder'].classes_.tolist(),
            'accuracy': metadata.get('accuracy') if metadata else None,
            'num_samples': metadata.get('num_samples') if metadata else None,
            'embedding_method': metadata.get('embedding_method') if metadata else None,
            'timestamp': metadata.get('timestamp') if metadata else None
        }


# Global ML service instance
ml_service: Optional[MLModelService] = None


def get_ml_service() -> MLModelService:
    """Get or create the global ML service instance."""
    global ml_service
    if ml_service is None:
        # Try different possible model directories
        possible_dirs = [
            "./ml_models",
            "./models",
            "/Users/adminuser/attack-dataset/backend/knowledge_engine/ml_models",
            "/Users/adminuser/attack-dataset/backend/knowledge_engine/models"
        ]
        
        models_dir = None
        for dir_path in possible_dirs:
            if Path(dir_path).exists():
                models_dir = dir_path
                break
        
        if models_dir is None:
            logger.warning("No models directory found, ML service will be disabled")
            ml_service = MLModelService(models_dir="./nonexistent")
        else:
            logger.info(f"Initializing ML service with models from: {models_dir}")
            ml_service = MLModelService(models_dir=models_dir)
    
    return ml_service