"""
Configuration loader for model_config.yaml.

All modules in openai-runtime import from here — never read the YAML directly.

S3 loading:
  Set MODEL_CONFIG_PATH=s3://bucket/config/model_config.yaml to load from S3.
  Set PROMPTS_CONFIG_PATH=s3://bucket/config/prompts.yaml to load from S3.
  If neither is set, the module also checks S3_ARTIFACT_BUCKET/config/<file>
  before falling back to the bundled YAML files.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

_CONFIG_PATH = Path(__file__).parent / "model_config.yaml"
_PROMPTS_PATH = Path(__file__).parent / "prompts.yaml"
_S3_BUCKET = os.environ.get("S3_ARTIFACT_BUCKET", "")


def _load_yaml_from_s3(s3_uri: str) -> dict:
    """Download and parse a YAML file from an s3:// URI."""
    import boto3
    rest = s3_uri[5:]
    bucket, key = rest.split("/", 1)
    region = os.environ.get("AWS_REGION", os.environ.get("APP_REGION", "us-east-1"))
    s3 = boto3.client("s3", region_name=region)
    resp = s3.get_object(Bucket=bucket, Key=key)
    return yaml.safe_load(resp["Body"].read())


def _load_yaml(default_local_path: Path, env_var: str, s3_config_key: str) -> dict:
    """
    Load a YAML config file with priority:
      1. Explicit env var (supports s3:// URI or local path)
      2. S3_ARTIFACT_BUCKET/config/<s3_config_key>  (if bucket env var is set)
      3. Bundled local file (default_local_path)
    """
    explicit = os.environ.get(env_var, "")
    if explicit:
        if explicit.startswith("s3://"):
            return _load_yaml_from_s3(explicit)
        with open(explicit) as f:
            return yaml.safe_load(f)

    if _S3_BUCKET:
        s3_uri = f"s3://{_S3_BUCKET}/config/{s3_config_key}"
        try:
            return _load_yaml_from_s3(s3_uri)
        except Exception:
            pass  # fall through to bundled file

    with open(default_local_path) as f:
        return yaml.safe_load(f)


# ── Typed config dataclasses ──────────────────────────────────────────────────

@dataclass
class ModelTier:
    high_capability: str
    low_capability: str


@dataclass
class PricingTier:
    input: float   # USD per million tokens
    output: float


@dataclass
class ProviderPricing:
    high_capability: PricingTier
    low_capability: PricingTier


@dataclass
class ProviderConfig:
    api_key_secret: str           # AWS Secrets Manager secret name
    models: ModelTier
    pricing: ProviderPricing


@dataclass
class AgentConfig:
    capability: str               # "high" | "low"
    max_tokens: int
    temperature: float
    timeout_sec: int
    model_override: Optional[str] = None
    # Research-specific
    max_search_queries: int = 6
    max_sources: int = 10
    max_source_chars: int = 4000


@dataclass
class WebSearchToolConfig:
    bing_secret_name: str
    serpapi_secret_name: str
    results_per_query: int


@dataclass
class FetchUrlToolConfig:
    timeout_sec: int
    max_content_bytes: int
    user_agent: str


@dataclass
class ResearchToolsConfig:
    web_search: WebSearchToolConfig
    fetch_url: FetchUrlToolConfig


@dataclass
class ModelConfig:
    version: str
    active_provider: str
    providers: dict[str, ProviderConfig]
    agents: dict[str, AgentConfig]
    research_tools: ResearchToolsConfig


# ── Loader ────────────────────────────────────────────────────────────────────

def _load_raw() -> dict:
    """Load model_config.yaml from S3 or local file."""
    return _load_yaml(_CONFIG_PATH, "MODEL_CONFIG_PATH", "model_config.yaml")


@lru_cache(maxsize=1)
def load_config() -> ModelConfig:
    raw = _load_raw()

    providers: dict[str, ProviderConfig] = {}
    for name, pc in raw.get("providers", {}).items():
        pricing_raw = pc.get("pricing_per_million_tokens", {})
        providers[name] = ProviderConfig(
            api_key_secret=pc["api_key_secret"],
            models=ModelTier(
                high_capability=pc["models"]["high_capability"],
                low_capability=pc["models"]["low_capability"],
            ),
            pricing=ProviderPricing(
                high_capability=PricingTier(**pricing_raw.get("high_capability", {"input": 0, "output": 0})),
                low_capability=PricingTier(**pricing_raw.get("low_capability", {"input": 0, "output": 0})),
            ),
        )

    agents: dict[str, AgentConfig] = {}
    for name, ac in raw.get("agents", {}).items():
        agents[name] = AgentConfig(
            capability=ac["capability"],
            max_tokens=ac["max_tokens"],
            temperature=ac["temperature"],
            timeout_sec=ac["timeout_sec"],
            model_override=ac.get("model_override"),
            max_search_queries=ac.get("max_search_queries", 6),
            max_sources=ac.get("max_sources", 10),
            max_source_chars=ac.get("max_source_chars", 4000),
        )

    rt_raw = raw.get("research_tools", {})
    research_tools = ResearchToolsConfig(
        web_search=WebSearchToolConfig(**rt_raw.get("web_search", {
            "bing_secret_name": "", "serpapi_secret_name": "", "results_per_query": 5
        })),
        fetch_url=FetchUrlToolConfig(**rt_raw.get("fetch_url", {
            "timeout_sec": 15, "max_content_bytes": 512000,
            "user_agent": "EbookBot/1.0",
        })),
    )

    return ModelConfig(
        version=raw["version"],
        active_provider=raw["active_provider"],
        providers=providers,
        agents=agents,
        research_tools=research_tools,
    )


def get_agent_config(agent_name: str) -> AgentConfig:
    return load_config().agents[agent_name]


def resolve_model(agent_name: str) -> str:
    """Return the concrete model ID for the given agent."""
    cfg = load_config()
    agent = cfg.agents[agent_name]
    if agent.model_override:
        return agent.model_override
    provider = cfg.providers[cfg.active_provider]
    return (provider.models.high_capability if agent.capability == "high"
            else provider.models.low_capability)


@lru_cache(maxsize=1)
def _load_prompts() -> dict:
    """Load prompts.yaml from S3 or local file."""
    return _load_yaml(_PROMPTS_PATH, "PROMPTS_CONFIG_PATH", "prompts.yaml")


def get_prompt(agent: str, key: str) -> str:
    """
    Return the prompt template string for the given agent and key.

    Template variables use ${variable_name} syntax (Python string.Template).
    Call string.Template(get_prompt(...)).safe_substitute(**vars) in agent code.

    Raises KeyError if agent or key is not found in prompts.yaml.
    """
    prompts = _load_prompts()
    agent_prompts = prompts.get(agent)
    if agent_prompts is None:
        raise KeyError(f"No prompts defined for agent '{agent}' in prompts.yaml")
    template = agent_prompts.get(key)
    if template is None:
        raise KeyError(f"Prompt key '{key}' not found under agent '{agent}' in prompts.yaml")
    return template


def active_provider_name() -> str:
    return load_config().active_provider


def estimate_cost_usd(agent_name: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a completed agent call."""
    cfg = load_config()
    agent = cfg.agents[agent_name]
    provider = cfg.providers[cfg.active_provider]
    tier = provider.pricing.high_capability if agent.capability == "high" else provider.pricing.low_capability
    return (input_tokens / 1_000_000 * tier.input) + (output_tokens / 1_000_000 * tier.output)
