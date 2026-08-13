"""Offline unit tests for mybk_planner.analysis (pure functions, no I/O).

GPA feed rows mimic the live tinChiTichLuy payload:
    {"mahk": "20231", "tbtlchunghe10": "6.5", "tbtlchunghe4": "2.0",
     "tinchi": "13"}
``tinchi`` is CUMULATIVE; per-semester load is the delta between rows.
"""

from types import SimpleNamespace

from mybk_planner import analysis


def _gpa_rows():
    """Three real semesters, cumulative credits 13 -> 26.1 -> 40."""
    return [
        {"mahk": "20231", "tbtlchunghe10": "6.5", "tbtlchunghe4": "2.0",
         "tinchi": "13"},
        {"mahk": "20232", "tbtlchunghe10": "7.2", "tbtlchunghe4": "2.7",
         "tinchi": "26.1"},
        {"mahk": "20233", "tbtlchunghe10": "7.8", "tbtlchunghe4": "3.0",
         "tinchi": "40"},
    ]


def _record(code, passed, letter, semester, name=None, credits=3,
            score_10=5.0):
    return SimpleNamespace(
        subject_code=code, passed=passed, letter=letter,
        subject_name=name or f"Course {code}", credits=credits,
        score_10=score_10, semester=semester,
    )


class TestGpaTrend:
    def test_up_trend(self):
        result = analysis.gpa_trend(_gpa_rows())
        assert result["direction"] == "up"
        assert result["delta"] == 1.3
        assert result["recent_delta"] == 0.6
        assert result["current_gpa_10"] == 7.8
        assert result["current_gpa_4"] == 3.0
        assert [s["hk"] for s in result["semesters"]] == [
            "20231", "20232", "20233"]

    def test_down_trend(self):
        rows = [
            {"mahk": "20231", "tbtlchunghe10": "8.0", "tbtlchunghe4": "3.4",
             "tinchi": "15"},
            {"mahk": "20232", "tbtlchunghe10": "7.0", "tbtlchunghe4": "2.6",
             "tinchi": "30"},
        ]
        result = analysis.gpa_trend(rows)
        assert result["direction"] == "down"
        assert result["delta"] == -1.0

    def test_flat_trend(self):
        rows = [
            {"mahk": "20231", "tbtlchunghe10": "7.0", "tbtlchunghe4": "2.7",
             "tinchi": "15"},
            {"mahk": "20232", "tbtlchunghe10": "7.02", "tbtlchunghe4": "2.7",
             "tinchi": "30"},
        ]
        assert analysis.gpa_trend(rows)["direction"] == "flat"

    def test_empty_input_is_unknown(self):
        result = analysis.gpa_trend([])
        assert result["direction"] == "unknown"
        assert result["semesters"] == []
        assert result["current_gpa_10"] is None
        assert result["current_gpa_4"] is None
        assert result["delta"] == 0.0
        assert result["recent_delta"] == 0.0

    def test_non_list_input_is_unknown(self):
        assert analysis.gpa_trend(None)["direction"] == "unknown"

    def test_placeholder_semesters_are_filtered(self):
        rows = [
            {"mahk": "BL", "tbtlchunghe10": "9.9", "tbtlchunghe4": "4.0",
             "tinchi": "0"},
            {"mahk": "99991", "tbtlchunghe10": "9.9", "tbtlchunghe4": "4.0",
             "tinchi": "0"},
            {"mahk": "20231", "tbtlchunghe10": "6.5", "tbtlchunghe4": "2.0",
             "tinchi": "13"},
        ]
        result = analysis.gpa_trend(rows)
        assert [s["hk"] for s in result["semesters"]] == ["20231"]
        assert result["current_gpa_10"] == 6.5

    def test_rows_without_valid_gpa10_are_filtered(self):
        rows = [
            {"mahk": "20231", "tbtlchunghe10": "--", "tbtlchunghe4": "2.0",
             "tinchi": "13"},
            {"mahk": "20232", "tbtlchunghe10": "", "tbtlchunghe4": "2.0",
             "tinchi": "13"},
            {"mahk": "20233", "tbtlchunghe10": None, "tbtlchunghe4": "2.0",
             "tinchi": "13"},
            {"mahk": "20241", "tbtlchunghe10": "7.1", "tbtlchunghe4": "2.8",
             "tinchi": "30"},
        ]
        result = analysis.gpa_trend(rows)
        assert [s["hk"] for s in result["semesters"]] == ["20241"]

    def test_rows_with_missing_mahk_are_filtered(self):
        rows = [
            {"mahk": "", "tbtlchunghe10": "7.0"},
            {"tbtlchunghe10": "7.0"},
            {"mahk": "20231", "tbtlchunghe10": "7.0"},
        ]
        result = analysis.gpa_trend(rows)
        assert [s["hk"] for s in result["semesters"]] == ["20231"]

    def test_single_semester_has_zero_recent_delta(self):
        rows = [{"mahk": "20231", "tbtlchunghe10": "7.0",
                 "tbtlchunghe4": "2.7", "tinchi": "15"}]
        result = analysis.gpa_trend(rows)
        assert result["delta"] == 0.0
        assert result["recent_delta"] == 0.0
        assert result["direction"] == "flat"


class TestCompletion:
    def test_normal_case(self):
        result = analysis.completion(105, 23)
        assert result["percent"] == 82.0
        assert result["total"] == 128
        assert result["remaining"] == 23

    def test_zero_total_guard(self):
        result = analysis.completion(0, 0)
        assert result["percent"] == 100.0
        assert result["total"] == 0

    def test_half_done(self):
        assert analysis.completion(50, 50)["percent"] == 50.0

    def test_nothing_left(self):
        result = analysis.completion(128, 0)
        assert result["percent"] == 100.0
        assert result["remaining"] == 0


class TestKhoiCompliance:
    def test_met_and_unmet_blocks(self):
        progress = [
            {"khối": "Toán", "tc_required": 13.0, "tc_done": 15.0},
            {"khối": "Chuyên ngành", "tc_required": 30.0, "tc_done": 21.0},
        ]
        result = analysis.khoi_compliance(progress)
        assert len(result) == 2
        assert result[0]["khoi"] == "Toán"
        assert result[0]["met"] is True
        assert result[0]["gap"] == 0.0
        assert result[1]["met"] is False
        assert result[1]["gap"] == 9.0

    def test_exactly_required_is_met(self):
        result = analysis.khoi_compliance(
            [{"khối": "X", "tc_required": 10.0, "tc_done": 10.0}])
        assert result[0]["met"] is True

    def test_empty_and_malformed_input(self):
        assert analysis.khoi_compliance([]) == []
        assert analysis.khoi_compliance(None) == []
        assert analysis.khoi_compliance(["junk", None]) == []

    def test_missing_numbers_default_to_zero(self):
        result = analysis.khoi_compliance([{"khối": "Y"}])
        assert result[0]["required"] == 0.0
        assert result[0]["done"] == 0.0
        assert result[0]["met"] is True


class TestGradeHealth:
    def test_retake_pass_clears_older_fail(self):
        records = [
            _record("MT1003", passed=False, letter="F", semester="20231",
                    score_10=3.0),
            _record("MT1003", passed=True, letter="D+", semester="20233",
                    score_10=5.5),
        ]
        result = analysis.grade_health(records)
        assert result["failed"] == []
        assert [c["code"] for c in result["d_courses"]] == ["MT1003"]

    def test_latest_record_is_authoritative_for_letters(self):
        records = [
            _record("MT1003", passed=True, letter="A", semester="20231"),
            _record("MT1003", passed=False, letter="F", semester="20232"),
        ]
        result = analysis.grade_health(records)
        assert [c["code"] for c in result["failed"]] == ["MT1003"]
        assert result["letters"].get("F") == 1
        assert "A" not in result["letters"]

    def test_d_and_dplus_passed_go_to_d_courses(self):
        records = [
            _record("A", passed=True, letter="D", semester="20231",
                    score_10=5.0),
            _record("B", passed=True, letter="D+", semester="20231",
                    score_10=5.5),
            _record("C", passed=True, letter="C", semester="20231",
                    score_10=6.5),
        ]
        result = analysis.grade_health(records)
        assert sorted(c["code"] for c in result["d_courses"]) == ["A", "B"]
        assert result["failed"] == []

    def test_letter_buckets_normalize_dplus_and_count_other(self):
        records = [
            _record("C1", passed=True, letter="A", semester="20231"),
            _record("C2", passed=True, letter="B", semester="20231"),
            _record("C3", passed=True, letter="C", semester="20231"),
            _record("C4", passed=True, letter="D+", semester="20231"),
            _record("C5", passed=False, letter="F", semester="20231"),
            _record("C6", passed=True, letter="Đạt", semester="20231"),
            _record("C7", passed=True, letter="X", semester="20231"),
            _record("C8", passed=True, letter="7.5", semester="20231"),
        ]
        letters = analysis.grade_health(records)["letters"]
        assert letters == {"A": 1, "B": 1, "C": 1, "D": 1, "F": 1,
                           "other": 3}

    def test_unlisted_plus_letters_fall_into_other(self):
        records = [_record("C1", passed=True, letter="B+", semester="20231")]
        assert analysis.grade_health(records)["letters"] == {"other": 1}

    def test_d_courses_and_letters_are_consistent(self):
        # A passed D+ course counts as D in letters AND appears in d_courses.
        records = [
            _record("C4", passed=True, letter="D+", semester="20231"),
            _record("C8", passed=True, letter="D", semester="20232"),
        ]
        result = analysis.grade_health(records)
        assert result["letters"]["D"] == len(result["d_courses"]) == 2

    def test_failed_entry_carries_course_metadata(self):
        records = [
            _record("MT1003", passed=False, letter="F", semester="20231",
                    name="Giải tích 1", credits=4, score_10=3.2),
        ]
        failed = analysis.grade_health(records)["failed"]
        assert failed == [{"code": "MT1003", "name": "Giải tích 1",
                           "credits": 4, "semester": "20231"}]

    def test_empty_records(self):
        result = analysis.grade_health([])
        assert result == {"failed": [], "d_courses": [], "letters": {}}

    def test_records_without_code_are_skipped(self):
        records = [
            _record("", passed=False, letter="F", semester="20231"),
            _record(None, passed=False, letter="F", semester="20231"),
        ]
        assert analysis.grade_health(records)["failed"] == []


class TestTimeline:
    def test_at_max_and_at_pace(self):
        # Cumulative 13.1 -> 26.2 gives a steady 13.1 TC/semester pace.
        rows = [
            {"mahk": "20231", "tbtlchunghe10": "7.0", "tinchi": "13.1"},
            {"mahk": "20232", "tbtlchunghe10": "7.0", "tinchi": "26.2"},
        ]
        result = analysis.timeline(23, 18, rows)
        assert result["at_max"] == 2  # ceil(23 / 18)
        assert result["avg_credits_per_sem"] == 13.1
        assert result["at_pace"] == 2  # ceil(23 / 13.1)

    def test_exact_division(self):
        rows = [{"mahk": "20231", "tbtlchunghe10": "7.0", "tinchi": "10"}]
        assert analysis.timeline(36, 18, rows)["at_max"] == 2

    def test_zero_remaining_needs_no_semesters(self):
        rows = [{"mahk": "20231", "tbtlchunghe10": "7.0", "tinchi": "10"}]
        result = analysis.timeline(0, 18, rows)
        assert result["at_max"] == 0
        assert result["at_pace"] == 0

    def test_zero_max_tc_guard(self):
        rows = [{"mahk": "20231", "tbtlchunghe10": "7.0", "tinchi": "10"}]
        assert analysis.timeline(23, 0, rows)["at_max"] == 0

    def test_empty_gpa_rows_gives_no_pace(self):
        result = analysis.timeline(23, 18, [])
        assert result["at_max"] == 2
        assert result["at_pace"] is None
        assert result["avg_credits_per_sem"] is None

    def test_placeholder_rows_do_not_count_toward_pace(self):
        rows = [
            {"mahk": "BL", "tbtlchunghe10": "9.9", "tinchi": "50"},
            {"mahk": "20231", "tbtlchunghe10": "7.0", "tinchi": "12"},
        ]
        result = analysis.timeline(23, 18, rows)
        assert result["avg_credits_per_sem"] == 12.0


class TestNextSemesterLabel:
    def test_regular_increment(self):
        sems = analysis.gpa_trend(_gpa_rows())["semesters"]
        assert analysis.next_semester_label(sems) == "HK 20241"

    def test_mid_year_increment(self):
        sems = [{"hk": "20252"}]
        assert analysis.next_semester_label(sems) == "HK 20253"

    def test_third_semester_rolls_over_to_next_year(self):
        assert analysis.next_semester_label([{"hk": "20253"}]) == "HK 20261"

    def test_empty_falls_back_to_generic_label(self):
        assert analysis.next_semester_label([]) == "HK tới"

    def test_malformed_code_falls_back(self):
        assert analysis.next_semester_label([{"hk": "ABC"}]) == "HK tới"
        assert analysis.next_semester_label([{}]) == "HK tới"
