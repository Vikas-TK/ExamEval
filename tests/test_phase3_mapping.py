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

from app.phase3.anchor_detector import _normalize_label, detect_anchors
from app.phase3.mapper import _extract_blueprint_questions, map_answers_to_blueprint
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

    assert "sparse Autoencoder" in q1.student_answer
    assert "True" in q2.student_answer
    assert "Standard Autoencoders" in q13.student_answer
    assert "GAN has two networks" in q14.student_answer
    assert "Named Entity Recognition" in q17.student_answer
    assert "Denoising encoder" in q19a.student_answer

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
