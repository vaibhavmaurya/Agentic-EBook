"""
Local development server — wraps all Lambda handlers as FastAPI routes.
Runs the exact same handler code that deploys to AWS Lambda.

Usage:
    cd services/api
    uvicorn local_dev_server:app --reload --port 8000

OpenAPI docs available at: http://localhost:8000/docs
"""
from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv

# Load .env.local from repo root before importing handlers
_repo_root = os.path.join(os.path.dirname(__file__), "../..")
load_dotenv(os.path.join(_repo_root, ".env.local"))

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from topics import lambda_handler as topics_handler
from public import lambda_handler as public_handler  # implemented in M7

app = FastAPI(
    title="Agentic Ebook Platform API",
    description="Local dev server wrapping AWS Lambda handlers.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_lambda_event(request: Request, body: bytes, path_params: dict) -> dict:
    """Convert a FastAPI request into an API Gateway HTTP API payload format 2.0 event."""
    return {
        "rawPath": request.url.path,
        "rawQueryString": str(request.url.query),
        "headers": dict(request.headers),
        "pathParameters": path_params,
        "queryStringParameters": dict(request.query_params),
        "body": body.decode("utf-8") if body else None,
        "isBase64Encoded": False,
        "requestContext": {
            "http": {
                "method": request.method,
                "path": request.url.path,
            },
            # Simulate a logged-in admin for local dev — real JWT validation happens in AWS
            "authorizer": {
                "jwt": {
                    "claims": {
                        "email": os.environ.get("ADMIN_USERNAME", "dev@local"),
                        "sub": "local-dev-user",
                    }
                }
            },
        },
    }


def _lambda_response(result: dict) -> Response:
    return Response(
        content=result.get("body", ""),
        status_code=result.get("statusCode", 200),
        headers=result.get("headers", {}),
        media_type="application/json",
    )


# ── Admin topic routes ────────────────────────────────────────────────────────


@app.get("/admin/topics")
async def list_topics(request: Request):
    body = await request.body()
    event = _build_lambda_event(request, body, {})
    return _lambda_response(topics_handler(event, None))


@app.post("/admin/topics")
async def create_topic(request: Request):
    body = await request.body()
    event = _build_lambda_event(request, body, {})
    return _lambda_response(topics_handler(event, None))


@app.put("/admin/topics/reorder")
async def reorder_topics(request: Request):
    body = await request.body()
    event = _build_lambda_event(request, body, {})
    return _lambda_response(topics_handler(event, None))


@app.get("/admin/topics/{topic_id}")
async def get_topic(topic_id: str, request: Request):
    body = await request.body()
    event = _build_lambda_event(request, body, {"topicId": topic_id})
    return _lambda_response(topics_handler(event, None))


@app.put("/admin/topics/{topic_id}")
async def update_topic(topic_id: str, request: Request):
    body = await request.body()
    event = _build_lambda_event(request, body, {"topicId": topic_id})
    return _lambda_response(topics_handler(event, None))


@app.delete("/admin/topics/{topic_id}")
async def delete_topic(topic_id: str, request: Request):
    body = await request.body()
    event = _build_lambda_event(request, body, {"topicId": topic_id})
    return _lambda_response(topics_handler(event, None))


@app.post("/admin/topics/{topic_id}/trigger")
async def trigger_run(topic_id: str, request: Request):
    body = await request.body()
    event = _build_lambda_event(request, body, {"topicId": topic_id})
    return _lambda_response(topics_handler(event, None))


# ── Public routes (M7) ────────────────────────────────────────────────────────


@app.post("/public/comments")
async def post_comment(request: Request):
    body = await request.body()
    event = _build_lambda_event(request, body, {})
    return _lambda_response(public_handler(event, None))


@app.post("/public/highlights")
async def post_highlight(request: Request):
    body = await request.body()
    event = _build_lambda_event(request, body, {})
    return _lambda_response(public_handler(event, None))


@app.get("/public/releases/latest")
async def get_releases(request: Request):
    body = await request.body()
    event = _build_lambda_event(request, body, {})
    return _lambda_response(public_handler(event, None))


# ── Health check ──────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "env": os.environ.get("ENV", "local")}
