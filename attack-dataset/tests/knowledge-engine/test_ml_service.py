"""
Tests for MLModelService - ML model loading and predictions.
"""
import pytest
from ml_service import MLModelService, get_ml_service


# ── ML Service Initialization ─────────────────────────────────────────────────

@pytest.mark.integration
def test_ml_service_initialization(ml_service):
    """Test that ML service initializes correctly."""
    assert ml_service is not None
    assert hasattr(ml_service, 'models')
    assert hasattr(ml_service, 'models_dir')


@pytest.mark.integration
def test_ml_service_get_instance():
    """Test getting ML service singleton instance."""
    service = get_ml_service()
    assert service is not None


# ── Model Loading Tests ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_load_available_models(ml_service):
    """Test that available models are loaded."""
    # Check if any models are loaded
    models = ml_service.get_available_models()
    assert isinstance(models, list)
    # May be empty if no models are available
    if models:
        assert all('target' in model for model in models)
        assert all('model_type' in model for model in models)


@pytest.mark.integration
def test_get_model_info_existing(ml_service):
    """Test getting info for an existing model."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available")
    
    target_name = models[0]['target']
    model_info = ml_service.get_model_info(target_name)
    
    assert model_info is not None
    assert model_info['target'] == target_name
    assert 'model_type' in model_info
    assert 'num_classes' in model_info


@pytest.mark.integration
def test_get_model_info_nonexistent(ml_service):
    """Test getting info for a non-existent model."""
    model_info = ml_service.get_model_info("nonexistent_model")
    
    assert model_info is None


# ── Text Preprocessing Tests ─────────────────────────────────────────────────

@pytest.mark.integration
def test_preprocess_text_basic(ml_service):
    """Test basic text preprocessing."""
    text = "SQL Injection Attack on Web Application"
    processed = ml_service.preprocess_text(text)
    
    assert isinstance(processed, str)
    assert len(processed) > 0
    assert len(processed) <= len(text)  # Should be shorter or equal


@pytest.mark.integration
def test_preprocess_text_lowercase(ml_service):
    """Test that preprocessing converts to lowercase."""
    text = "SQL INJECTION ATTACK"
    processed = ml_service.preprocess_text(text)
    
    assert processed.islower() or not any(c.isupper() for c in processed)


@pytest.mark.integration
def test_preprocess_text_special_characters(ml_service):
    """Test preprocessing with special characters."""
    text = "SQL injection! @#$%^&*()"
    processed = ml_service.preprocess_text(text)
    
    assert isinstance(processed, str)
    # Special characters should be removed or handled
    assert processed is not None


@pytest.mark.integration
def test_preprocess_text_empty(ml_service):
    """Test preprocessing with empty string."""
    processed = ml_service.preprocess_text("")
    
    assert processed == ""


@pytest.mark.integration
def test_preprocess_text_none(ml_service):
    """Test preprocessing with None input."""
    processed = ml_service.preprocess_text(None)
    
    assert processed == ""


@pytest.mark.integration
def test_preprocess_text_numbers(ml_service):
    """Test preprocessing with numbers."""
    text = "SQL injection 123 attack 456"
    processed = ml_service.preprocess_text(text)
    
    assert isinstance(processed, str)
    # Numbers should be removed (only alphabetic characters kept)


# ── Prediction Tests ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_predict_single(ml_service):
    """Test single prediction."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available for prediction")
    
    target_name = models[0]['target']
    text = "SQL injection attack on web application"
    
    predictions = ml_service.predict(target_name, text, top_k=3)
    
    assert isinstance(predictions, list)
    assert len(predictions) <= 3
    
    if predictions:
        assert 'label' in predictions[0]
        assert 'confidence' in predictions[0]
        assert 'rank' in predictions[0]
        assert predictions[0]['rank'] == 1
        assert 0 <= predictions[0]['confidence'] <= 1


@pytest.mark.integration
def test_predict_nonexistent_model(ml_service):
    """Test prediction with non-existent model."""
    with pytest.raises(ValueError):
        ml_service.predict("nonexistent_model", "test text")


@pytest.mark.integration
def test_predict_empty_text(ml_service):
    """Test prediction with empty text."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available for prediction")
    
    target_name = models[0]['target']
    predictions = ml_service.predict(target_name, "", top_k=3)
    
    assert isinstance(predictions, list)


@pytest.mark.integration
def test_predict_custom_top_k(ml_service):
    """Test prediction with custom top_k value."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available for prediction")
    
    target_name = models[0]['target']
    text = "SQL injection attack"
    
    predictions_5 = ml_service.predict(target_name, text, top_k=5)
    predictions_1 = ml_service.predict(target_name, text, top_k=1)
    
    assert len(predictions_5) <= 5
    assert len(predictions_1) <= 1


# ── Batch Prediction Tests ───────────────────────────────────────────────────

@pytest.mark.integration
def test_batch_predict(ml_service):
    """Test batch prediction."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available for prediction")
    
    target_name = models[0]['target']
    texts = [
        "SQL injection attack",
        "Port scanning",
        "Brute force attack",
        "XSS attack",
        "Privilege escalation"
    ]
    
    predictions = ml_service.batch_predict(target_name, texts, top_k=3)
    
    assert isinstance(predictions, list)
    assert len(predictions) == len(texts)
    
    for pred_list in predictions:
        assert isinstance(pred_list, list)
        assert len(pred_list) <= 3


@pytest.mark.integration
def test_batch_predict_empty_list(ml_service):
    """Test batch prediction with empty list."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available for prediction")
    
    target_name = models[0]['target']
    predictions = ml_service.batch_predict(target_name, [], top_k=3)
    
    assert isinstance(predictions, list)
    assert len(predictions) == 0


@pytest.mark.integration
def test_batch_predict_single_item(ml_service):
    """Test batch prediction with single item."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available for prediction")
    
    target_name = models[0]['target']
    texts = ["SQL injection attack"]
    
    predictions = ml_service.batch_predict(target_name, texts, top_k=3)
    
    assert isinstance(predictions, list)
    assert len(predictions) == 1


# ── Model Information Tests ─────────────────────────────────────────────────

@pytest.mark.integration
def test_get_available_models_structure(ml_service):
    """Test structure of available models response."""
    models = ml_service.get_available_models()
    
    assert isinstance(models, list)
    
    for model in models:
        assert 'target' in model
        assert 'model_type' in model
        assert 'num_classes' in model
        assert isinstance(model['num_classes'], int)
        assert model['num_classes'] > 0


@pytest.mark.integration
def test_get_model_info_structure(ml_service):
    """Test structure of model info response."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available")
    
    target_name = models[0]['target']
    info = ml_service.get_model_info(target_name)
    
    assert info is not None
    assert 'target' in info
    assert 'model_type' in info
    assert 'num_classes' in info
    assert 'classes' in info
    assert isinstance(info['classes'], list)


@pytest.mark.integration
def test_get_model_info_classes(ml_service):
    """Test that model info contains valid classes."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available")
    
    target_name = models[0]['target']
    info = ml_service.get_model_info(target_name)
    
    assert info is not None
    assert len(info['classes']) > 0
    assert all(isinstance(cls, str) for cls in info['classes'])


# ── NLTK Data Handling Tests ─────────────────────────────────────────────────

@pytest.mark.integration
def test_nltk_data_availability(ml_service):
    """Test that NLTK data is handled correctly."""
    # This is implicitly tested by the preprocessing tests
    # If NLTK data is not available, the service should fall back to basic preprocessing
    text = "SQL injection attack"
    processed = ml_service.preprocess_text(text)
    
    assert isinstance(processed, str)
    assert len(processed) > 0


# ── Edge Cases and Error Handling ─────────────────────────────────────────────

@pytest.mark.integration
def test_predict_with_unicode(ml_service):
    """Test prediction with unicode characters."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available for prediction")
    
    target_name = models[0]['target']
    text = "SQL injection attack ñ 中文"
    
    predictions = ml_service.predict(target_name, text, top_k=3)
    
    assert isinstance(predictions, list)


@pytest.mark.integration
def test_predict_with_very_long_text(ml_service):
    """Test prediction with very long text."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available for prediction")
    
    target_name = models[0]['target']
    text = "SQL injection " * 1000  # Very long text
    
    predictions = ml_service.predict(target_name, text, top_k=3)
    
    assert isinstance(predictions, list)


@pytest.mark.integration
def test_batch_predict_mixed_texts(ml_service):
    """Test batch prediction with mixed text types."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available for prediction")
    
    target_name = models[0]['target']
    texts = [
        "SQL injection attack",
        "",
        "Port scanning",
        "XSS",
        "A" * 100,  # Very long string
        "Brute force"
    ]
    
    predictions = ml_service.batch_predict(target_name, texts, top_k=3)
    
    assert isinstance(predictions, list)
    assert len(predictions) == len(texts)


# ── Confidence Score Tests ───────────────────────────────────────────────────

@pytest.mark.integration
def test_prediction_confidence_scores(ml_service):
    """Test that prediction confidence scores are valid."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available for prediction")
    
    target_name = models[0]['target']
    text = "SQL injection attack"
    
    predictions = ml_service.predict(target_name, text, top_k=5)
    
    if predictions:
        # Check that confidence scores are valid
        for pred in predictions:
            assert 'confidence' in pred
            assert isinstance(pred['confidence'], (int, float))
            assert 0 <= pred['confidence'] <= 1
        
        # Check that scores are in descending order
        if len(predictions) > 1:
            for i in range(len(predictions) - 1):
                assert predictions[i]['confidence'] >= predictions[i + 1]['confidence']


@pytest.mark.integration
def test_prediction_ranking(ml_service):
    """Test that predictions are properly ranked."""
    models = ml_service.get_available_models()
    
    if not models:
        pytest.skip("No models available for prediction")
    
    target_name = models[0]['target']
    text = "SQL injection attack"
    
    predictions = ml_service.predict(target_name, text, top_k=3)
    
    if predictions:
        for i, pred in enumerate(predictions):
            assert pred['rank'] == i + 1