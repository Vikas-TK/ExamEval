"""
Phase 5 – Parallel Multi-Agent Evaluator
Runs Accuracy, Completeness, and Depth agents concurrently for each question.
"""
from __future__ import annotations

import asyncio
import uuid
import logging
from typing import Dict, Any, Tuple

from app.phase4_context.schemas import EvaluationContextOut
from app.phase5_agents.agents.accuracy_agent import evaluate_accuracy
from app.phase5_agents.agents.completeness_agent import evaluate_completeness
from app.phase5_agents.agents.depth_agent import evaluate_depth

logger = logging.getLogger(__name__)


async def run_multi_agent_evaluation(
    ctx: EvaluationContextOut
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Executes Accuracy, Completeness, and Depth agents concurrently using asyncio.gather.
    Fault-tolerant: If an individual agent fails, returns a FAILED fallback object
    without canceling the other agents.
    """
    async def _safe_accuracy():
        try:
            return await evaluate_accuracy(ctx)
        except Exception as exc:
            logger.error("Accuracy agent execution failed for Q%s: %s", ctx.question_number, exc)
            return {
                "score": 0.0,
                "percentage": 0.0,
                "confidence": 0.0,
                "correct_concepts": [],
                "incorrect_concepts": [],
                "technical_errors": [f"Agent failure: {exc}"],
                "remarks": "Accuracy Agent execution failed.",
                "status": "FAILED",
            }

    async def _safe_completeness():
        try:
            return await evaluate_completeness(ctx)
        except Exception as exc:
            logger.error("Completeness agent execution failed for Q%s: %s", ctx.question_number, exc)
            return {
                "score": 0.0,
                "percentage": 0.0,
                "confidence": 0.0,
                "covered_points": [],
                "missing_points": [f"Agent failure: {exc}"],
                "missing_keywords": [],
                "missing_concepts": [],
                "remarks": "Completeness Agent execution failed.",
                "status": "FAILED",
            }

    async def _safe_depth():
        try:
            return await evaluate_depth(ctx)
        except Exception as exc:
            logger.error("Depth agent execution failed for Q%s: %s", ctx.question_number, exc)
            return {
                "score": 0.0,
                "percentage": 0.0,
                "confidence": 0.0,
                "strong_sections": [],
                "weak_sections": [f"Agent failure: {exc}"],
                "remarks": "Depth Agent execution failed.",
                "status": "FAILED",
            }

    # Parallel Execution
    acc_res, cmp_res, dph_res = await asyncio.gather(
        _safe_accuracy(),
        _safe_completeness(),
        _safe_depth(),
    )

    return acc_res, cmp_res, dph_res
