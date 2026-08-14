"""Two-layer Windows read-only enforcement: an icacls deny-ACE (the real
backstop, spec §10) plus the read-only file attribute (a second signal).
Denies Write/WriteData/WriteAttributes/Delete AND WriteDAC/WriteOwner, on
BOTH the account's own SID and the well-known OWNER RIGHTS SID (S-1-3-4) --
the account-only deny leaves Windows' implicit owner WRITE_DAC grant intact,
which is what would let the same non-elevated account reset its own deny
rule with no elevation. Locking is one-directional and NOT idempotent at the
icacls-call level once fully applied (a fully denied WRITE_DAC means a
second icacls call would itself be denied -- that's the point);
apply_readonly_lock is idempotent at the call level by checking
verify_locked() first."""
from __future__ import annotations

import getpass
import os
import stat
import subprocess
from pathlib import Path

_DENY_RIGHTS = "WD,WA,WEA,DE,WDAC,WO"
_OWNER_RIGHTS_SID = "*S-1-3-4"


def apply_readonly_lock(path: Path) -> None:
    if verify_locked(path):
        return  # already fully locked -- a second icacls call would itself be denied

    # Skip if the read-only ATTRIBUTE bit is already set. os.chmod uses
    # SetFileAttributes under the hood, which needs WriteAttributes
    # regardless of whether the call would actually change anything -- so on
    # the RESUME path (first icacls call already landed, denying WA to the
    # account, but the OWNER RIGHTS call below hasn't run yet), a second
    # unconditional os.chmod call here would itself raise PermissionError,
    # even though there's nothing left for it to do. This is exactly the
    # partial-lock state Task 15's resume_unlocked_conversions calls this
    # function to finish.
    if not (path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY):
        os.chmod(path, stat.S_IREAD)

    # Adding this deny ACE a second time (the resume path) is harmless --
    # icacls appends a redundant entry rather than erroring, and at this
    # point the account still has implicit WRITE_DAC (the OWNER RIGHTS deny
    # below hasn't landed yet), so modifying its own DACL still succeeds.
    account = getpass.getuser()
    subprocess.run(
        ["icacls", str(path), "/deny", f"{account}:({_DENY_RIGHTS})"],
        capture_output=True, text=True, check=True,
    )
    # The entry that actually closes the self-reset hole -- see module
    # docstring. Applied second and separately: if the process dies between
    # this call and the one above, verify_locked() still correctly reports
    # "not yet fully locked" and a later retry (Task 15's
    # resume_unlocked_conversions) can still complete it, because the
    # account-only deny above does not yet block WRITE_DAC on its own.
    subprocess.run(
        ["icacls", str(path), "/deny", f"{_OWNER_RIGHTS_SID}:({_DENY_RIGHTS})"],
        capture_output=True, text=True, check=True,
    )


def verify_locked(path: Path) -> bool:
    if not path.exists():
        return False
    if os.access(path, os.W_OK):
        return False
    result = subprocess.run(["icacls", str(path)], capture_output=True, text=True, check=True)
    output = result.stdout
    # icacls sometimes resolves the well-known OWNER RIGHTS SID to its
    # display name ("OWNER RIGHTS") rather than printing the raw "S-1-3-4"
    # string, depending on Windows version/locale -- match either form, or
    # this would never report True on a build that resolves it, and every
    # job would stall at 'placing' forever.
    has_owner_rights_entry = "S-1-3-4" in output or "OWNER RIGHTS" in output.upper()
    return has_owner_rights_entry and "DENY" in output.upper()
