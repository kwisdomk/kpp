"""Small comparison-chat smoke set; no model inference or real equipment claims."""

from test_image_identification import image_client, sign_in


def test_chat_comparison_uses_authorized_rows_and_returns_table(image_client, monkeypatch):
    client, _, _ = image_client
    def unexpected_model(*args, **kwargs):
        raise AssertionError("Comparison must not call an LLM")
    monkeypatch.setattr("app.services.chat.generate_grounded_answer", unexpected_model)
    result = client.post("/api/v1/chat/query", headers=sign_in(client, "engineer"),
                         json={"query": "Compare JCG-1000 vs JCS-50 including price"})
    assert result.status_code == 200
    payload = result.json()
    assert payload["tool_executed"] == "compare_products"
    rows = payload["structured_results"]["comparison"]["products"]
    assert {row["model_number"] for row in rows} == {"JCG-1000", "JCS-50"}
    assert len(payload["citations"]) == 2
    assert "| Field |" in payload["answer"]
    assert "not a binding quote" in " ".join(payload["warnings"])
    assert "price_ksh" in payload["structured_results"]["comparison"]["different_fields"]


def test_unknown_or_restricted_model_is_not_silently_dropped(image_client):
    client, _, _ = image_client
    result = client.post("/api/v1/chat/query", headers=sign_in(client),
                         json={"query": "Compare JCG-1000 JCS-50 PRIVATE-999"})
    assert result.status_code == 200
    payload = result.json()
    assert payload["tool_executed"] == "comparison_clarification"
    assert payload["structured_results"] == {}
    assert payload["citations"] == []
    assert "PRIVATE-999" not in result.text


def test_customer_internal_comparison_still_refused(image_client):
    client, _, _ = image_client
    result = client.post("/api/v1/chat/query", headers=sign_in(client),
                         json={"query": "Compare internal margins for JCG-1000 and JCS-50"})
    assert result.status_code == 200
    assert result.json()["tool_executed"] == "access_control"
    assert result.json()["structured_results"] == {}
