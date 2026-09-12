import time

import agents.analyst_agent as analyst_agent
from agents.analyst_agent import analyze_evidence, assess_evidence_stance
from models.evidence import Evidence
from models.schemas import Stance


def make_evidence(title: str, snippet: str, credibility: float = 0.8) -> Evidence:
    return Evidence(
        title=title,
        url="https://example.com/source",
        snippet=snippet,
        source="Example",
        query="example query",
        domain="example.com",
        credibility_score=credibility,
    )


def test_direct_term_overlap_supports_simple_factual_claim():
    assessments = assess_evidence_stance(
        "Water freezes at 0 degrees Celsius at standard pressure.",
        [
            make_evidence(
                "Freezing point",
                (
                    "The temperature at which a liquid freezes is known as the "
                    "freezing point. The best-known freezing point is that of "
                    "water at 32 degrees Fahrenheit or 0 degrees Celsius."
                ),
            )
        ],
    )

    assert assessments[0].stance is Stance.SUPPORTS
    assert assessments[0].relevance_score >= 0.5
    assert "0 degrees Celsius" in assessments[0].relevant_passage


def test_freezing_value_mismatch_refutes_claim():
    assessments = assess_evidence_stance(
        "Water freezes at 100 degrees Celsius at standard pressure.",
        [
            make_evidence(
                "Water phase changes",
                "Water boils at 100 degrees Celsius and freezes at 0 degrees Celsius at standard pressure.",
            )
        ],
    )

    assert assessments[0].stance is Stance.REFUTES


def test_boiling_value_does_not_support_freezing_value_claim():
    assessments = assess_evidence_stance(
        "Water freezes at 100 degrees Celsius at standard pressure.",
        [
            make_evidence(
                "Boiling point",
                "Water boils at 100 degrees Celsius under standard pressure.",
            )
        ],
    )

    assert assessments[0].stance is Stance.NEUTRAL


def test_explicit_refutation_language_refutes_relevant_claim():
    assessments = assess_evidence_stance(
        "The city launched the program in 2026.",
        [
            make_evidence(
                "Program launch fact check",
                "The claim is false: city records show the program launched in 2024, not 2026.",
            )
        ],
    )

    assert assessments[0].stance is Stance.REFUTES


def test_location_mismatch_refutes_located_in_claim():
    assessments = assess_evidence_stance(
        "The Eiffel Tower is located in Berlin, Germany.",
        [
            make_evidence(
                "Eiffel Tower location",
                "The Eiffel Tower is a wrought-iron tower located in Paris, France.",
            )
        ],
    )

    assert assessments[0].stance is Stance.REFUTES


def test_location_route_result_does_not_support_located_in_claim():
    assessments = assess_evidence_stance(
        "The Eiffel Tower is located in Berlin, Germany.",
        [
            make_evidence(
                "Berlin to Eiffel Tower",
                "What companies run services between Berlin, Germany and Eiffel Tower, France?",
            )
        ],
    )

    assert assessments[0].stance is Stance.NEUTRAL


def test_bare_not_in_nuanced_science_passage_does_not_force_refutation():
    assessments = assess_evidence_stance(
        "Water freezes at 0 degrees Celsius at standard pressure.",
        [
            make_evidence(
                "Physics lecture",
                (
                    "At standard pressure, water begins to freeze very close to "
                    "0 degrees Celsius. If pressure is increased greatly, water "
                    "will not begin to freeze until colder temperatures."
                ),
            )
        ],
    )

    assert assessments[0].stance is Stance.SUPPORTS


def test_special_case_caveat_stays_neutral():
    assessments = assess_evidence_stance(
        "Water freezes at 0 degrees Celsius at standard pressure.",
        [
            make_evidence(
                "Can water stay liquid below zero degrees Celsius?",
                (
                    "At standard pressure, pure water can be supercooled to "
                    "as low as about -40 degrees Celsius."
                ),
            )
        ],
    )

    assert assessments[0].stance is Stance.NEUTRAL
    assert "special case" in assessments[0].explanation


def test_mixed_pressure_caveat_snippet_stays_neutral():
    assessments = assess_evidence_stance(
        "Water freezes at 0 degrees Celsius at standard pressure.",
        [
            make_evidence(
                "Freezing point of water",
                (
                    "The temperature at which water will begin to freeze is "
                    "0.01 degrees centigrade. If we increase the pressure, "
                    "water will begin to freeze at even colder temperatures."
                ),
            )
        ],
    )

    assert assessments[0].stance is Stance.NEUTRAL


class FakeGeminiResponse:
    def __init__(self, text: str):
        self.text = text


class FakeGeminiModels:
    def __init__(self, text: str | None = None, error: Exception | None = None, delay: float = 0):
        self.text = text
        self.error = error
        self.delay = delay
        self.last_config = None

    def generate_content(self, **kwargs):
        self.last_config = kwargs["config"]
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return FakeGeminiResponse(self.text or "")


class FakeGeminiClient:
    def __init__(self, models: FakeGeminiModels):
        self.models = models


def test_analyze_evidence_uses_mocked_gemini_json(monkeypatch):
    models = FakeGeminiModels(
        '{"verdict":"SUPPORTED","confidence":82,"explanation":"The source directly confirms the claim."}'
    )
    monkeypatch.setattr(analyst_agent, "gemini_client", FakeGeminiClient(models))

    result = analyze_evidence(
        "Water freezes at 0 degrees Celsius at standard pressure.",
        [
            make_evidence(
                "Freezing point",
                "Water freezes at 0 degrees Celsius at standard atmospheric pressure.",
            )
        ],
    )

    assert result.verdict == "SUPPORTED"
    assert result.confidence == 82
    assert result.explanation == "The source directly confirms the claim."
    assert models.last_config["response_mime_type"] == "application/json"
    assert models.last_config["response_schema"]["required"] == ["verdict", "confidence", "explanation"]


def test_invalid_gemini_json_falls_back_without_crashing(monkeypatch):
    monkeypatch.setattr(
        analyst_agent,
        "gemini_client",
        FakeGeminiClient(FakeGeminiModels("not json")),
    )

    result = analyze_evidence(
        "Water freezes at 0 degrees Celsius at standard pressure.",
        [
            make_evidence(
                "Freezing point",
                "Water freezes at 0 degrees Celsius at standard atmospheric pressure.",
            )
        ],
    )

    assert result.verdict == "SUPPORTED"
    assert result.confidence > 0
    assert "automated synthesis is unavailable" not in result.explanation


def test_gemini_error_falls_back_without_crashing(monkeypatch):
    monkeypatch.setattr(
        analyst_agent,
        "gemini_client",
        FakeGeminiClient(FakeGeminiModels(error=RuntimeError("provider exploded"))),
    )

    result = analyze_evidence(
        "The city launched the program in 2026.",
        [
            make_evidence(
                "Program launch fact check",
                "The claim is false: city records show the program launched in 2024, not 2026.",
            )
        ],
    )

    assert result.verdict == "REFUTED"
    assert result.confidence > 0


def test_gemini_timeout_falls_back_without_crashing(monkeypatch):
    monkeypatch.setattr(analyst_agent, "gemini_timeout_seconds", 0.01)
    monkeypatch.setattr(
        analyst_agent,
        "gemini_client",
        FakeGeminiClient(FakeGeminiModels('{"verdict":"SUPPORTED"}', delay=0.2)),
    )

    result = analyze_evidence(
        "Water freezes at 0 degrees Celsius at standard pressure.",
        [
            make_evidence(
                "Freezing point",
                "Water freezes at 0 degrees Celsius at standard atmospheric pressure.",
            )
        ],
    )

    assert result.verdict == "SUPPORTED"
    assert result.confidence > 0


class FakeProvider:
    def __init__(self, name, payload=None, error=None, configured=True):
        self.name = name
        self.payload = payload
        self.error = error
        self.configured = configured
        self.called = False

    def available(self):
        return self.configured

    def generate_json(self, prompt):
        self.called = True
        if self.error:
            raise self.error
        return self.payload


def test_configured_provider_fallback_records_provider_used(monkeypatch):
    primary = FakeProvider("primary", error=RuntimeError("timeout"))
    fallback = FakeProvider(
        "fallback",
        {
            "verdict": "SUPPORTED",
            "confidence": 71,
            "explanation": "The fallback provider returned valid structured JSON.",
        },
    )

    monkeypatch.setattr(analyst_agent, "_configured_providers", lambda: [primary, fallback])

    result = analyze_evidence(
        "Water freezes at 0 degrees Celsius at standard pressure.",
        [
            make_evidence(
                "Freezing point",
                "Water freezes at 0 degrees Celsius at standard atmospheric pressure.",
            )
        ],
    )

    assert primary.called is True
    assert fallback.called is True
    assert result.verdict == "SUPPORTED"
    assert result.provider_used == "fallback"
    assert result.provider_failures == ["primary: RuntimeError"]
