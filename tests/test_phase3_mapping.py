"""
Regression tests for the Phase 3 anchor detection / segmentation / mapping
fix: long multi-page descriptive answers were being truncated to just their
first paragraph because internal numbered lists ("1. Take input...",
"2. Separate...") were misdetected as fresh top-level question anchors, and
`_split_section_header_blocks` then discarded every paragraph after the
first one as an orphan. See app/phase3/anchor_detector.py,
app/phase3/segmenter.py, app/phase3/mapper.py.
"""
from __future__ import annotations

import uuid

import app.phase3.mapper as mapper_module
from app.phase3.anchor_detector import _normalize_label, detect_anchors
from app.phase3.mapper import _extract_blueprint_questions, map_answers_to_blueprint
from app.phase3.schemas import AnswerBlock, BlueprintQuestion, QuestionAnchor
from app.phase3.segmenter import segment_answers


def _ocr(pages_text: list[str]) -> dict:
    return {
        "pages": [
            {"page_number": i + 1, "transcript": text, "visual_elements": []}
            for i, text in enumerate(pages_text)
        ]
    }


def _blueprint(sections: list[tuple[str, list[tuple[str, str, float, str]]]]) -> dict:
    """sections: [(name, [(question_id, question_number, marks, text), ...])]"""
    return {
        "sections": [
            {
                "name": name,
                "questions": [
                    {
                        "question_id": qid,
                        "question_number": qnum,
                        "question_text": text,
                        "maximum_marks": marks,
                        "question_type": "Descriptive",
                        "question_order": i + 1,
                    }
                    for i, (qid, qnum, marks, text) in enumerate(questions)
                ],
            }
            for name, questions in sections
        ]
    }


def _run(ocr_json: dict, blueprint_json: dict):
    # Mirrors Phase3Service.run(): the real blueprint question numbers are
    # always available and threaded into anchor detection/segmentation, so
    # tests exercise the same path production does.
    blueprint_question_numbers = {
        _normalize_label(bq.question_number)
        for bq in _extract_blueprint_questions(blueprint_json)
    }
    flat_text, page_map, anchors = detect_anchors(ocr_json, blueprint_question_numbers)
    blocks = segment_answers(flat_text, anchors, ocr_json, page_map, blueprint_question_numbers)
    return map_answers_to_blueprint(blocks, blueprint_json, uuid.uuid4(), uuid.uuid4())


def _by_id(mapped_qas, qid):
    return next(m for m in mapped_qas if m.question_id == qid)


def _ocr_with_structure_map(pages: list[tuple[str, dict]]) -> dict:
    """pages: [(transcript, structure_map), ...]"""
    return {
        "pages": [
            {"page_number": i + 1, "transcript": text, "structure_map": sm, "visual_elements": []}
            for i, (text, sm) in enumerate(pages)
        ]
    }


def test_short_discrete_answers_stay_individually_mapped():
    """Part-A style: each bare number is its own real answer, not a continuation."""
    ocr_json = _ocr([
        "Part-A\n"
        "1. contractive autoencoder\n\n"
        "2. Single\n\n"
        "3. True\n"
    ])
    blueprint_json = _blueprint([
        ("Part-A", [
            ("q1", "1", 1.0, "Which autoencoder type restricts capacity directly?"),
            ("q2", "2", 1.0, "How many hidden layers does a simple autoencoder need?"),
            ("q3", "3", 1.0, "True or False: autoencoders can denoise images."),
        ]),
    ])

    mapped = _run(ocr_json, blueprint_json)

    assert "contractive autoencoder" in _by_id(mapped, "q1").student_answer
    assert "Single" in _by_id(mapped, "q2").student_answer
    assert "True" in _by_id(mapped, "q3").student_answer
    # Each answer must stay separate — none should bleed into another.
    assert "Single" not in _by_id(mapped, "q1").student_answer
    assert "True" not in _by_id(mapped, "q2").student_answer
    assert all(m.mapping_status == "MAPPED" for m in mapped)


def test_long_multipage_essay_is_not_truncated():
    """
    A 14-mark essay (Q13) spanning multiple pages, containing its own
    internal numbered working-process list (1-7) and several blank-line
    paragraphs, must map as ONE complete answer — not just its first
    paragraph — and must not swallow or corrupt the following Q14.
    """
    page1 = (
        "Part-C\n"
        "13) LSTM Model:\n"
        "LSTM stands for Long Short Term Memory\n"
        "LSTM is a special type of RNN used to learn long-term dependencies "
        "in sequential data.\n"
    )
    page2 = (
        "Architecture:\n"
        "Cell state has gates which control the overflow.\n\n"
        "Working Process in Caption Generation:\n"
        "1. Take input as a video frame\n"
        "2. Separate each frame from that video\n"
        "3. Extract features from the image\n"
        "4. Apply LSTM to feed feature\n"
        "5. Find the next word\n"
        "6. Extract the words one by one\n"
        "7. Combine words to form the complete sequence\n"
    )
    page3 = (
        "This was the working procedure of LSTM in this caption generation "
        "from the video frames\n\n"
        "14) GRU architecture:\n"
        "GRU is a special type of RNN and it is used in time series, text, "
        "image etc.\n"
    )
    ocr_json = _ocr([page1, page2, page3])
    blueprint_json = _blueprint([
        ("Part-C", [
            ("q13", "13", 14.0, "Explain the LSTM model and its use in caption generation."),
            ("q14", "14", 14.0, "Explain the GRU architecture."),
        ]),
    ])

    mapped = _run(ocr_json, blueprint_json)
    q13 = _by_id(mapped, "q13")
    q14 = _by_id(mapped, "q14")

    assert q13.mapping_status == "MAPPED"
    for expected in [
        "LSTM stands for Long Short Term Memory",
        "Architecture:",
        "Working Process in Caption Generation",
        "1. Take input as a video frame",
        "7. Combine words to form the complete sequence",
        "This was the working procedure of LSTM",
    ]:
        assert expected in q13.student_answer, f"missing from q13 answer: {expected!r}"

    # Q14 must be its own answer, not contaminated with Q13's content or its
    # internal numbered list being misattributed here.
    assert q14.mapping_status == "MAPPED"
    assert "GRU is a special type of RNN" in q14.student_answer
    assert "LSTM" not in q14.student_answer
    assert "Take input as a video frame" not in q14.student_answer


def test_genuinely_missed_adjacent_question_numbers_still_split():
    """
    A real 'next question's number got missed' case (rare, but the original
    reason _split_section_header_blocks existed) must still work: strictly
    increasing bare numbers immediately after a real anchor are still
    treated as new questions, not swallowed into the previous one.
    """
    ocr_json = _ocr([
        "Part-B\n"
        "5) Explain use cases.\n"
        "A use case is a description of system behavior.\n\n"
        "6. Explain actors.\n"
        "An actor is an external entity interacting with the system.\n\n"
        "7. Explain scenarios.\n"
        "A scenario is one path through a use case.\n"
    ])
    blueprint_json = _blueprint([
        ("Part-B", [
            ("q5", "5", 2.0, "Explain use cases."),
            ("q6", "6", 2.0, "Explain actors."),
            ("q7", "7", 2.0, "Explain scenarios."),
        ]),
    ])

    mapped = _run(ocr_json, blueprint_json)

    assert "use case is a description" in _by_id(mapped, "q5").student_answer
    assert "actor is an external entity" in _by_id(mapped, "q6").student_answer
    assert "scenario is one path" in _by_id(mapped, "q7").student_answer


def test_orphaned_fragment_is_reattached_not_dropped():
    """
    Mapper safety net (Pass 4): a fragment nothing else can claim (no label,
    no keyword overlap with any question) must be appended to the nearest
    preceding mapped question rather than silently vanish, and must not
    alter any other question's mapping.
    """
    ocr_json = _ocr([
        "Part-D\n"
        "19(a) Denoising autoencoder:\n"
        "Autoencoder is a type of neural network that compresses input data "
        "and reconstructs the original image.\n\n"
        "xyz miscellaneous trailing remark with no shared vocabulary at all "
        "zzqq wobble frobnicate.\n"
    ])
    blueprint_json = _blueprint([
        ("Part-D", [
            ("q19a", "19(a)", 10.0, "Explain the denoising autoencoder."),
        ]),
    ])

    mapped = _run(ocr_json, blueprint_json)
    q19a = _by_id(mapped, "q19a")

    assert q19a.mapping_status == "MAPPED"
    assert "compresses input data" in q19a.student_answer
    assert "zzqq wobble frobnicate" in q19a.student_answer


def test_sections_answered_out_of_order_still_isolate_correctly():
    """
    A student is free to answer optional/choice sections in whatever order
    they like — writing Part D right after Part A, then Part C, then Part B,
    is completely normal. Two things must both work for this to map
    correctly: (1) "Part-D"/"Part-C"/"Part-B" (hyphenated, not "Part D"
    with a space) must register as real section-boundary anchors so the
    monotonic-sequence guard resets its numbering floor at each one —
    otherwise every later, lower-numbered Part's real questions get
    rejected as "internal list markers" once a higher number (19) was
    already accepted; and (2) "19(a)" must be captured as one compound
    top-level anchor, not just its trailing "(a)" losing the "19".
    """
    ocr_json = _ocr([
        "Part-A\n"
        "1. a) sparse Autoencoder\n"
        "2. True\n",

        "Part-D\n"
        "19(a) Denoising Autoencoder:\n"
        "Denoising encoder is used to enhance the noisy input into a clearer "
        "form using a bottleneck.\n",

        "Part-c\n"
        "17. Named Entity Recognition:(NER)\n"
        "NER is used to recognize a word from the given data and identify "
        "the predefined entity.\n",

        "Part-B\n"
        "13. Standard Autoencoders can perform well on low-dimensional data, "
        "while Sparse Autoencoders perform better on high-dimensional data.\n"
        "14. GAN has two networks: Generative and Discriminative.\n",
    ])
    blueprint_json = _blueprint([
        ("Part A", [
            ("q1", "1", 0.5, "Which autoencoder reduces overfitting?"),
            ("q2", "2", 0.5, "True or False."),
        ]),
        ("Part B", [
            ("q13", "13", 2.0, "Compare standard vs sparse autoencoders."),
            ("q14", "14", 2.0, "Determine the suitability of GANs."),
        ]),
        ("Part C", [
            ("q17", "17", 14.0, "Demonstrate NER using deep learning."),
        ]),
        ("Part D", [
            ("q19a", "19(a)", 10.0, "Explain the denoising autoencoder."),
        ]),
    ])

    mapped = _run(ocr_json, blueprint_json)

    q1 = _by_id(mapped, "q1")
    q2 = _by_id(mapped, "q2")
    q13 = _by_id(mapped, "q13")
    q14 = _by_id(mapped, "q14")
    q17 = _by_id(mapped, "q17")
    q19a = _by_id(mapped, "q19a")

    for q in (q1, q2, q13, q14, q17, q19a):
        assert q.mapping_status == "MAPPED", f"{q.question_id} was {q.mapping_status}"

    assert "sparse autoencoder" in q1.student_answer.lower()
    assert "true" in q2.student_answer.lower()
    assert "standard autoencoders" in q13.student_answer.lower()
    assert "gan has two networks" in q14.student_answer.lower()
    assert "named entity recognition" in q17.student_answer.lower()
    assert "denoising encoder" in q19a.student_answer.lower()

    # None of Part B/C/D's content leaked backward into Part A's short answers.
    assert "Denoising" not in q1.student_answer
    assert "GAN" not in q2.student_answer


def test_higher_number_answered_before_lower_one_in_same_section():
    """
    A "answer any two of 16/17/18" style Part has no expected order — a
    student writing Q18 before Q16, with no Part header between them (same
    section, so the guard's usual reset point never fires), must still get
    Q16 recognized as its own real anchor instead of being merged into
    Q18's answer. This is only possible because the real blueprint question
    numbers are threaded into anchor detection (see Phase3Service.run and
    _run() in this file) — the plain monotonic-sequence rule alone would
    reject 16 for not exceeding 18.
    """
    ocr_json = _ocr([
        "Part-C\n"
        "18. LSTM model to generate captions for video frames:\n"
        "LSTM is used to generate captions by extracting the dialogue from "
        "the video frames. First preprocess the video dataset, then train "
        "the model.\n"
        "16. Evaluate the suitability of GRU architecture for time-series "
        "forecasting.\n"
        "GRU is a simplified version of LSTM and is used for sequence "
        "modeling. GRU has two gates: update gate and reset gate.\n"
    ])
    blueprint_json = _blueprint([
        ("Part C", [
            ("q16", "16", 14.0, "Evaluate the suitability of GRU architecture."),
            ("q18", "18", 14.0, "Apply an LSTM model to generate captions for video frames."),
        ]),
    ])

    mapped = _run(ocr_json, blueprint_json)
    q16 = _by_id(mapped, "q16")
    q18 = _by_id(mapped, "q18")

    assert q16.mapping_status == "MAPPED"
    assert q18.mapping_status == "MAPPED"
    assert "GRU is a simplified version" in q16.student_answer
    assert "LSTM is used to generate captions" in q18.student_answer
    # Each stays isolated to its own answer — neither absorbed the other's.
    assert "update gate" not in q18.student_answer
    assert "video frames" not in q16.student_answer



def _anchor(raw_label, normalized, confidence, method="regex", offset=0):
    return QuestionAnchor(
        raw_label=raw_label, normalized=normalized, char_offset=offset,
        label_end_offset=offset + len(raw_label),
        page_number=1, confidence=confidence, detection_method=method,
    )


def _block(text, raw_label="", normalized="", confidence=0.5, method="regex", offset=0):
    return AnswerBlock(
        anchor=_anchor(raw_label, normalized, confidence, method, offset),
        raw_text=text, visual_elements=[], page_numbers=[1],
    )


def _bq(qid, qnum, text, section="Part A", order=1):
    return BlueprintQuestion(
        question_id=qid, question_number=qnum, question_text=text,
        maximum_marks=1.0, question_type="Descriptive", section_name=section,
        question_order=order,
    )


def test_llm_verification_pass_confirms_a_valid_grounded_correction(monkeypatch):
    """
    The one path where Pass 1.5 is SUPPOSED to change something: a block
    weakly matched (low confidence) to q1, whose content actually shares
    vocabulary with q2's question text, gets reassigned to q2 when the LLM
    says so — proving the mechanism can fire, not just refuse.
    """
    b1 = _block("GRU has an update gate and reset gate", confidence=0.5)
    bp = [
        _bq("q1", "1", "Explain sparse autoencoders."),
        _bq("q2", "2", "Explain the GRU update gate mechanism."),
    ]
    direct_matches = {"q1": b1}

    monkeypatch.setattr(
        mapper_module, "_call_local_llm_json",
        lambda system, user, max_tokens=1024: {str(id(b1)): "q2"},
    )
    corrections = mapper_module._llm_verify_uncertain_matches(
        [b1], bp, direct_matches, {"q1"},
    )
    assert corrections == {"q2": str(id(b1))}


def test_llm_verification_rejects_invented_question_id(monkeypatch):
    """A question_id the LLM returns that isn't in the blueprint at all must never be trusted."""
    b1 = _block("GRU has an update gate and reset gate", confidence=0.5)
    bp = [_bq("q1", "1", "Explain sparse autoencoders.")]
    direct_matches = {"q1": b1}

    monkeypatch.setattr(
        mapper_module, "_call_local_llm_json",
        lambda system, user, max_tokens=1024: {str(id(b1)): "totally-fabricated-qid"},
    )
    corrections = mapper_module._llm_verify_uncertain_matches(
        [b1], bp, direct_matches, {"q1"},
    )
    assert corrections == {}


def test_llm_verification_rejects_zero_keyword_overlap(monkeypatch):
    """
    A real question_id paired with a block that shares no vocabulary with
    it is not grounded in the text and must be discarded, exactly like the
    existing semantic-match grounding check.
    """
    b1 = _block("xyz miscellaneous unrelated filler with no shared vocabulary", confidence=0.5)
    bp = [
        _bq("q1", "1", "Explain sparse autoencoders."),
        _bq("q2", "2", "Explain the GRU update gate mechanism."),
    ]
    direct_matches = {"q1": b1}

    monkeypatch.setattr(
        mapper_module, "_call_local_llm_json",
        lambda system, user, max_tokens=1024: {str(id(b1)): "q2"},
    )
    corrections = mapper_module._llm_verify_uncertain_matches(
        [b1], bp, direct_matches, {"q1"},
    )
    assert corrections == {}


def test_llm_verification_rejects_block_outside_uncertain_pool(monkeypatch):
    """
    A block currently owned by a CONFIDENT (non-uncertain) match must never
    be stolen, even if the LLM proposes it — only blocks already flagged
    uncertain are eligible to move.
    """
    confident_block = _block("Sparse autoencoders restrict capacity.", confidence=0.95)
    bp = [
        _bq("q1", "1", "Explain sparse autoencoders."),
        _bq("q2", "2", "Explain the GRU update gate mechanism."),
    ]
    direct_matches = {"q1": confident_block}  # q1 not in uncertain_question_ids

    monkeypatch.setattr(
        mapper_module, "_call_local_llm_json",
        lambda system, user, max_tokens=1024: {str(id(confident_block)): "q2"},
    )
    corrections = mapper_module._llm_verify_uncertain_matches(
        [confident_block], bp, direct_matches, {"q2"},
    )
    assert corrections == {}


def test_llm_verification_failure_returns_empty_and_never_raises(monkeypatch):
    """
    Pass 1.5 must never crash or propagate an exception when the local LLM
    is unavailable (e.g. Ollama not running) — callers must be able to
    treat this identically to "nothing to correct."
    """
    b1 = _block("GRU has an update gate and reset gate", confidence=0.5)
    bp = [_bq("q1", "1", "Explain sparse autoencoders.")]
    direct_matches = {"q1": b1}

    def _raise(*args, **kwargs):
        raise RuntimeError("local LLM endpoint unreachable")

    monkeypatch.setattr(mapper_module, "_call_local_llm_json", _raise)
    corrections = mapper_module._llm_verify_uncertain_matches(
        [b1], bp, direct_matches, {"q1"},
    )
    assert corrections == {}


def test_map_answers_to_blueprint_swaps_ownership_without_double_claiming(monkeypatch):
    """
    End-to-end through map_answers_to_blueprint: when Pass 1.5 moves a block
    from its originally (weakly) matched question to a different one, the
    old question must be vacated, not left pointing at the same block that
    now also belongs to the new question — otherwise the same answer text
    would appear twice under two different question numbers.
    """
    ocr_json = _ocr([
        "Part-A\n"
        "1. GRU has an update gate and reset gate for sequence modeling\n"
    ])
    blueprint_json = _blueprint([
        ("Part-A", [
            ("q1", "1", 1.0, "Explain sparse autoencoders."),
            ("q2", "2", 1.0, "Explain the GRU update gate mechanism."),
        ]),
    ])

    monkeypatch.setattr(mapper_module.settings, "phase3_llm_verification_enabled", True)
    # Force q1's match to read as low-confidence so it's treated as uncertain,
    # regardless of what real confidence regex assigned it.
    monkeypatch.setattr(
        mapper_module.settings, "phase3_llm_verification_confidence_threshold", 0.99
    )

    captured_bid = {}

    def _fake_llm(system, user, max_tokens=1024):
        for line in user.splitlines():
            if "-> currently: q1 |" in line:
                bid = line.split(":", 1)[0].strip()
                captured_bid["bid"] = bid
                return {bid: "q2"}
        return {}

    monkeypatch.setattr(mapper_module, "_call_local_llm_json", _fake_llm)

    mapped = _run(ocr_json, blueprint_json)
    q1 = _by_id(mapped, "q1")
    q2 = _by_id(mapped, "q2")

    assert captured_bid, "test setup did not exercise the LLM correction path"
    assert q2.mapping_status == "MAPPED"
    assert "update gate" in q2.student_answer
    # q1 must be vacated, not left duplicating q2's content.
    assert q1.mapping_status == "SKIPPED"
    assert q1.student_answer is None


def test_ambiguous_choice_group_resolved_by_content_not_duplicated():
    """
    Real-world case from a scanned answer booklet: the row-number and the
    chosen sub-letter of a "19(a) / 19(b)" choice question are written as
    two separate tokens ("19)" then "b)" on its own line) rather than the
    fused "19(b)" the regex expects — so the anchor is detected as a bare
    "19", which shares its stripped digit with BOTH blueprint siblings.
    Without Pass 1b's ambiguous-digit guard, the naive fuzzy-digit fallback
    let both q19a and q19b independently claim the same block, duplicating
    the one real answer onto the question the student never attempted.
    """
    ocr_json = _ocr([
        "Part-D\n"
        "19) b)\n\n"
        "Transfer learning\n\n"
        "Transfer learning is one of the deep learning model technique where "
        "a pre-trained model is reused for a new task. VGG16 is a popular "
        "CNN model used to predict the imagenet dataset.\n"
    ])
    blueprint_json = _blueprint([
        ("Part-D", [
            ("q19a", "19(a)", 10.0, "Explain the denoising autoencoder architecture."),
            ("q19b", "19(b)", 10.0, "Explain transfer learning using VGG16 for image classification."),
        ]),
    ])

    mapped = _run(ocr_json, blueprint_json)
    q19a = _by_id(mapped, "q19a")
    q19b = _by_id(mapped, "q19b")

    assert q19b.mapping_status == "MAPPED"
    assert "Transfer learning" in q19b.student_answer
    # The unanswered sibling must stay unanswered, not inherit a duplicate
    # of q19b's content just because they share the digit "19".
    assert q19a.mapping_status == "SKIPPED"
    assert q19a.student_answer is None


def test_two_digit_anchor_label_does_not_leak_into_answer_text():
    """
    Regression for a label/offset misalignment: char_offset pointed at the
    whole regex match (including the leading newline it consumed) while
    raw_label was only the captured digits, so segmenter.py's
    char_offset + len(raw_label) landed one character short of the label's
    real end — inside a 2+ digit label rather than past it. A two-digit
    question's own second digit (and a single-digit question's whole
    "N. " prefix) used to survive into student_answer.
    """
    ocr_json = _ocr([
        "Part-A\n"
        "11. True\n"
        "12. memory and dependencies.\n"
    ])
    blueprint_json = _blueprint([
        ("Part-A", [
            ("q11", "11", 1.0, "True or False question."),
            ("q12", "12", 1.0, "What does an LSTM cell store?"),
        ]),
    ])

    mapped = _run(ocr_json, blueprint_json)
    q11 = _by_id(mapped, "q11")
    q12 = _by_id(mapped, "q12")

    assert q11.student_answer.strip() == "True"
    assert q12.student_answer.strip().startswith("memory and dependencies")


def test_structure_map_recovers_labels_missing_from_transcript():
    """
    Regression: the OCR vision model sometimes correctly identifies a
    question's number as a structure_map key while dropping that same
    number from the free-form transcript body — e.g. a whole page of
    answers transcribed with no inline "13.", "14." labels at all, even
    though the model still keyed them correctly in structure_map. Phase 3
    must recover these from structure_map rather than losing them entirely
    (previously: Pass 4's safety net would glue this content onto whatever
    question happened to be mapped immediately before it).

    Also verifies a DIFFERENT page's generic {"1": ..., "2": ...}
    structure_map (a long answer's own internal step-by-step breakdown,
    not real question numbers) does NOT get treated as fresh Q1/Q2 anchors
    that collide with the real Part-A Q1/Q2 earlier in the document — the
    same sequence guard that already protects regex anchors must apply here.
    """
    ocr_json = _ocr_with_structure_map([
        ("1. contractive autoencoder\n2. perceptron\n", {"2.": "perceptron", "1.": "contractive autoencoder"}),
        (
            # No inline "13."/"14." labels at all — just the two answers
            # back to back, exactly as the model sometimes transcribes them.
            "Standard autoencoders are less efficient for high dimensional data.\n\n"
            "GAN has a generator and a discriminator that compete with each other.\n",
            {
                "13": "Standard autoencoders are less efficient for high dimensional data.",
                "14": "GAN has a generator and a discriminator that compete with each other.",
            },
        ),
        (
            # A long Q15 essay's OWN internal numbered steps, misreported by
            # the model as a generic structure_map breakdown — must be
            # rejected, not treated as new Q1/Q2 anchors.
            "15. Explain the pipeline.\nFirst we take input, then we process it, then we output it.\n",
            {"1": "we take input", "2": "we process it"},
        ),
    ])
    blueprint_json = _blueprint([
        ("Part-A", [
            ("q1", "1", 1.0, "Autoencoder type?"),
            ("q2", "2", 1.0, "Perceptron layers?"),
        ]),
        ("Part-B", [
            ("q13", "13", 2.0, "Compare standard and sparse autoencoders."),
            ("q14", "14", 2.0, "Explain GANs."),
            ("q15", "15", 2.0, "Explain the pipeline."),
        ]),
    ])

    mapped = _run(ocr_json, blueprint_json)

    assert _by_id(mapped, "q13").mapping_status == "MAPPED"
    assert "less efficient" in _by_id(mapped, "q13").student_answer
    assert _by_id(mapped, "q14").mapping_status == "MAPPED"
    assert "generator and a discriminator" in _by_id(mapped, "q14").student_answer
    # Q13's content must not have bled into Q1/Q2, and vice versa.
    assert "less efficient" not in _by_id(mapped, "q1").student_answer
    assert "less efficient" not in _by_id(mapped, "q2").student_answer


def test_duplicate_blueprint_question_id_deduped_to_one_mapped_answer():
    """
    Regression: a blueprint can give two distinct either/or sub-questions
    (e.g. "19(a)" / "19(b)") the SAME question_id when upstream generation
    fails to disambiguate them. Since a block is looked up by question_id,
    both entries would otherwise receive the identical answer text and
    produce two duplicate mapped rows for one physical answer. Only the
    entry whose question_text best matches the actual answer should come
    out MAPPED; its sibling must come out SKIPPED with no answer, not a
    duplicate of the same text.
    """
    ocr_json = _ocr([
        "Part-D\n"
        "19. Demonstrate a Denoising Autoencoder for image reconstruction.\n"
    ])
    blueprint_json = _blueprint([
        ("Part-D", [
            ("q-q19", "Q19", 10.0, "Demonstrate a Denoising Autoencoder for image reconstruction."),
            ("q-q19", "Q19", 10.0, "Develop a VGG16 based image classification model."),
        ]),
    ])

    mapped = _run(ocr_json, blueprint_json)
    q19_rows = [m for m in mapped if m.question_id == "q-q19"]

    assert len(q19_rows) == 2
    statuses = sorted(m.mapping_status for m in q19_rows)
    assert statuses == ["MAPPED", "SKIPPED"]
    mapped_row = next(m for m in q19_rows if m.mapping_status == "MAPPED")
    skipped_row = next(m for m in q19_rows if m.mapping_status == "SKIPPED")
    assert "Denoising Autoencoder" in mapped_row.student_answer
    assert not skipped_row.student_answer


def test_structure_map_recovers_labels_from_compound_keys():
    """
    Regression: the OCR model sometimes returns a structure_map key with
    question text baked into it too (e.g. "14. GAN" instead of a clean
    "14"), rather than a clean numeric label — real production example:
    a page transcribed with NO inline "14."/"15." labels at all, whose
    structure_map came back as {"14. GAN": "...", "15. Improving
    performance": "..."}. These must not be rejected outright; only their
    leading numeric token should be trusted (validated the normal way
    through _apply_sequence_guard), recovering the real anchor instead of
    losing it.
    """
    ocr_json = _ocr_with_structure_map([
        ("1. contractive autoencoder\n", {"1.": "contractive autoencoder"}),
        (
            # No inline "14."/"15." at all - exactly the production shape.
            "GAN has a generator and a discriminator that compete.\n\n"
            "Segmentation improves performance by separating the image.\n",
            {
                "14. GAN": "GAN has a generator and a discriminator that compete.",
                "15. Improving performance": "Segmentation improves performance by separating the image.",
            },
        ),
    ])
    blueprint_json = _blueprint([
        ("Part-A", [("q1", "1", 1.0, "Autoencoder type?")]),
        ("Part-B", [
            ("q14", "14", 2.0, "Explain GANs."),
            ("q15", "15", 2.0, "How to improve performance?"),
        ]),
    ])

    mapped = _run(ocr_json, blueprint_json)

    assert _by_id(mapped, "q14").mapping_status == "MAPPED"
    assert "generator and a discriminator" in _by_id(mapped, "q14").student_answer
    assert _by_id(mapped, "q15").mapping_status == "MAPPED"
    assert "separating the image" in _by_id(mapped, "q15").student_answer


def test_structure_map_list_value_is_joined_not_repr_dumped():
    """
    Regression: the OCR schema asks for one string per structure_map entry,
    but the model sometimes returns a list of bullet lines instead. Naively
    embedding that (an f-string over a non-str value) produces a literal
    Python repr like "['point one', 'point two']" as if it were real answer
    text — seen verbatim in production. detect_anchors' structure_map
    harvesting must join list values into plain text, not skip them or
    leak their repr.
    """
    ocr_json = _ocr_with_structure_map([
        (
            "Denoising Autoencoder removes noise from images.\n"
            "It is trained on a large noisy dataset.\n",
            {
                "19": [
                    "Denoising Autoencoder removes noise from images.",
                    "It is trained on a large noisy dataset.",
                ]
            },
        ),
    ])
    blueprint_json = _blueprint([
        ("Part-D", [("q19", "19", 10.0, "Explain the denoising autoencoder.")]),
    ])

    mapped = _run(ocr_json, blueprint_json)
    q19 = _by_id(mapped, "q19")

    assert q19.mapping_status == "MAPPED"
    assert "[" not in q19.student_answer
    assert "removes noise from images" in q19.student_answer
