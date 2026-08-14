"""Tests the read-only guarantees for real -- an actual OS-level write
attempt must fail, not a code-review assumption (spec §13)."""
from __future__ import annotations

import getpass
import subprocess

import pytest

from doc_ingest import lock, sync


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
    try:
        sync.sync_source_files(conn, input_root)  # must not raise -- read-only scan
        with pytest.raises(PermissionError):
            target.write_bytes(b"an attempted mutation of the read-only input tree")
    finally:
        subprocess.run(["icacls", str(target), "/reset"], capture_output=True, text=True)


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
