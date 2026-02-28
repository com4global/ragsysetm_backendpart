"""
Prompt Loader — Phase 6: Prompt Versioning
===========================================
Loads prompts from YAML config files in the prompts/ directory.

Benefits:
1. Edit prompts without touching Python code
2. Git tracks prompt version history automatically
3. Easy A/B testing: create v2 copies and switch
4. Clear separation of concerns: logic vs content

Usage:
    from prompt_loader import load_prompt, get_system_prompt
    
    # Load a specific prompt config
    config = load_prompt("rag_query_en")
    
    # Get the system prompt string
    system_prompt = get_system_prompt("rag_query_en")
"""

import os
import logging
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# PROMPT DIRECTORY
# ──────────────────────────────────────────────────────────────

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

# Cache loaded prompts (reload on file change in dev)
_prompt_cache: Dict[str, Dict] = {}
_prompt_mtimes: Dict[str, float] = {}


# ──────────────────────────────────────────────────────────────
# YAML LOADER (with fallback if PyYAML not available)
# ──────────────────────────────────────────────────────────────

def _load_yaml(filepath: str) -> Dict:
    """Load a YAML file. Falls back to basic parsing if PyYAML unavailable."""
    try:
        import yaml
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Minimal YAML parser for simple key: value files
        logger.warning("PyYAML not installed — using basic YAML parser")
        return _basic_yaml_parse(filepath)


def _basic_yaml_parse(filepath: str) -> Dict:
    """Very basic YAML parser for simple configs (fallback)."""
    result = {}
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Handle multiline values (key: |)
    import re
    blocks = re.split(r'\n(?=\w)', content)
    
    for block in blocks:
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        
        if ": |" in block:
            key = block.split(": |")[0].strip()
            value = block.split(": |", 1)[1].strip()
            result[key] = value
        elif ": " in block:
            parts = block.split(": ", 1)
            key = parts[0].strip()
            value = parts[1].strip().strip('"').strip("'")
            result[key] = value
    
    return result


# ──────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────

def load_prompt(name: str) -> Dict:
    """
    Load a prompt config by name.
    
    Args:
        name: Prompt name (filename without .yaml extension)
        
    Returns:
        Dict with keys: version, name, system_prompt, user_prompt_template, etc.
    """
    filepath = os.path.join(PROMPTS_DIR, f"{name}.yaml")
    
    if not os.path.exists(filepath):
        logger.warning(f"⚠️ Prompt config not found: {filepath}")
        return {}
    
    # Check cache (reload if file changed)
    mtime = os.path.getmtime(filepath)
    if name in _prompt_cache and _prompt_mtimes.get(name) == mtime:
        return _prompt_cache[name]
    
    try:
        config = _load_yaml(filepath)
        _prompt_cache[name] = config
        _prompt_mtimes[name] = mtime
        logger.info(f"📝 Loaded prompt: {name} v{config.get('version', '?')}")
        return config
    except Exception as e:
        logger.error(f"❌ Failed to load prompt {name}: {e}")
        return {}


def get_system_prompt(name: str) -> str:
    """
    Get just the system prompt string from a prompt config.
    
    Args:
        name: Prompt name (e.g., "rag_query_en")
        
    Returns:
        System prompt string, or empty string if not found
    """
    config = load_prompt(name)
    return config.get("system_prompt", config.get("system_prompt_addon", ""))


def get_user_prompt_template(name: str) -> str:
    """Get the user prompt template from a config."""
    config = load_prompt(name)
    return config.get("user_prompt_template", "CONTEXT:\n{context}\n\nUSER QUESTION:\n{question}")


def list_prompts() -> list:
    """List all available prompt configs."""
    if not os.path.exists(PROMPTS_DIR):
        return []
    
    prompts = []
    for f in os.listdir(PROMPTS_DIR):
        if f.endswith(".yaml") or f.endswith(".yml"):
            name = f.rsplit(".", 1)[0]
            config = load_prompt(name)
            prompts.append({
                "name": name,
                "version": config.get("version", "?"),
                "description": config.get("description", ""),
            })
    
    return prompts
