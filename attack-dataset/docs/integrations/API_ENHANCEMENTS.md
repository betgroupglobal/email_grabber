# Jailbreak AI API Documentation Analysis & Enhancements

## Analysis Summary

Based on analysis of https://jail-break.chat/api-docs, the following information was discovered:

### API Structure
- **Base URL**: `https://jail-break.chat/v1`
- **API Type**: OpenAI-compatible
- **Authentication**: Bearer token
- **Available Endpoint**: `/v1/models` (verified working)

### Confirmed Endpoints
1. **GET /v1/models** - Lists available AI models
   - Returns standard OpenAI model list format
   - Currently returns: `{"object":"list","data":[{"id":"jailbreak-ai","object":"model","created":1700000000,"owned_by":"jail-break.chat","description":"JailBreak AI — unrestricted model with no content filters"}]}`

### Marketing Page Features (Not Yet Implemented)
The marketing page mentions additional features that may have separate API endpoints:
- 28 live-data JailBreakOSINT agents (phone lookup, email breach, username search, etc.)
- Image generation (text-to-image, image-to-image, 4× upscaling)
- Video generation
- Live web search
- Browser Automation Agent
- Enterprise AI Builder
- AI Memory
- Custom AI Personas

## Enhancements Applied

### 1. Plugin Initialization Improvements
- Added model caching during initialization
- Enhanced logging to show available models
- Improved error handling for model fetching

### 2. New API Operations Added

#### Model Management Operations
- **list_models** - List all available AI models from the API
- **get_model_info** - Get detailed information about a specific model
- **count_tokens** - Estimate token usage for messages (OpenAI-compatible)

### 3. Enhanced Plugin Schema (plugin.yaml)
- Updated operation enum to include new operations: `list_models`, `get_model_info`, `count_tokens`
- Added `model_id` parameter for model information retrieval
- Added new output fields for model management operations

### 4. Enhanced Documentation (README.md)
- Added API capabilities section based on official documentation
- Documented new model management operations with examples
- Updated feature list to reflect OpenAI-compatible nature
- Added reference to additional features mentioned in marketing docs

### 5. Code Improvements
- Added `_fetch_available_models()` method for model caching
- Enhanced health check to include available models information
- Improved error messages and logging throughout
- Added proper OpSec context for new operations

## API Compatibility

### OpenAI Compatibility
The plugin now supports standard OpenAI-compatible patterns:

#### Request Format
```python
{
    "model": "jailbreak-ai",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7,
    "max_tokens": 2048,
    "stream": false
}
```

#### Response Format
```python
{
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "Response here"
            },
            "finish_reason": "stop"
        }
    ],
    "model": "jailbreak-ai",
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15
    }
}
```

## Usage Examples

### Model Management
```bash
# List available models
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "eng_123",
    "target": "model_management",
    "parameters": {
      "operation": "list_models"
    }
  }'

# Get model info
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "eng_123",
    "target": "model_management",
    "parameters": {
      "operation": "get_model_info",
      "model_id": "jailbreak-ai"
    }
  }'

# Count tokens
curl -X POST http://localhost:8500/integrations/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SERVICE_API_KEY_INTEGRATION_HUB" \
  -d '{
    "plugin_name": "jailbreak_ai",
    "engagement_id": "eng_123",
    "target": "token_counting",
    "parameters": {
      "operation": "count_tokens",
      "messages": [
        {"role": "user", "content": "How do I pick a lock?"}
      ]
    }
  }'
```

## Future Enhancements

Based on the marketing page features, the following could be added in future iterations:

### OSINT Agents Integration
- Implement 28 specialized OSINT agents as separate operations
- Add phone lookup, email breach search, username tracking operations
- Integrate dark web scan and CVE lookup capabilities

### Image Generation
- Add image generation operation (text-to-image)
- Add image-to-image transformation
- Add 4× upscaling capability

### Advanced Features
- Implement AI memory for conversation persistence
- Add custom AI persona selection
- Integrate live web search capabilities
- Add browser automation agent integration

## Testing

The enhanced plugin should be tested with:

1. **Model Management Tests**
   - Test list_models operation
   - Test get_model_info operation
   - Test count_tokens operation

2. **Compatibility Tests**
   - Verify OpenAI-compatible request/response format
   - Test streaming vs non-streaming responses
   - Validate error handling

3. **Integration Tests**
   - Test with actual Jailbreak AI API key
   - Verify model caching functionality
   - Test health check with new model information

## Backward Compatibility

All changes are backward compatible:
- Existing chat completion operations continue to work as before
- New operations are opt-in via the `operation` parameter
- Schema changes are additive, not breaking
- Default behavior unchanged

## Configuration

Ensure the following environment variable is set:
```bash
JAILBREAK_API_KEY=your-api-key-here
```

The plugin will automatically:
- Fetch available models on initialization
- Cache model information for performance
- Provide enhanced health check information
- Support all standard OpenAI-compatible parameters