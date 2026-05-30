# Comprehensive OpsecAI Setup Guide

This guide provides complete setup instructions for the OpsecAI platform, including the AI training system, dashboard, and integration between components.

## Table of Contents

1. [System Overview](#system-overview)
2. [Prerequisites](#prerequisites)
3. [AI Training System Setup](#ai-training-system-setup)
4. [Dashboard Setup](#dashboard-setup)
5. [Integration Configuration](#integration-configuration)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)

## System Overview

The OpsecAI platform consists of three main components:

1. **AI Training System** (`backend/knowledge_engine/`)
   - ML model training on attack patterns
   - Classification and embedding generation
   - Model persistence and inference API

2. **Dashboard** (`frontend/dashboard/`)
   - Next.js-based user interface
   - Real-time monitoring and visualization
   - Service management and analytics

3. **Backend Services** (`backend/`)
   - Integration Hub (port 8500)
   - Knowledge Engine (port 8000)
   - Orchestrator (port 3001)
   - OpSec Monitor (port 8002)

## Prerequisites

### Required Software

- **Docker & Docker Compose** - For containerized services
- **Node.js 18+** - For dashboard development
- **Python 3.8+** - For AI training system
- **PostgreSQL 16+** - Database (or use Docker)
- **Redis** - Caching and message queue (or use Docker)

### System Requirements

- **RAM**: 8GB minimum (16GB recommended for ML training)
- **Disk**: 20GB free space
- **CPU**: 4 cores minimum (8 cores recommended for training)

## AI Training System Setup

### 1. Install ML Dependencies

```bash
cd backend/knowledge_engine
pip install -r requirements_ml.txt
```

### 2. Download NLTK Data

```bash
python -c "import nltk; nltk.download('punkt_tab'); nltk.download('stopwords'); nltk.download('wordnet')"
```

### 3. Configure Database Connection

The training system can work with either a live database or SQL backup file.

#### Option A: Live Database Connection

Ensure PostgreSQL is running and the attack patterns database is populated:

```bash
# Using Docker Compose
docker-compose up -d postgres

# Verify database
docker-compose exec postgres psql -U opsec -d attack_db -c "SELECT COUNT(*) FROM attacks;"
```

#### Option B: SQL Backup File

If you have a SQL backup file (e.g., `bingo.lc`), place it in the knowledge engine directory:

```bash
cp /path/to/bingo.lc backend/knowledge_engine/
```

### 4. Train a Model

#### Basic Training (Database)

```bash
cd backend/knowledge_engine
python train_ai_model.py \
  --target-column category \
  --model-type random_forest \
  --embedding-method tfidf \
  --output-dir ./models
```

#### Training from Backup File

```bash
python train_ai_model.py \
  --backup-file ../../bingo.lc \
  --target-column category \
  --model-type logistic_regression \
  --use-backup \
  --output-dir ./ml_models
```

#### Advanced Training Options

```bash
# Train with gradient boosting and sentence transformers
python train_ai_model.py \
  --target-column attack_type \
  --model-type gradient_boosting \
  --embedding-method sentence_transformer \
  --output-dir ./advanced_models \
  --use-backup
```

### 5. Test Model Inference

```bash
# Load and test the trained model
python inference_example.py \
  --model-path ./models/category_classifier.joblib \
  --description "SQL injection attack on login form" \
  --top-k 3
```

### 6. Integrate with Application

The trained models can be integrated into the Knowledge Engine API:

```python
from knowledge_engine.train_ai_model import AttackPatternClassifier

# Load trained model
classifier = AttackPatternClassifier('./models/category_classifier.joblib')

# Make predictions in your API
predictions = classifier.predict_category(
    attack_description=user_input,
    top_k=3
)
```

## Dashboard Setup

### 1. Install Dependencies

```bash
cd frontend/dashboard
npm install
```

### 2. Environment Configuration

Create a `.env.local` file:

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:3001
NEXT_PUBLIC_WS_URL=ws://localhost:3001

# AI Model Configuration
NEXT_PUBLIC_AI_MODEL_URL=http://localhost:8000
NEXT_PUBLIC_ENABLE_AI_CLASSIFICATION=true

# Feature Flags
NEXT_PUBLIC_ENABLE_ANALYTICS=true
NEXT_PUBLIC_ENABLE_REALTIME=true
NEXT_PUBLIC_ENABLE_MITRE_VISUALIZATION=true

# Authentication
NEXT_PUBLIC_AUTH_ENABLED=true
```

### 3. Start Development Server

```bash
npm run dev
```

Access the dashboard at [http://localhost:3000](http://localhost:3000)

### 4. Build for Production

```bash
npm run build
npm start
```

## Integration Configuration

### 1. Backend Services Integration

Configure the integration between AI training, dashboard, and backend services:

#### Update Knowledge Engine API

Add AI model endpoints to `backend/knowledge_engine/api.py`:

```python
from fastapi import FastAPI
from train_ai_model import AttackPatternClassifier

app = FastAPI()

# Load trained model
classifier = AttackPatternClassifier('./models/category_classifier.joblib')

@app.post("/api/classify")
async def classify_attack(description: str):
    predictions = classifier.predict_category(description, top_k=3)
    return {"predictions": predictions}
```

#### Dashboard Integration

Create API client in `frontend/dashboard/lib/api.ts`:

```typescript
export async function classifyAttack(description: string) {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_AI_MODEL_URL}/api/classify`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description })
    }
  );
  return response.json();
}
```

### 2. WebSocket Integration

Configure real-time updates between dashboard and backend:

#### Dashboard WebSocket Client

```typescript
// frontend/dashboard/lib/websocket.ts
export function createAttackMonitoringWebSocket() {
  const ws = new WebSocket(process.env.NEXT_PUBLIC_WS_URL + '/ws/attacks');
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Update dashboard state
  };
  
  return ws;
}
```

### 3. Service Discovery

Configure service URLs in environment variables:

```bash
# backend/.env
KNOWLEDGE_ENGINE_URL=http://localhost:8000
INTEGRATION_HUB_URL=http://localhost:8500
ORCHESTRATOR_URL=http://localhost:3001
OPSEC_MONITOR_URL=http://localhost:8002

# frontend/dashboard/.env.local
NEXT_PUBLIC_API_URL=http://localhost:3001
NEXT_PUBLIC_AI_MODEL_URL=http://localhost:8000
NEXT_PUBLIC_INTEGRATION_HUB_URL=http://localhost:8500
```

## Verification

### 1. Verify AI Training System

```bash
# Check if model was created
ls -lh backend/knowledge_engine/models/

# Test inference
cd backend/knowledge_engine
python inference_example.py --model-path ./models/category_classifier.joblib
```

Expected output:
```
Model loaded successfully!
Model type: random_forest
Number of classes: 63
Top 3 predictions:
1. Insider Threat: 94.15%
2. Malware & Threat: 64.62%
3. Email & Messaging Protocol Exploits: 23.81%
```

### 2. Verify Dashboard

```bash
# Check if dashboard starts
cd frontend/dashboard
npm run dev
```

Expected: Dashboard accessible at http://localhost:3000

### 3. Verify Backend Services

```bash
# Check all services are running
docker-compose ps

# Test Knowledge Engine API
curl http://localhost:8000/health

# Test Integration Hub
curl http://localhost:8500/health

# Test Orchestrator
curl http://localhost:3001/health
```

### 4. End-to-End Integration Test

```bash
# Test classification through API
curl -X POST http://localhost:8000/api/classify \
  -H "Content-Type: application/json" \
  -d '{"description": "Phishing email with malicious attachment"}'

# Test dashboard can reach backend
# Open browser console and run:
fetch(`${process.env.NEXT_PUBLIC_API_URL}/health`)
  .then(r => r.json())
  .then(console.log)
```

## Production Deployment

### 1. Docker Deployment

Use the provided Docker Compose configuration:

```bash
# Build and start all services
docker-compose -f docker-compose.prod.yml up -d

# Check service health
docker-compose ps
```

### 2. Environment Variables

Set production environment variables:

```bash
# Production .env
POSTGRES_HOST=postgres-prod
POSTGRES_PASSWORD=secure_password
REDIS_URL=redis://redis-prod:6379

# Dashboard production .env.local
NEXT_PUBLIC_API_URL=https://api.opsec.ai
NEXT_PUBLIC_WS_URL=wss://api.opsec.ai
NEXT_PUBLIC_AI_MODEL_URL=https://ai.opsec.ai
```

### 3. Model Deployment

Deploy trained models to production:

```bash
# Copy models to production server
scp backend/knowledge_engine/models/* user@prod-server:/app/models/

# Update model path in production config
export MODEL_PATH=/app/models
```

## Troubleshooting

### AI Training Issues

#### NLTK Data Missing

```bash
python -c "import nltk; nltk.download('punkt_tab'); nltk.download('stopwords'); nltk.download('wordnet')"
```

#### Memory Issues During Training

```bash
# Reduce max_features in train_ai_model.py
# Change: TfidfVectorizer(max_features=1000)  # Reduce from 5000
```

#### Database Connection Failed

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U opsec -d attack_db -c "SELECT 1;"
```

### Dashboard Issues

#### Port Already in Use

```bash
# Kill process on port 3000
npx kill-port 3000

# Or use different port
npm run dev -- -p 3001
```

#### Build Errors

```bash
# Clear Next.js cache
rm -rf .next
rm -rf node_modules package-lock.json
npm install
```

#### API Connection Failed

```bash
# Verify backend is running
curl http://localhost:3001/health

# Check environment variables
cat .env.local
```

### Integration Issues

#### WebSocket Connection Failed

```bash
# Check WebSocket endpoint
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  http://localhost:3001/ws/attacks

# Check CORS configuration
```

#### Model Not Loading

```bash
# Verify model file exists
ls -lh backend/knowledge_engine/models/

# Check file permissions
chmod 644 backend/knowledge_engine/models/*.joblib

# Test model loading
python -c "import joblib; joblib.load('backend/knowledge_engine/models/category_classifier.joblib')"
```

## Performance Optimization

### AI Training Optimization

#### For Faster Training

```bash
# Use TF-IDF instead of sentence transformers
--embedding-method tfidf

# Use simpler model
--model-type logistic_regression

# Reduce features
# Edit train_ai_model.py: max_features=1000
```

#### For Better Accuracy

```bash
# Use advanced model
--model-type gradient_boosting

# Use semantic embeddings
--embedding-method sentence_transformer

# Increase features
# Edit train_ai_model.py: max_features=10000
```

### Dashboard Optimization

#### Enable Production Mode

```bash
# Set environment variable
NODE_ENV=production npm run build
```

#### Enable Compression

Add to `next.config.js`:
```javascript
module.exports = {
  compress: true,
  swcMinify: true
}
```

## Monitoring and Logging

### AI Training System

Logs are stored in:
- Console output during training
- Model metadata JSON files
- Training accuracy metrics

### Dashboard

Monitor dashboard performance:
```bash
# Check Next.js build output
npm run build

# Monitor bundle size
npm run build -- --profile
```

### Backend Services

Use Docker logs:
```bash
# View logs for all services
docker-compose logs -f

# View specific service logs
docker-compose logs -f knowledge-engine
```

## Security Considerations

### API Security

1. Enable authentication on all endpoints
2. Use HTTPS in production
3. Implement rate limiting
4. Validate all input data

### Model Security

1. Don't commit trained models to version control
2. Use environment variables for model paths
3. Implement model versioning
4. Regular security audits of model predictions

### Database Security

1. Use strong passwords
2. Enable SSL connections
3. Regular backups
4. Limit database user permissions

## Next Steps

1. **Customize Models**: Train models on your specific attack pattern data
2. **Extend Dashboard**: Add custom visualizations and features
3. **Integrate Additional Tools**: Connect with other security tools
4. **Set Up Monitoring**: Implement comprehensive monitoring and alerting
5. **Scale Deployment**: Deploy to cloud infrastructure for production use

## Support

For additional help:
- AI Training System: See `docs/setup/ai-training.md`
- Dashboard: See `docs/setup/dashboard.md`
- Integration Hub: See `docs/integrations/INTEGRATION_ARCHITECTURE.md`
- General Issues: Check GitHub Issues or project documentation

---

**Comprehensive Setup Guide Version:** 1.0.0  
**Last Updated:** 2026-05-19  
**Platform:** OpsecAI Security Platform