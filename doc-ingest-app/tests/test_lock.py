import getpass
import subprocess
import uuid

import pytest

from doc_ingest import lock


def _fresh_target(lock_test_dir):
    # A unique filename per test run -- an already-locked leftover from a
    # prior run must never collide with this run's fixture.
    return lock_test_dir / f"locked-{uuid.uuid4().hex}.md"


def _stub_icacls(monkeypatch, stdout: str) -> None:
    """Feeds verify_locked a synthetic icacls transcript. Deliberately NOT a
    real lock: every real lock leaves a permanently undeletable fixture behind
    (see conftest's lock_test_dir docstring), and the two cases below are
    about how the OUTPUT is parsed, not about whether icacls works."""
    def _fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(lock.subprocess, "run", _fake_run)
    monkeypatch.setattr(lock.os, "access", lambda p, mode: False)


def test_verify_locked_is_not_fooled_by_owner_rights_and_deny_text_in_a_filename(tmp_path, monkeypatch):
    """verify_locked is the ONLY automated confirmation the OS-level lock
    landed, so a false positive silently reports an unprotected file as
    locked. The converted filename comes from a user-controlled Drive title,
    so "Owner Rights (deny)" is constructible. The previous defence stripped
    the echoed path prefix, which required str(path) to byte-match icacls's
    own output -- a non-ASCII filename can decode differently under an
    OEM-vs-ANSI codepage mismatch, the strip silently no-ops, and the check
    fails OPEN. Here the echoed path deliberately does NOT match str(path)."""
    target = tmp_path / "Owner Rights (deny) notes \u2019v2\u2019.md"
    target.write_text("content", encoding="utf-8")
    _stub_icacls(
        monkeypatch,
        "C:\\out\\Owner Rights (deny) notes ?v2?.md BUILTIN\\Users:(I)(F)\n"
        "                                          NT AUTHORITY\\SYSTEM:(I)(F)\n"
        "\nSuccessfully processed 1 files; Failed processing 0 files\n",
    )
    assert lock.verify_locked(target) is False


def test_verify_locked_finds_a_real_ace_when_the_echoed_path_does_not_byte_match(tmp_path, monkeypatch):
    """The other half of the same fix: a genuine ACE must still be recognised
    when the prefix strip would have failed. ':' can never appear in a name
    this pipeline creates (naming.FORBIDDEN_CHARS strips it), so the
    contiguous "<trustee>:(DENY)" form is unambiguous no matter what the path
    echo decoded to."""
    target = tmp_path / "d\u2019accord \u2014 se\u0301ance.md"
    target.write_text("content", encoding="utf-8")
    _stub_icacls(
        monkeypatch,
        "C:\\out\\d?accord ? se?ance.md OWNER RIGHTS:(DENY)(DE,WDAC,WO,WA,WEA,WD)\n"
        "                              BUILTIN\\Users:(I)(F)\n",
    )
    assert lock.verify_locked(target) is True


def test_verify_locked_accepts_the_raw_sid_form_of_the_ace(tmp_path, monkeypatch):
    """Some Windows builds print the raw S-1-3-4 SID instead of resolving it
    to the "OWNER RIGHTS" display name; both must count."""
    target = tmp_path / "doc.md"
    target.write_text("content", encoding="utf-8")
    _stub_icacls(monkeypatch, "C:\\out\\doc.md S-1-3-4:(DENY)(DE,WDAC,WO,WA,WEA,WD)\n")
    assert lock.verify_locked(target) is True


@pytest.mark.allow_subprocess
def test_apply_readonly_lock_denies_a_real_write(lock_test_dir):
    target = _fresh_target(lock_test_dir)
    target.write_text("original content", encoding="utf-8")
    lock.apply_readonly_lock(target)
    with pytest.raises(PermissionError):
        target.write_text("attempted overwrite", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "original content"


@pytest.mark.allow_subprocess
def test_verify_locked_confirms_the_lock_took(lock_test_dir):
    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    lock.apply_readonly_lock(target)
    assert lock.verify_locked(target) is True


@pytest.mark.allow_subprocess
def test_verify_locked_returns_false_for_an_unlocked_file(lock_test_dir):
    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    assert lock.verify_locked(target) is False
    target.unlink()  # never locked -- safe to clean up normally


@pytest.mark.allow_subprocess
def test_apply_readonly_lock_is_a_noop_the_second_time(lock_test_dir):
    # NOT "icacls runs twice successfully" -- once OWNER RIGHTS denies
    # WRITE_DAC, a second icacls /deny call against the same file would
    # itself be denied. Idempotency lives at the call level: verify_locked()
    # short-circuits the second call entirely.
    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    lock.apply_readonly_lock(target)
    lock.apply_readonly_lock(target)  # must not raise
    assert lock.verify_locked(target) is True


@pytest.mark.allow_subprocess
def test_apply_readonly_lock_completes_a_partial_lock_without_raising(lock_test_dir):
    """Simulates the exact state a crash between the two icacls calls in
    apply_readonly_lock leaves behind (spec §4 step 9's resume scenario,
    Task 15): read-only attribute set and the account-level deny applied,
    but the OWNER RIGHTS deny never landed. verify_locked() must report this
    as NOT fully locked, and a subsequent apply_readonly_lock() call must
    complete it -- not raise PermissionError trying to re-run os.chmod on an
    attribute that's already set."""
    import getpass
    import os
    import stat
    import subprocess

    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)
    account = getpass.getuser()
    subprocess.run(
        ["icacls", str(target), "/deny", f"{account}:(WD,WA,WEA,DE,WDAC,WO)"],
        capture_output=True, text=True, check=True,
    )

    assert lock.verify_locked(target) is False  # partially locked, not fully

    lock.apply_readonly_lock(target)  # must not raise

    assert lock.verify_locked(target) is True


@pytest.mark.allow_subprocess
def test_owner_rights_deny_actually_closes_the_self_reset_hole(lock_test_dir):
    # The empirical claim spec §10 makes: the SAME non-elevated account that
    # created and locked the file cannot reset its own deny rule. Proven
    # here by actually attempting the bypass, not by re-reading our own
    # icacls output back.
    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    lock.apply_readonly_lock(target)

    reset_result = subprocess.run(
        ["icacls", str(target), "/reset"], capture_output=True, text=True,
    )
    assert reset_result.returncode != 0
    assert lock.verify_locked(target) is True  # still locked -- the reset did not take


@pytest.mark.allow_subprocess
def test_icacls_output_shows_the_owner_rights_deny_entry(lock_test_dir):
    target = _fresh_target(lock_test_dir)
    target.write_text("content", encoding="utf-8")
    lock.apply_readonly_lock(target)
    result = subprocess.run(["icacls", str(target)], capture_output=True, text=True)
    # On this machine's Windows build, icacls resolves the well-known
    # S-1-3-4 SID to its display name "OWNER RIGHTS" rather than printing
    # the raw SID string -- the exact ambiguity lock.verify_locked()'s own
    # docstring already anticipates and handles by matching either form.
    # The brief's literal "S-1-3-4" in result.stdout assertion does not
    # survive that resolution on this build; widened to match either form,
    # same as verify_locked's own check.
    assert "S-1-3-4" in result.stdout or "OWNER RIGHTS" in result.stdout.upper()
    assert "DENY" in result.stdout.upper()
    # Pin the FIRST icacls call too (the account-level deny), not just the
    # OWNER RIGHTS one. Nothing else in this suite checks for it:
    # verify_locked() never inspects the account-level entry, and the
    # account-level deny is not actually redundant with the OWNER RIGHTS
    # deny -- OWNER RIGHTS only applies while the accessing principal IS the
    # object's owner, so the account-level deny is what covers a changed-
    # ownership scenario. Without this assertion, deleting the account-level
    # /deny call from apply_readonly_lock would silently pass all 7 tests.
    account = getpass.getuser()
    assert f"{account.upper()}:(DENY)" in result.stdout.upper()
