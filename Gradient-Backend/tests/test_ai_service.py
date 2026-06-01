import json
import os
import types


def _install_fake_openai_client(ai_service_module, base_json_obj, final_json_obj):
    """Monkeypatch ai_service_module.client.chat.completions.create with a 2-call queue."""

    class _FakeChatCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if kwargs.get("response_format") != {"type": "json_object"}:
                raise AssertionError("Expected response_format=json_object in all calls")

            payload = base_json_obj if self.calls == 1 else final_json_obj
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(content=json.dumps(payload))
                    )
                ]
            )

    fake = _FakeChatCompletions()
    ai_service_module.client.chat.completions = fake
    return fake


def test_analyze_email_without_company_search(monkeypatch):
    # Disable search and ensure we still get valid JSON back.
    monkeypatch.setenv("COMPANY_SEARCH_ENABLED", "false")

    import importlib
    import service.aiService as ai_service

    importlib.reload(ai_service)

    base_json_obj = {"company": None, "website": None}
    final_json_obj = {
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "full_name": "John Doe",
        "company": None,
        "company_summary": None,
        "order_number": None,
        "order_description": None,
        "amount": None,
        "currency": None,
        "phone_number": None,
        "website": None,
        "person_role": "Sales Manager",
        "person_location": "Kyiv, Ukraine",
        "person_experience": "5+ years",
        "person_summary": "John Doe — sales manager.",
    }

    _install_fake_openai_client(ai_service, base_json_obj, final_json_obj)

    out = ai_service.analyze_email(subject="Hi", body="Hello", sender="john@example.com")
    assert out["full_name"] == "John Doe"
    assert out["company_summary"] is None


def test_analyze_email_with_tool_call(monkeypatch):
    monkeypatch.setenv("COMPANY_SEARCH_ENABLED", "true")

    import importlib
    import service.aiService as ai_service

    importlib.reload(ai_service)

    base_json_obj = {
        "email": "hr@softserve.com",
        "full_name": "Ivan",
        "company": "SoftServe",
        "website": None,
    }
    final_json_obj = {
        "email": "hr@softserve.com",
        "first_name": "Ivan",
        "last_name": None,
        "full_name": "Ivan",
        "company": "SoftServe",
        "company_summary": "IT services company.",
        "order_number": None,
        "order_description": None,
        "amount": None,
        "currency": None,
        "phone_number": None,
        "website": "https://www.softserveinc.com",
        "person_role": "HR Manager",
        "person_location": "Lviv, Ukraine",
        "person_experience": "Senior level",
        "person_summary": "Ivan — HR manager у SoftServe.",
    }

    # Avoid real network enrichment
    monkeypatch.setattr(ai_service, "search_company_tool", lambda name: "SoftServe overview")
    monkeypatch.setattr(ai_service, "fetch_website_tool", lambda url: "Title: SoftServe")

    _install_fake_openai_client(ai_service, base_json_obj, final_json_obj)

    out = ai_service.analyze_email(subject="Hello", body="", sender="hr@softserve.com")
    assert out["company"] == "SoftServe"
    assert out["company_summary"] == "IT services company."


def test_company_candidate_from_domain(monkeypatch):
    monkeypatch.setenv("COMPANY_SEARCH_ENABLED", "false")

    import importlib
    import service.aiService as ai_service

    importlib.reload(ai_service)

    assert ai_service._company_candidate_from_sender_email("a@nova-poshta.ua") == "Nova Poshta"
    assert ai_service._company_candidate_from_sender_email("a@gmail.com") is None


def test_dedupe_text_removes_repeated_paragraph():
    import service.aiService as ai_service

    text = "Same paragraph. Same paragraph."
    assert ai_service._dedupe_text(text) == "Same paragraph."


def test_finalize_lead_analysis_fills_missing_role_from_search():
    import service.aiService as ai_service

    result = ai_service._finalize_lead_analysis(
        {
            "full_name": "Daniel Moore",
            "company": "Microsoft",
            "person_summary": "Daniel Moore is a partner. Daniel Moore is a partner.",
        },
        sender="daniel@example.com",
        company_candidate="Microsoft",
        person_insights=[
            {
                "title": "Daniel Moore - Managing Partner at Microsoft | LinkedIn",
                "snippet": "15+ years in enterprise technology",
                "url": "https://linkedin.com/in/daniel",
            }
        ],
        company_insights=[],
    )

    assert result["person_role"] == "Managing Partner"
    assert result["person_experience"] == "15+ years"
    assert "Daniel Moore is a partner." in (result["person_summary"] or "")
    assert (result["person_summary"] or "").count("Daniel Moore is a partner.") == 1
