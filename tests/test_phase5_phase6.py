import uuid
import pytest
from app.phase4_context.schemas import EvaluationContextOut
from app.phase5_agents.agents.accuracy_agent import evaluate_accuracy
from app.phase5_agents.agents.completeness_agent import evaluate_completeness
from app.phase5_agents.agents.depth_agent import evaluate_depth
from app.phase5_agents.evaluator import run_multi_agent_evaluation
from app.phase6_consensus.agreement import calculate_agreement_and_confidence
from app.phase6_consensus.rules import calculate_weighted_marks_and_status
from app.phase6_consensus.feedback import consolidate_agent_feedback


@pytest.fixture
def sample_context():
    return EvaluationContextOut(
        context_id=uuid.uuid4(),
        student_id="STU-001",
        evaluation_id=uuid.uuid4(),
        blueprint_id=uuid.uuid4(),
        question_id="Q13",
        question_number="13",
        question_text="Define Software Engineering.",
        question_intent="Definition",
        question_type="Short Answer",
        maximum_marks=5.0,
        expected_answer_depth="Short",
        student_answer="Software engineering is a systematic approach to software development.",
        expected_answer_characteristics=["Technical Terminology"],
        key_concepts=["Software Engineering", "Development"],
        keywords=["Software", "Engineering", "Development"],
        evaluation_criteria=["Concept Accuracy"],
        status="READY_FOR_PHASE_5",
    )


@pytest.mark.asyncio
async def test_phase5_individual_agents(sample_context):
    acc = await evaluate_accuracy(sample_context)
    cmp = await evaluate_completeness(sample_context)
    dph = await evaluate_depth(sample_context)

    assert "score" in acc and "percentage" in acc
    assert "covered_points" in cmp
    assert "strong_sections" in dph


@pytest.mark.asyncio
async def test_phase5_parallel_execution(sample_context):
    acc_res, cmp_res, dph_res = await run_multi_agent_evaluation(sample_context)
    assert acc_res["status"] == "COMPLETED"
    assert cmp_res["status"] == "COMPLETED"
    assert dph_res["status"] == "COMPLETED"


def test_phase6_agreement_analysis():
    # <= 10% diff -> High Agreement
    lbl, conf = calculate_agreement_and_confidence([90.0, 85.0, 88.0], [0.9, 0.9, 0.9])
    assert lbl == "High Agreement"
    assert conf >= 0.85

    # 10% - 20% diff -> Medium Agreement
    lbl, conf = calculate_agreement_and_confidence([90.0, 75.0, 85.0], [0.9, 0.9, 0.9])
    assert lbl == "Medium Agreement"

    # > 20% diff -> Low Agreement
    lbl, conf = calculate_agreement_and_confidence([90.0, 60.0, 85.0], [0.9, 0.9, 0.9])
    assert lbl == "Low Agreement"


def test_phase6_consensus_rules_weights():
    # 5.0 max marks, perfect scores: Accuracy=5.0 (50%), Completeness=5.0 (30%), Depth=5.0 (20%)
    w_score, final_m, pct, stat = calculate_weighted_marks_and_status(
        accuracy_score=5.0,
        accuracy_status="COMPLETED",
        completeness_score=5.0,
        completeness_status="COMPLETED",
        depth_score=5.0,
        depth_status="COMPLETED",
        maximum_marks=5.0,
    )
    assert final_m == 5.0
    assert pct == 100.0
    assert stat == "Excellent"


def test_phase6_consensus_weight_redistribution_on_failure():
    # If Depth Agent fails, Accuracy (50%) and Completeness (30%) are redistributed to 62.5% and 37.5%
    w_score, final_m, pct, stat = calculate_weighted_marks_and_status(
        accuracy_score=4.0,
        accuracy_status="COMPLETED",
        completeness_score=4.0,
        completeness_status="COMPLETED",
        depth_score=0.0,
        depth_status="FAILED",
        maximum_marks=5.0,
    )
    assert final_m == 4.0
    assert pct == 80.0
    assert stat == "Very Good"


def test_phase6_feedback_deduplication():
    acc_dict = {"correct_concepts": ["Software Engineering"], "technical_errors": [], "remarks": "Accurate."}
    cmp_dict = {"covered_points": ["Software Engineering"], "missing_concepts": ["Lifecycle"], "missing_keywords": [], "remarks": "Complete."}
    dph_dict = {"strong_sections": ["Definition"], "weak_sections": [], "remarks": "Good depth."}

    strengths, weaknesses, missing, suggestions, remarks = consolidate_agent_feedback(
        acc_dict, cmp_dict, dph_dict
    )
    assert isinstance(strengths, list)
    assert len(strengths) == len(set(strengths))  # Deduplicated
    assert "Accurate. Complete. Good depth." in remarks
