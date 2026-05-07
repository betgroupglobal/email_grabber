"""
Knowledge Engine FastAPI — main REST entry point.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from config import API_HOST, API_PORT
from models import (
    SearchQuery,
    SearchResponse,
    AttackRecord,
    AttackVectorRequest,
    AttackVectorResponse,
    MitreMapping,
    OpsecNote,
)
from searcher import AttackSearcher
from attack_chainer import AttackChainer

log = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)

searcher: AttackSearcher
chainer: AttackChainer


@asynccontextmanager
async def lifespan(app: FastAPI):
    global searcher, chainer
    log.info("Initialising searcher and chainer…")
    searcher = AttackSearcher()
    chainer = AttackChainer(searcher)
    log.info("Knowledge Engine ready.")
    yield
    searcher.pg.close()


app = FastAPI(
    title="Attack Knowledge Engine",
    description="Semantic search and attack vector generation from the Attack Dataset",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "knowledge-engine"}


# ── Search ────────────────────────────────────────────────────────────────────

@app.post("/search", response_model=SearchResponse)
def search(query: SearchQuery):
    """
    Semantic search over the attack knowledge base.
    Supply a natural-language description of a target, service, vulnerability,
    or attack technique. Returns ranked attack records with similarity scores.
    """
    return searcher.semantic_search(
        query=query.query,
        top_k=query.top_k,
        category=query.category_filter,
        attack_type=query.attack_type_filter,
        mitre=query.mitre_filter,
    )


@app.get("/search/keyword", response_model=List[AttackRecord])
def keyword_search(
    q: str = Query(..., description="Keyword or phrase"),
    limit: int = Query(20, ge=1, le=100),
):
    return searcher.keyword_search(q, limit=limit)


# ── MITRE ─────────────────────────────────────────────────────────────────────

@app.get("/mitre/{technique_id}", response_model=List[AttackRecord])
def get_by_mitre(technique_id: str, limit: int = 20):
    results = searcher.get_by_mitre(technique_id, limit=limit)
    if not results:
        raise HTTPException(status_code=404, detail="No attacks found for that technique")
    return results


@app.get("/mitre", response_model=List[Dict[str, Any]])
def list_mitre():
    return searcher.list_mitre_techniques()


# ── Category ──────────────────────────────────────────────────────────────────

@app.get("/categories", response_model=List[Dict[str, Any]])
def list_categories():
    return searcher.list_categories()


@app.get("/categories/{category}", response_model=List[AttackRecord])
def get_by_category(category: str, limit: int = 50):
    return searcher.get_by_category(category, limit=limit)


# ── Target ────────────────────────────────────────────────────────────────────

@app.get("/targets/{target_type}", response_model=List[AttackRecord])
def get_by_target(target_type: str, limit: int = 30):
    return searcher.get_by_target(target_type, limit=limit)


# ── Tools ─────────────────────────────────────────────────────────────────────

@app.get("/tools", response_model=List[Dict[str, Any]])
def list_tools():
    return searcher.list_tools()


# ── Attack Vector Builder ─────────────────────────────────────────────────────

@app.post("/attack-vector", response_model=AttackVectorResponse)
def build_attack_vector(request: AttackVectorRequest):
    """
    Given a target context (description, detected services, OS),
    generate multi-stage ranked attack chains with OpSec notes.
    """
    return chainer.build_chains(request)


# ── OpSec ─────────────────────────────────────────────────────────────────────

@app.get("/opsec/{attack_id}", response_model=OpsecNote)
def get_opsec_note(attack_id: int):
    """
    Retrieve OpSec/evasion notes for a specific attack record.
    """
    note = chainer.get_opsec_note(attack_id)
    if not note:
        raise HTTPException(status_code=404, detail="Attack record not found")
    return note


# ── Run directly ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host=API_HOST, port=API_PORT, reload=True)
