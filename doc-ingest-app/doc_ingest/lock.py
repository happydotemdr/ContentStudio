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
import re
import stat
import subprocess
from pathlib import Path

_DENY_RIGHTS = "WD,WA,WEA,DE,WDAC,WO"
_OWNER_RIGHTS_SID = "*S-1-3-4"

# A genuine icacls deny ACE is printed as "<principal>:(DENY)(<rights>)" with
# NO separator between the principal and the colon -- so the trustee token and
# "(DENY)" are CONTIGUOUS. That contiguity is what makes this safe to search
# for anywhere in icacls's output, echoed file path included: ':' is one of the
# nine characters naming.sanitize_component strips unconditionally from every
# name this pipeline creates, so no converted filename or folder can contain a
# colon at all, and therefore no path echo can ever produce this substring.
# icacls resolves S-1-3-4 to its display name "OWNER RIGHTS" on some Windows
# builds and prints the raw SID on others; both forms are accepted.
_OWNER_RIGHTS_DENY_ACE_RE = re.compile(r"(?:OWNER RIGHTS|S-1-3-4):\(DENY\)", re.IGNORECASE)


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
    # icacls prints the echoed file path immediately followed by the FIRST ACE
    # on the SAME line ("<path> OWNER RIGHTS:(DENY)(...)"), then each
    # subsequent ACE on its own line. Because the converted filename is derived
    # from a user-controlled Drive document title, a naive scan for "OWNER
    # RIGHTS"/"S-1-3-4" and "DENY" as INDEPENDENT substrings would let a
    # coaching doc titled around "Owner Rights (deny) ..." be misread as a real
    # ACE -- reporting an unprotected file as fully locked, and this call is the
    # only automated confirmation the OS-level lock actually landed.
    #
    # An earlier version defended against that by stripping the echoed path
    # prefix, which required str(path) to byte-match icacls's own output. That
    # match is not reliable: a non-ASCII filename (curly apostrophes, accented
    # characters -- ordinary in a real coaching archive) can decode differently
    # under an OEM-vs-ANSI codepage mismatch between icacls and
    # subprocess.run(text=True), the strip silently no-ops, and the check falls
    # back to the broad scan it was written to prevent -- i.e. it fails OPEN.
    #
    # The contiguous-substring match below has no such dependency: it needs the
    # trustee token and "(DENY)" adjacent across a colon, exactly as icacls
    # formats a real ACE, and ':' cannot occur in any name this pipeline
    # creates (see _OWNER_RIGHTS_DENY_ACE_RE).
    return bool(_OWNER_RIGHTS_DENY_ACE_RE.search(result.stdout))
