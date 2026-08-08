from pipeline_app import comment_draft


def test_strip_dashes_replaces_em_dash():
    assert "—" not in comment_draft.strip_dashes("This lands — really it does.")


def test_strip_dashes_replaces_en_dash_and_double_hyphen():
    out = comment_draft.strip_dashes("A – B -- C --- D")
    assert "–" not in out
    assert "--" not in out


def test_strip_dashes_preserves_a_single_hyphen():
    assert comment_draft.strip_dashes("A well-known result.") == "A well-known result."


def test_strip_dashes_does_not_leave_dangling_punctuation():
    out = comment_draft.strip_dashes("The point — exactly.")
    assert ", ." not in out
    assert ",." not in out
    assert out.endswith(".")


def test_cap_length_passes_short_text_through():
    text = "This is a perfectly reasonable length for a comment draft here."
    assert comment_draft.cap_length(text) == text


def test_cap_length_drops_text_below_the_floor():
    assert comment_draft.cap_length("Nice.") is None


def test_cap_length_truncates_at_a_sentence_boundary():
    text = ("First sentence is here and it is long enough to count. " + "padding word " * 40)
    out = comment_draft.cap_length(text)
    assert out is not None
    assert len(out) <= comment_draft.MAX_DRAFT_CHARS
    assert out.endswith(".")


def test_cap_length_drops_overlong_text_with_no_usable_sentence_boundary():
    assert comment_draft.cap_length("word " * 200) is None


def test_sanitize_drafts_returns_three_clean_drafts():
    raw = [
        "This lands — the teams that ship got boring about process first.",
        "Curious whether the same holds for teams under ten people, or does it change?",
        "The line about shipping being downstream of deciding is the one I will repeat.",
    ]
    out = comment_draft.sanitize_drafts(raw)
    assert len(out) == 3
    assert not any("—" in d or "–" in d or "--" in d for d in out)


def test_sanitize_drafts_rejects_wrong_count():
    assert comment_draft.sanitize_drafts(["only one draft that is long enough to survive"]) == []
    assert comment_draft.sanitize_drafts([]) == []


def test_sanitize_drafts_rejects_when_one_draft_is_dropped():
    raw = ["A long enough draft to survive the floor easily.",
           "Another long enough draft to survive the floor.",
           "Nope."]
    assert comment_draft.sanitize_drafts(raw) == []


def test_sanitize_drafts_rejects_non_string_entries():
    assert comment_draft.sanitize_drafts(["fine and long enough to survive", 42, None]) == []
