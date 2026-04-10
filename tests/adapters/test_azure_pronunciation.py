"""Tests for Azure Pronunciation adapter — difflib miscue detection logic."""

from parla.adapters.azure_pronunciation import _apply_difflib_miscue


class TestApplyDifflibMiscue:
    def test_perfect_match(self) -> None:
        ref = ["hello", "world"]
        rec = [
            {
                "word": "hello",
                "accuracy_score": 95.0,
                "error_type": "None",
                "offset_seconds": 0.0,
                "duration_seconds": 0.3,
            },
            {
                "word": "world",
                "accuracy_score": 90.0,
                "error_type": "None",
                "offset_seconds": 0.4,
                "duration_seconds": 0.3,
            },
        ]
        result = _apply_difflib_miscue(ref, rec)

        assert len(result) == 2
        assert result[0].word == "hello"
        assert result[0].accuracy_score == 95.0
        assert result[0].error_type == "None"
        assert result[1].word == "world"

    def test_omission_detected(self) -> None:
        ref = ["the", "cat", "sat"]
        rec = [
            {
                "word": "the",
                "accuracy_score": 95.0,
                "error_type": "None",
                "offset_seconds": 0.0,
                "duration_seconds": 0.2,
            },
            {
                "word": "sat",
                "accuracy_score": 90.0,
                "error_type": "None",
                "offset_seconds": 0.3,
                "duration_seconds": 0.2,
            },
        ]
        result = _apply_difflib_miscue(ref, rec)

        words_map = {w.word: w.error_type for w in result}
        assert words_map["cat"] == "Omission"
        assert words_map["the"] == "None"
        assert words_map["sat"] == "None"

    def test_insertion_detected(self) -> None:
        ref = ["the", "cat"]
        rec = [
            {
                "word": "the",
                "accuracy_score": 95.0,
                "error_type": "None",
                "offset_seconds": 0.0,
                "duration_seconds": 0.2,
            },
            {
                "word": "big",
                "accuracy_score": 80.0,
                "error_type": "None",
                "offset_seconds": 0.2,
                "duration_seconds": 0.2,
            },
            {
                "word": "cat",
                "accuracy_score": 90.0,
                "error_type": "None",
                "offset_seconds": 0.4,
                "duration_seconds": 0.2,
            },
        ]
        result = _apply_difflib_miscue(ref, rec)

        types = [(w.word, w.error_type) for w in result]
        assert ("the", "None") in types
        assert ("cat", "None") in types
        assert ("big", "Insertion") in types

    def test_replacement_produces_omission_and_insertion(self) -> None:
        ref = ["hello", "world"]
        rec = [
            {
                "word": "hello",
                "accuracy_score": 95.0,
                "error_type": "None",
                "offset_seconds": 0.0,
                "duration_seconds": 0.3,
            },
            {
                "word": "earth",
                "accuracy_score": 50.0,
                "error_type": "None",
                "offset_seconds": 0.4,
                "duration_seconds": 0.3,
            },
        ]
        result = _apply_difflib_miscue(ref, rec)

        types = {w.word: w.error_type for w in result}
        assert types["hello"] == "None"
        assert types["world"] == "Omission"
        assert types["earth"] == "Insertion"

    def test_empty_recognized(self) -> None:
        ref = ["hello", "world"]
        rec: list[dict] = []
        result = _apply_difflib_miscue(ref, rec)

        assert len(result) == 2
        assert all(w.error_type == "Omission" for w in result)

    def test_omission_has_negative_offset(self) -> None:
        ref = ["the", "cat"]
        rec = [
            {
                "word": "the",
                "accuracy_score": 95.0,
                "error_type": "None",
                "offset_seconds": 0.0,
                "duration_seconds": 0.2,
            },
        ]
        result = _apply_difflib_miscue(ref, rec)

        omissions = [w for w in result if w.error_type == "Omission"]
        assert len(omissions) == 1
        assert omissions[0].offset_seconds == -1.0

    def test_case_insensitive_matching(self) -> None:
        ref = ["Hello", "World"]
        rec = [
            {
                "word": "hello",
                "accuracy_score": 95.0,
                "error_type": "None",
                "offset_seconds": 0.0,
                "duration_seconds": 0.3,
            },
            {
                "word": "world",
                "accuracy_score": 90.0,
                "error_type": "None",
                "offset_seconds": 0.4,
                "duration_seconds": 0.3,
            },
        ]
        result = _apply_difflib_miscue(ref, rec)

        assert len(result) == 2
        # Preserves reference casing
        assert result[0].word == "Hello"
        assert result[1].word == "World"
