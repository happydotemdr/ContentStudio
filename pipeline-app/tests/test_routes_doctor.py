def test_doctor_page_renders_without_real_claude_installed(client):
    resp = client.get("/doctor")
    assert resp.status_code == 200
    assert "Claude CLI" in resp.text
