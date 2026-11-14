
import math
import re
from collections import Counter


STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were",
    "what", "how", "why", "when", "where", "who",
    "explain", "describe", "define", "tell", "me",
    "about", "in", "on", "of", "to", "for", "and",
    "or", "do", "does", "can", "could", "would"
}

ALIASES = {
    "dbms": ["database", "management", "system"],
    "normalisation": ["normalization"],
}


def _tokenize(text):
    if not isinstance(text, str):
        return []

    words = re.findall(r"[a-z0-9]+", text.lower())
    tokens = []

    for word in words:
        if word in STOP_WORDS:
            continue

        expanded = ALIASES.get(word, [word])

        for token in expanded:
            if token.endswith("s") and len(token) > 3:
                token = token[:-1]

            if token not in STOP_WORDS:
                tokens.append(token)

    return tokens


def _build_vectors(documents):
    tokenized = [_tokenize(document) for document in documents]
    document_frequency = Counter()

    for tokens in tokenized:
        document_frequency.update(set(tokens))

    total_documents = len(documents)
    vectors = []

    for tokens in tokenized:
        if not tokens:
            vectors.append({})
            continue

        frequencies = Counter(tokens)
        vector = {}

        for word, count in frequencies.items():
            term_frequency = count / len(tokens)

            inverse_document_frequency = (
                math.log(
                    (1 + total_documents) /
                    (1 + document_frequency[word])
                ) + 1
            )

            vector[word] = term_frequency * inverse_document_frequency

        vectors.append(vector)

    return vectors


def _cosine_similarity(vector_a, vector_b):
    if not vector_a or not vector_b:
        return 0.0

    common_words = set(vector_a) & set(vector_b)

    dot_product = sum(
        vector_a[word] * vector_b[word]
        for word in common_words
    )

    magnitude_a = math.sqrt(
        sum(value ** 2 for value in vector_a.values())
    )

    magnitude_b = math.sqrt(
        sum(value ** 2 for value in vector_b.values())
    )

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    similarity = dot_product / (magnitude_a * magnitude_b)

    if math.isclose(
        similarity, 1.0,
        rel_tol=1e-12,
        abs_tol=1e-12
    ):
        return 1.0

    return max(0.0, min(1.0, similarity))


def calculate_similarity(question_a, question_b):
    if not isinstance(question_a, str):
        return 0.0

    if not isinstance(question_b, str):
        return 0.0

    if not question_a.strip() or not question_b.strip():
        return 0.0

    vectors = _build_vectors([question_a, question_b])

    return round(
        _cosine_similarity(vectors[0], vectors[1]),
        4
    )


def find_similar_questions(questions, threshold=0.30):
    if (
        not isinstance(threshold, (int, float))
        or isinstance(threshold, bool)
    ):
        raise ValueError(
            "Threshold must be a number between 0 and 1"
        )

    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError(
            "Threshold must be between 0 and 1"
        )

    if questions is None:
        return []

    if not isinstance(questions, (list, tuple)):
        raise TypeError(
            "Questions must be a list or tuple"
        )

    valid_questions = [
        (index, question)
        for index, question in enumerate(questions)
        if isinstance(question, str) and question.strip()
    ]

    if len(valid_questions) < 2:
        return []

    texts = [question for _, question in valid_questions]
    vectors = _build_vectors(texts)
    matches = []

    for i in range(len(valid_questions)):
        for j in range(i + 1, len(valid_questions)):
            score = _cosine_similarity(vectors[i], vectors[j])

            if score <= 0 or score < threshold:
                continue

            matches.append({
                "question_1": valid_questions[i][1],
                "question_2": valid_questions[j][1],
                "index_1": valid_questions[i][0],
                "index_2": valid_questions[j][0],
                "similarity": round(score, 4),
                "label": "Potentially similar"
            })

    return sorted(
        matches,
        key=lambda item: item["similarity"],
        reverse=True
    )
