import pytest

from services.interview_similarity import (
    calculate_similarity,
    find_similar_questions,
)


def test_similar_dbms_normalization_questions():
    question1 = "Explain normalization in DBMS."
    question2 = "What is database normalization?"

    score = calculate_similarity(question1, question2)

    assert 0 <= score <= 1
    assert score > 0


def test_identical_questions_have_full_similarity():
    question = "What is Python programming?"

    score = calculate_similarity(question, question)

    assert score == 1.0


def test_unrelated_questions_have_low_similarity():
    score = calculate_similarity(
        "Explain database normalization",
        "Describe the process of photosynthesis"
    )

    assert score < 0.30


def test_empty_questions_return_zero():
    assert calculate_similarity("", "Explain DBMS") == 0.0
    assert calculate_similarity("Explain DBMS", "") == 0.0
    assert calculate_similarity("", "") == 0.0


def test_invalid_question_types_return_zero():
    assert calculate_similarity(None, "Explain DBMS") == 0.0
    assert calculate_similarity("Explain DBMS", None) == 0.0


def test_find_similar_questions_returns_potential_matches():
    questions = [
        "What is database normalization?",
        "Explain normalization in DBMS.",
        "What is Python programming?",
    ]

    matches = find_similar_questions(questions, threshold=0.30)

    assert any(
        match["index_1"] == 0 and match["index_2"] == 1
        for match in matches
    )

    for match in matches:
        assert match["label"] == "Potentially similar"
        assert 0 <= match["similarity"] <= 1
        assert match["index_1"] < match["index_2"]


def test_blank_questions_are_ignored():
    questions = [
        "",
        "   ",
        "Explain database normalization",
    ]

    assert find_similar_questions(questions) == []


def test_single_question_returns_no_matches():
    assert find_similar_questions(["Explain DBMS"]) == []


def test_invalid_threshold_is_rejected():
    with pytest.raises(ValueError):
        find_similar_questions(["Question one", "Question two"], -0.1)

    with pytest.raises(ValueError):
        find_similar_questions(["Question one", "Question two"], 1.1)


def test_boolean_threshold_is_rejected():
    with pytest.raises(ValueError):
        find_similar_questions(["Question one", "Question two"], True)


def test_invalid_question_collection_is_rejected():
    with pytest.raises(TypeError):
        find_similar_questions("This is not a question list")


def test_questions_containing_only_stop_words_return_zero():
    assert calculate_similarity("What is this?", "How are you?") == 0.0


def test_stop_word_only_questions_do_not_crash_similarity_search():
    matches = find_similar_questions(
        ["What is this?", "How are you?", "Explain DBMS"]
    )

    assert isinstance(matches, list)