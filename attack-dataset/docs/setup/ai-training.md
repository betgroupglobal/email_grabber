# AI Training System for Attack Patterns

## Overview

This AI training system enables machine learning model training on the comprehensive attack patterns database. It supports various classification tasks, embedding generation, and model deployment for security analysis.

## Features

- **Multiple ML Models**: Random Forest, Logistic Regression, SVM, Gradient Boosting
- **Flexible Data Sources**: Direct database connection or SQL backup files
- **Multiple Classification Targets**: Category, attack type, MITRE technique, etc.
- **Embedding Generation**: TF-IDF and Sentence Transformers for semantic search
- **Comprehensive Evaluation**: Accuracy metrics, classification reports, confusion matrices
- **Model Persistence**: Save/load trained models for deployment
- **Inference API**: Easy-to-use prediction interface

## Installation

### Install Dependencies

```bash
cd backend/knowledge_engine
pip install -r requirements_ml.txt
```

### Requirements

- Python 3.8+
- scikit-learn >= 1.3.0
- nltk >= 3.8.0
- pandas >= 2.0.0
- numpy >= 1.24.0
- psycopg2-binary >= 2.9.0
- joblib >= 1.3.0

Optional (for advanced embeddings):
- sentence-transformers >= 2.2.0

## Usage

### Training Models

#### Train from Database

```bash
python train_ai_model.py \
  --target-column category \
  --model-type random_forest \
  --embedding-method tfidf \
  --output-dir ./models
```

#### Train from Backup File

```bash
python train_ai_model.py \
  --backup-file ../../bingo.lc \
  --target-column category \
  --model-type logistic_regression \
  --use-backup \
  --output-dir ./ml_models
```

### Command Line Options

- `--backup-file`: Path to SQL backup file (optional)
- `--target-column`: Target column for classification (default: category)
  - Options: category, attack_type, mitre_technique, vulnerability, etc.
- `--model-type`: Type of ML model (default: random_forest)
  - Options: random_forest, logistic_regression, svm, gradient_boosting
- `--embedding-method`: Embedding generation method (default: tfidf)
  - Options: tfidf, sentence_transformer
- `--output-dir`: Directory to save trained models (default: ./models)
- `--use-backup`: Use backup file instead of database connection

### Making Predictions

#### Using the Inference Script

```bash
# Example predictions
python inference_example.py --model-path ./ml_models/category_classifier.joblib

# Single prediction
python inference_example.py \
  --model-path ./ml_models/category_classifier.joblib \
  --description "SQL injection attack on login form" \
  --top-k 3
```

#### Programmatic Usage

```python
from train_ai_model import AttackPatternClassifier

# Load trained model
classifier = AttackPatternClassifier('./ml_models/category_classifier.joblib')

# Make predictions
predictions = classifier.predict_category(
    "Phishing email with malicious PDF attachment",
    top_k=3
)

for pred in predictions:
    print(f"{pred['category']}: {pred['confidence']:.2%}")
```

## Training Results

### Test Run Results

**Configuration:**
- Dataset: 13,974 attack patterns
- Target: Category classification
- Model: Logistic Regression
- Embeddings: TF-IDF (1000 features)

**Performance:**
- Accuracy: 81.22%
- Classes: 63 unique categories
- Training samples: 11,179
- Test samples: 2,795

### Top Performing Categories

The model shows strong performance on major categories:
- Insider Threat: 94.15% confidence
- Malware & Threat: 64.62% confidence
- Email & Messaging Protocol Exploits: 23.81% confidence

## Model Architecture

### Data Processing Pipeline

1. **Data Loading**: Load from PostgreSQL or SQL backup file
2. **Text Preprocessing**: 
   - Tokenization
   - Stopword removal
   - Lemmatization
   - Text normalization
3. **Feature Extraction**: TF-IDF vectorization (n-grams: 1-2)
4. **Label Encoding**: Encode target classes
5. **Train/Test Split**: 80/20 stratified split
6. **Model Training**: Train selected ML algorithm
7. **Evaluation**: Calculate accuracy and classification report
8. **Embedding Generation**: Create semantic embeddings
9. **Model Persistence**: Save model and components

### Class Structure

- `AttackDataLoader`: Handles data loading and preprocessing
- `AttackClassifier`: ML model training and evaluation
- `EmbeddingGenerator`: Creates semantic embeddings
- `TrainingPipeline`: Orchestrates complete training workflow

## Output Files

Training generates the following files in the output directory:

- `{target}_classifier.joblib`: Trained model with vectorizer and encoder
- `{target}_embeddings.npy`: Generated embeddings (numpy array)
- `{target}_metadata.json`: Training metadata and configuration

### Metadata Format

```json
{
  "timestamp": "2026-05-18T06:59:10.482812",
  "target_column": "category",
  "model_type": "logistic_regression",
  "accuracy": 0.8122,
  "num_classes": 63,
  "num_samples": 13974,
  "embedding_method": "tfidf",
  "classes": ["AI Agents & LLM Exploits", "AI Data Leakage & Privacy Risks", ...]
}
```

## Advanced Usage

### Custom Model Training

```python
from train_ai_model import TrainingPipeline

config = {
    'backup_file': '../../bingo.lc',
    'target_column': 'attack_type',
    'model_type': 'gradient_boosting',
    'embedding_method': 'sentence_transformer',
    'output_dir': './custom_models',
    'use_backup': True
}

pipeline = TrainingPipeline(config)
results = pipeline.run()
```

### Cross-Validation

```python
from sklearn.model_selection import cross_val_score

# Load your data
X, y, label_encoder = data_loader.prepare_training_data(df, 'category')

# Create vectorizer and model
vectorizer = TfidfVectorizer(max_features=5000)
X_tfidf = vectorizer.fit_transform(X)

model = RandomForestClassifier(n_estimators=100)
cv_scores = cross_val_score(model, X_tfidf, y, cv=5)

print(f"CV Accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
```

### Hyperparameter Tuning

```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [50, 100, 200],
    'max_depth': [10, 20, None],
    'min_samples_split': [2, 5, 10]
}

grid_search = GridSearchCV(
    RandomForestClassifier(),
    param_grid,
    cv=5,
    scoring='accuracy'
)

grid_search.fit(X_train_tfidf, y_train)
print(f"Best parameters: {grid_search.best_params_}")
print(f"Best accuracy: {grid_search.best_score_:.4f}")
```

## Database Schema

The training system works with the following database schema:

### Attacks Table
- `id`: Primary key
- `title`: Attack name
- `category`: Security category (63 unique values)
- `attack_type`: Specific attack technique (8,818 unique values)
- `scenario_description`: Detailed attack scenario
- `tools_used`: Required tools
- `attack_steps`: Step-by-step execution guide
- `target_type`: Target systems
- `vulnerability`: Specific vulnerability
- `mitre_technique`: MITRE ATT&CK mapping
- `impact`: Attack impact
- `detection_method`: Detection mechanisms
- `solution`: Remediation steps
- `tags`: Searchable tags
- `source`: Reference sources

## Performance Optimization

### For Large Datasets

- Use `--embedding-method tfidf` for faster training
- Reduce `max_features` in vectorizer (default: 5000)
- Use simpler models like Logistic Regression
- Enable sparse matrix operations

### For Better Accuracy

- Use `--model-type gradient_boosting` or `--model-type random_forest`
- Increase `max_features` in vectorizer
- Use `--embedding-method sentence_transformer` for semantic embeddings
- Enable hyperparameter tuning

## Troubleshooting

### NLTK Issues

```bash
# Download required NLTK data
python -c "import nltk; nltk.download('punkt_tab'); nltk.download('stopwords'); nltk.download('wordnet')"
```

### Memory Issues

```bash
# Reduce memory usage by limiting features
# Edit train_ai_model.py and change max_features
self.vectorizer = TfidfVectorizer(max_features=1000)  # Reduce from 5000
```

### Database Connection Issues

```bash
# Check database connectivity
docker-compose exec postgres psql -U opsec -d attack_db -c "SELECT COUNT(*) FROM attacks;"
```

## Future Enhancements

- Deep learning models (BERT, RoBERTa fine-tuning)
- Multi-label classification support
- Real-time prediction API
- Model versioning and A/B testing
- Automated hyperparameter optimization
- Integration with the main application API

## Contributing

When adding new features:
1. Update the requirements_ml.txt file
2. Add comprehensive docstrings
3. Include unit tests
4. Update this README with usage examples

## License

This training system is part of the OpsecAI project and follows the same license terms.

## Support

For issues or questions:
1. Check the logs for detailed error messages
2. Verify all dependencies are installed
3. Ensure database connectivity
4. Review the configuration parameters

---

**Training System Version:** 1.0.0  
**Last Updated:** 2026-05-18  
**Database Version:** PostgreSQL 16.13