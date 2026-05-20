"""
ML Model Training Script for Attack Dataset
Usage: python train_models.py --model-dir ./models --test-size 0.2
"""
import argparse
import json
import logging
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import psycopg2
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml_trainer")
def load_data_from_postgres():
    """Load attack data from PostgreSQL."""
    import os
    dsn = os.getenv("POSTGRES_DSN", "postgresql://opsec:opsec@localhost:5432/attack_db")
    conn = psycopg2.connect(dsn)
    query = "SELECT * FROM attacks"
    df = pd.read_sql(query, conn)
    conn.close()
    return df
def create_feature_text(row):
    fields = [row.get('title', ''), row.get('scenario_description', ''), 
            row.get('attack_steps', ''), row.get('tools_used', '')]
    return ' '.join(str(f) for f in fields if pd.notna(f))
def train_classifier(X, y, model_type='logistic_regression'):
    from sklearn.model_selection import train_test_split
    y_clean = y.dropna()
    X_clean = X[y_clean.index]
    X_train, X_test, y_train, y_test = train_test_split(
        X_clean, y_clean, test_size=0.2, random_state=42, stratify=y_clean
    )
    if model_type == 'logistic_regression':
        model = LogisticRegression(max_iter=1000, random_state=42)
    else:
        model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    accuracy = accuracy_score(y_test, model.predict(X_test))
    return model, accuracy
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-dir', type=str, default='./models')
    args = parser.parse_args()
    
    print("Loading data from PostgreSQL...")
    df = load_data_from_postgres()
    print(f"Loaded {len(df)} records")
    
    print("Preparing features...")
    df['feature_text'] = df.apply(create_feature_text, axis=1)
    vectorizer = TfidfVectorizer(max_features=10000, ngram_range=(1, 2))
    X = vectorizer.fit_transform(df['feature_text'])
    
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    
    # Save vectorizer
    with open(model_dir / 'vectorizer.pkl', 'wb') as f:
        pickle.dump(vectorizer, f)
    
    # Train models
    models = [
        ('category', 'category', 'logistic_regression'),
        ('attack_type', 'attack_type', 'logistic_regression'),
        ('target_type', 'target_type', 'logistic_regression'),
        ('impact', 'impact', 'random_forest'),
    ]
    
    results = {}
    for name, col, mtype in models:
        if col in df.columns:
            model, acc = train_classifier(X, df[col], mtype)
            with open(model_dir / f'{name}_model.pkl', 'wb') as f:
                pickle.dump(model, f)
            results[name] = {'accuracy': acc, 'status': 'success'}
            print(f"✓ {name}: accuracy={acc:.3f}")
    
    with open(model_dir / 'training_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\\nModels saved to {model_dir}")
if __name__ == "__main__":
    main()
