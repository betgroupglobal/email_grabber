#!/usr/bin/env python3
"""
Inference Example Script for Attack Pattern Classification
Demonstrates how to use the trained model for predictions.
"""

import sys
import joblib
import argparse
import json


class AttackPatternClassifier:
    """Load and use trained attack pattern classifier."""
    
    def __init__(self, model_path: str):
        """Load trained model and components."""
        print(f"Loading model from {model_path}...")
        model_data = joblib.load(model_path)
        
        self.model = model_data['model']
        self.vectorizer = model_data['vectorizer']
        self.label_encoder = model_data['label_encoder']
        self.model_type = model_data['model_type']
        
        print(f"Model loaded successfully!")
        print(f"Model type: {self.model_type}")
        print(f"Number of classes: {len(self.label_encoder.classes_)}")
        
    def preprocess_text(self, text: str) -> str:
        """Preprocess input text."""
        import nltk
        from nltk.tokenize import word_tokenize
        from nltk.corpus import stopwords
        from nltk.stem import WordNetLemmatizer
        
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
    
    def predict_category(self, attack_description: str, top_k: int = 3) -> list:
        """Predict attack category from description."""
        # Preprocess
        processed_text = self.preprocess_text(attack_description)
        
        # Transform
        text_tfidf = self.vectorizer.transform([processed_text])
        
        # Get probabilities
        if hasattr(self.model, 'predict_proba'):
            probabilities = self.model.predict_proba(text_tfidf)[0]
            top_indices = probabilities.argsort()[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                category = self.label_encoder.inverse_transform([idx])[0]
                confidence = probabilities[idx]
                results.append({
                    'category': category,
                    'confidence': float(confidence)
                })
            
            return results
        else:
            # Fallback to single prediction
            prediction = self.model.predict(text_tfidf)[0]
            category = self.label_encoder.inverse_transform([prediction])[0]
            return [{'category': category, 'confidence': 1.0}]
    
    def batch_predict(self, descriptions: list) -> list:
        """Predict categories for multiple descriptions."""
        results = []
        for desc in descriptions:
            result = self.predict_category(desc)
            results.append({
                'description': desc,
                'predictions': result
            })
        return results


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Classify attack patterns using trained model')
    parser.add_argument('--model-path', type=str,
                        default='./ml_models/category_classifier.joblib',
                        help='Path to trained model file')
    parser.add_argument('--description', type=str, 
                        help='Attack description to classify')
    parser.add_argument('--top-k', type=int, default=3,
                        help='Number of top predictions to return')
    
    args = parser.parse_args()
    
    # Load model
    try:
        classifier = AttackPatternClassifier(args.model_path)
    except Exception as e:
        print(f"Error loading model: {e}")
        sys.exit(1)
    
    # Example predictions if no description provided
    if not args.description:
        print("\n" + "="*60)
        print("EXAMPLE PREDICTIONS")
        print("="*60)
        
        examples = [
            "An attacker uses SQL injection to bypass authentication and access the admin panel",
            "Malware that encrypts files and demands ransom payment",
            "Phishing email with malicious attachment to steal credentials",
            "Exploiting a buffer overflow in a web server to gain remote code execution",
            "Insider threat where employee steals sensitive customer data"
        ]
        
        for example in examples:
            print(f"\nInput: {example}")
            predictions = classifier.predict_category(example, args.top_k)
            print("Predictions:")
            for i, pred in enumerate(predictions, 1):
                print(f"  {i}. {pred['category']} (confidence: {pred['confidence']:.2%})")
    else:
        # Single prediction
        print(f"\nInput: {args.description}")
        predictions = classifier.predict_category(args.description, args.top_k)
        print("Predictions:")
        for i, pred in enumerate(predictions, 1):
            print(f"  {i}. {pred['category']} (confidence: {pred['confidence']:.2%})")


if __name__ == '__main__':
    main()