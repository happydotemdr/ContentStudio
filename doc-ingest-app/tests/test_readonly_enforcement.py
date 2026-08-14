"""Tests the read-only guarantees for real -- an actual OS-level write
attempt must fail, not a code-review assumption (spec §13)."""
from __future__ import annotations

import getpass
import subprocess
import warnings

import pytest

from doc_ingest import lock, sync


def _icacls_reset(path):
    """Reset an icacls ACL and surface a failed reset instead of swallowing
    it -- a silently-failed reset here would leave a file/folder locked
    inside tmp_path with zero visibility, which is exactly the failure mode
    the lock_test_dir-vs-tmp_path split exists to avoid for real locks.
    Deliberately not check=True: this runs from a `finally` block and must
    never raise over a primary assertion failure/error already in flight."""
    result = subprocess.run(["icacls", str(path), "/reset"], capture_output=True, text=True)
    if result.returncode != 0:
        warnings.warn(
            f"icacls /reset failed for {path!r} (returncode={result.returncode}): "
            f"{result.stderr.strip()}",
            stacklevel=2,
        )


@pytest.mark.allow_subprocess
def test_a_readonly_input_folder_makes_any_write_attempt_fail_with_a_real_os_error(conn, tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    target = input_root / "a.pdf"
    target.write_bytes(b"%PDF-1.4 fake")

    account = getpass.getuser()
    subprocess.run(
        ["icacls", str(target), "/deny", f"{account}:(WD,WA,WEA,DE)"],
        capture_output=True, text=True, check=True,
    )
    # Denying the existing file alone only proves "a write to THIS file
    # fails" -- it says nothing about the FOLDER being read-only, which is
    # what the test name and spec §13's guarantee actually claim. Also deny
    # folder-level Write Data / Add subDirectory on input_root itself so
    # creating a brand-new file inside it is denied too.
    subprocess.run(
        ["icacls", str(input_root), "/deny", f"{account}:(WD,AD)"],
        capture_output=True, text=True, check=True,
    )
    try:
        sync.sync_source_files(conn, input_root)  # must not raise -- read-only scan
        with pytest.raises(PermissionError):
            target.write_bytes(b"an attempted mutation of the read-only input tree")
        with pytest.raises(PermissionError):
            (input_root / "new.pdf").write_bytes(b"an attempted new file in the read-only input tree")
    finally:
        _icacls_reset(target)
        _icacls_reset(input_root)


@pytest.mark.allow_subprocess
def test_a_locked_output_file_rejects_a_write_from_the_same_account(lock_test_dir):
    # lock_test_dir (Task 13), NOT tmp_path -- lock.apply_readonly_lock's
    # deny includes Delete at the OWNER RIGHTS level, so a file it fully
    # locks is not guaranteed deletable by the same non-elevated account
    # afterward, which would leave pytest's tmp_path cleanup hitting a real
    # PermissionError on every subsequent run.
    import uuid

    target = lock_test_dir / f"locked-{uuid.uuid4().hex}.pdf.md"
    target.write_text("locked content", encoding="utf-8")
    lock.apply_readonly_lock(target)
    with pytest.raises(PermissionError):
        target.write_text("attempted overwrite", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "locked content"
