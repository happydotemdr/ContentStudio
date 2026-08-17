"""Orchestrates one claimed job end to end (spec §4 steps 6-9): stage,
convert, gauntlet, then an explicit write -> commit-as-current -> lock ->
verify sequence -- not one atomic operation, because a filesystem write and
an icacls subprocess call cannot share a SQLite transaction. A job that dies
-- or whose lock simply doesn't confirm -- between the write and the lock-
verify is left with locked_confirmed_at NULL and its conversion_jobs row at
'placing', not 'complete'; resume_unlocked_conversions re-attempts only the
lock and flips the job to 'complete' once it lands, never a reconversion.

A heartbeat thread runs on its own connection for the life of the job (spec
§5: never share conn across threads) so reclaim_stale_jobs (Task 7) can tell
a live worker from a dead one even when the actual conversion step takes
longer than the reclaim staleness threshold.

Handles both local files (pdf/docx/xlsx/txt/md/ppt) and Drive-native sources
(.gdoc/.gsheet, classification='gdoc_pointer') -- the latter export via
drive_client (Task 14) instead of copying from cfg.input_root."""
from __future__ import annotations

import datetime as dt
import json
import shutil
import threading
from pathlib import Path

from doc_ingest import calendar_client, client_tagging, convert, db, drive_client, frontmatter, gauntlet, jobs, lock, metadata_readers, naming

_LOCAL_EXTENSIONS = {"pdf": "pdf", "docx": "docx", "xlsx": "xlsx", "txt": "txt", "md": "md", "ppt": "ppt"}


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _db_path_of(conn) -> Path:
    """The heartbeat thread needs its own connection (spec §5) but
    process_job only receives an already-open one -- PRAGMA database_list's
    third column is the file path SQLite actually resolved from the
    connection string, which is how the heartbeat thread gets there without
    process_job's signature needing a separate db_path parameter."""
    row = conn.execute("PRAGMA database_list").fetchone()
    return Path(row[2])


def _run_heartbeat_loop(db_path: Path, job_id: int, worker_id: str, interval_s: float, stop_event: threading.Event) -> None:
    heartbeat_conn = db.get_connection(db_path)
    try:
        while not stop_event.wait(interval_s):
            try:
                jobs.heartbeat(heartbeat_conn, job_id, worker_id)
            except Exception:
                pass  # best-effort -- a missed tick risks an earlier reclaim, not a crash
    finally:
        heartbeat_conn.close()


def _source_type_for(extension: str, sniffed_signature: str | None) -> str:
    if extension:
        return _LOCAL_EXTENSIONS[extension]
    if sniffed_signature == "pdf":
        return "pdf"
    raise ValueError(f"cannot determine source_type for an extensionless file (sniffed_signature={sniffed_signature!r})")


def _convert(staged_path, source_type: str, cfg):
    """TXT/MD bypass firecrawl entirely -- it's not in firecrawl's supported
    format list, and spec §2/§8 call for a verbatim pass-through with
    frontmatter added, not a parse."""
    if source_type in ("txt", "md"):
        try:
            body = staged_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            return convert.ConversionResult(success=False, markdown_body=None, tool="passthrough", error=f"invalid_utf8: {exc}")
        return convert.ConversionResult(success=True, markdown_body=body, tool="passthrough", error=None)
    return convert.convert_local_file(staged_path, source_type, cfg)


def _convert_drive_native(service, doc_id: str, source_type: str, tmp_dir, cfg):
    """Drive export first, then -- for anything that came back as raw bytes
    rather than markdown (the docx/xlsx fallback paths, spec §9) -- the same
    local conversion + independent-reader path a real local file of that
    type would get. tool is preserved from the EXPORT step (google-docs-
    export / google-docs-export-docx-fallback / google-sheets-export), not
    overwritten with 'firecrawl-parse', so the record correctly shows the
    file came via Drive.

    export_google_doc doesn't know ahead of time whether it'll get markdown
    or docx bytes, so it writes to whatever path it's given -- if the docx
    fallback happened, the file at that path IS docx content but is still
    named export.md at that point. It's renamed to export.docx before being
    treated as a real .docx (read by metadata_readers, sent to firecrawl
    with a matching filename) rather than left as a .md-named file holding
    binary docx bytes."""
    if source_type == "gdoc":
        dest = tmp_dir / "export.md"
        export_result = drive_client.export_google_doc(service, doc_id, dest, cfg)
        if not export_result.success:
            return export_result, None, {}
        if export_result.tool == "google-docs-export":
            return export_result, dest, {}  # direct markdown -- see Task 22's open item 2

        docx_path = tmp_dir / "export.docx"
        dest.rename(docx_path)
        metadata = {
            "source_word_count": metadata_readers.read_docx_word_count(docx_path),
            "source_table_count": metadata_readers.read_docx_table_count(docx_path),
        }
        converted = _convert(docx_path, "docx", cfg)
        merged = convert.ConversionResult(
            success=converted.success, markdown_body=converted.markdown_body,
            tool=export_result.tool, error=converted.error,
        )
        return merged, docx_path, metadata

    dest = tmp_dir / "export.xlsx"
    export_result = drive_client.export_google_sheet(service, doc_id, dest, cfg)
    if not export_result.success:
        return export_result, None, {}
    sheet_count, row_count = metadata_readers.read_xlsx_sheet_and_row_counts(dest)
    converted = _convert(dest, "xlsx", cfg)
    merged = convert.ConversionResult(
        success=converted.success, markdown_body=converted.markdown_body,
        tool=export_result.tool, error=converted.error,
    )
    return merged, dest, {"source_sheet_count": sheet_count, "source_row_count": row_count}


def _independent_metadata(staged_path, source_type: str) -> dict:
    """SOURCE-side values only, read independently of firecrawl's own
    output -- Gate 1 (Task 11) computes every OUTPUT-side count itself from
    the assembled markdown."""
    if source_type == "pdf":
        return {"page_count": metadata_readers.read_pdf_page_count(staged_path)}
    if source_type == "docx":
        return {
            "source_word_count": metadata_readers.read_docx_word_count(staged_path),
            "source_table_count": metadata_readers.read_docx_table_count(staged_path),
        }
    if source_type == "xlsx":
        sheet_count, row_count = metadata_readers.read_xlsx_sheet_and_row_counts(staged_path)
        return {"source_sheet_count": sheet_count, "source_row_count": row_count}
    return {}


def _frontmatter_extras(independent_metadata: dict) -> dict:
    """Maps this module's internal source_*-prefixed metadata keys onto the
    exact field names spec §7 sanctions in frontmatter (page_count,
    word_count, sheet_count, row_count_total) -- source_table_count is
    gauntlet-only and deliberately excluded, since table_count isn't a
    frontmatter field spec §7 lists."""
    extras = {}
    if "page_count" in independent_metadata:
        extras["page_count"] = independent_metadata["page_count"]
    if "source_word_count" in independent_metadata:
        extras["word_count"] = independent_metadata["source_word_count"]
    if "source_sheet_count" in independent_metadata:
        extras["sheet_count"] = independent_metadata["source_sheet_count"]
    if "source_row_count" in independent_metadata:
        extras["row_count_total"] = independent_metadata["source_row_count"]
    return extras


def _fail_job(conn, job_id: int, reason: str) -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE conversion_jobs SET status = 'failed', failure_reason = ?, finished_at = ? WHERE id = ?",
            (reason, _now_iso(), job_id),
        )


def process_job(conn, job_id: int, cfg, worker_id: str, drive_service_factory=None, calendar_service_factory=None) -> None:
    job = conn.execute(
        "SELECT source_file_id FROM conversion_jobs WHERE id = ?", (job_id,)
    ).fetchone()
    source_file_id = job[0]
    source = conn.execute(
        "SELECT rel_path, extension, size_bytes, sniffed_signature, mtime, content_hash, "
        "classification, doc_id, drive_modified_time FROM source_files WHERE id = ?",
        (source_file_id,),
    ).fetchone()
    (rel_path, extension, size_bytes, sniffed_signature, source_mtime, local_content_hash,
     classification, doc_id, drive_modified_time) = source
    is_drive_native = classification == "gdoc_pointer"

    tmp_dir = cfg.tmp_root / f"job-{job_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with db.transaction(conn):
        conn.execute(
            "UPDATE conversion_jobs SET status = 'converting', tmp_dir = ? WHERE id = ?",
            (str(tmp_dir), job_id),
        )

    stop_heartbeat = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_run_heartbeat_loop,
        args=(_db_path_of(conn), job_id, worker_id, cfg.reclaim_heartbeat_interval_s, stop_heartbeat),
        daemon=True,
    )
    heartbeat_thread.start()
    try:
        # --- steps 6-8: stage, convert, gauntlet -- ANY unexpected exception
        # here (an unmapped extension, a corrupt/encrypted PDF/DOCX/XLSX that
        # metadata_readers can't parse, a staging I/O error, or -- since Task
        # 22 -- a Drive-native failure such as a missing/expired token.json or
        # a non-retryable Drive API error) is converted to a clean job failure
        # rather than allowed to propagate. Left unhandled, the job would stay
        # stuck at 'converting' forever, get reset to 'pending' by reclaim_stale_jobs
        # once the staleness threshold passes, get re-claimed, and crash
        # identically -- an unbounded poison-pill retry loop that burns a
        # real billed firecrawl .parse() call every single pass (since
        # _convert runs before this can fail), because the job never reaches
        # 'failed' and enqueue_pending_jobs's already-failed-at-this-version
        # guard -- the only backstop against retry loops in the whole
        # design -- can never engage. Deliberately scoped to ONLY this
        # pre-write section: the write -> commit -> lock -> verify sequence
        # below must keep raising uncaught, since that's what leaves a job
        # correctly parked at 'placing' for resume_unlocked_conversions
        # rather than losing track of an already-written, already-committed
        # conversion.
        try:
            if is_drive_native:
                source_type = "gdoc" if extension == "gdoc" else "gsheet"
                service = (drive_service_factory or drive_client.build_default_service)(cfg)
                conversion_result, staged_path, independent_metadata = _convert_drive_native(
                    service, doc_id, source_type, tmp_dir, cfg,
                )
                # source_hash for frontmatter/conversions -- see Task 22's open
                # item 1 (a real headRevisionId isn't fetched yet;
                # drive_modified_time is a practical stand-in with the same "did
                # the content change" purpose).
                source_hash = drive_modified_time
                # source_modified_at must be the actual Drive edit time, NOT the
                # local stub's filesystem mtime -- the stub is a static 176-byte
                # pointer that never changes when the real document is edited
                # (spec §4 step 3, §7). Using the stub's mtime here would be
                # exactly the conflation the mtime-vs-modifiedTime regression
                # test (Task 22) exists to catch, just moved into frontmatter
                # instead of into enqueue's change detection.
                source_modified_at = drive_modified_time
            else:
                source_type = _source_type_for(extension, sniffed_signature)

                staged_path = tmp_dir / rel_path.rsplit("/", 1)[-1]
                shutil.copy2(cfg.input_root / rel_path, staged_path)

                conversion_result = _convert(staged_path, source_type, cfg)
                independent_metadata = _independent_metadata(staged_path, source_type) if conversion_result.success else {}
                source_hash = local_content_hash
                source_modified_at = source_mtime

            if not conversion_result.success:
                _fail_job(conn, job_id, conversion_result.error)
                return

            prior_version = conn.execute(
                "SELECT MAX(version_number) FROM conversions WHERE source_file_id = ?", (source_file_id,)
            ).fetchone()[0]
            version = (prior_version or 0) + 1

            gate2_result, dest_rel_path = gauntlet.run_gate2(conn, rel_path, source_file_id, version, cfg)
            if not gate2_result.passed:
                _fail_job(conn, job_id, gate2_result.failure_reason)
                return

            frontmatter_extras = _frontmatter_extras(independent_metadata)
            tag_result = client_tagging.classify(
                conn, rel_path, conversion_result.markdown_body,
                calendar_service_factory or calendar_client.build_default_service,
            )
            frontmatter_extras.update(tag_result.frontmatter_extra)
            client_value = tag_result.frontmatter_extra.get("client")
            if tag_result.event_type:
                with db.transaction(conn):
                    conn.execute(
                        "INSERT INTO events (ts, event_type, source_file_id, details_json) VALUES (?, ?, ?, ?)",
                        (_now_iso(), tag_result.event_type, source_file_id, json.dumps(tag_result.event_details)),
                    )
            base_fm = {
                "source_path": rel_path, "source_type": source_type, "source_hash": source_hash,
                "source_modified_at": source_modified_at, "converted_at": _now_iso(),
                "conversion_tool": conversion_result.tool, "version": version, "status": "current",
                "business_line": "freedom2beu", "gauntlet_passed_at": _now_iso(),
            }
            fm = frontmatter.build_frontmatter(base_fm, frontmatter_extras)
            assembled = frontmatter.serialize(fm, conversion_result.markdown_body)

            gate1_result = gauntlet.run_gate1(source_type, size_bytes or 0, assembled, independent_metadata, cfg)
            if not gate1_result.passed:
                _fail_job(conn, job_id, gate1_result.failure_reason)
                return
        except Exception as exc:
            _fail_job(conn, job_id, f"unexpected_error: {exc}")
            return

        # --- 9(a): write the final file ---
        final_path = cfg.converted_root / dest_rel_path
        final_path.parent.mkdir(parents=True, exist_ok=True)
        # \\?\-prefixed open(), not final_path.write_text(): the defense-in-
        # depth backstop spec §6 describes for a path that's still over
        # cfg.long_path_threshold_chars despite naming.py's shortening --
        # applied at this one call site because Python's open() on Windows
        # honors the prefix reliably, which icacls (lock.py) is not
        # guaranteed to (naming.long_path's docstring, Task 4).
        with open(naming.long_path(final_path), "w", encoding="utf-8") as fh:
            fh.write(assembled)

        # --- 9(b): commit the DB row as current + FTS, one transaction ---
        drive_modified_time_at_conversion = drive_modified_time if is_drive_native else None
        with db.transaction(conn):
            conn.execute(
                "UPDATE conversions SET status = 'superseded' WHERE source_file_id = ? AND status = 'current'",
                (source_file_id,),
            )
            conn.execute(
                """
                INSERT INTO conversions
                    (source_file_id, job_id, version_number, output_path, status, source_type,
                     source_hash_at_conversion, drive_modified_time_at_conversion, conversion_tool,
                     converted_at, gauntlet_passed_at, client,
                     page_count, word_count, sheet_count, row_count_total)
                VALUES (?, ?, ?, ?, 'current', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_file_id, job_id, version, dest_rel_path, source_type,
                    source_hash, drive_modified_time_at_conversion, conversion_result.tool,
                    _now_iso(), _now_iso(), client_value,
                    frontmatter_extras.get("page_count"),
                    frontmatter_extras.get("word_count"),
                    frontmatter_extras.get("sheet_count"),
                    frontmatter_extras.get("row_count_total"),
                ),
            )
            conversion_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO conversions_fts (conversion_id, source_rel_path, output_path, body) VALUES (?, ?, ?, ?)",
                (conversion_id, rel_path, dest_rel_path, assembled),
            )
            conn.execute(
                "UPDATE conversion_jobs SET status = 'placing' WHERE id = ?", (job_id,),
            )

        # --- 9(c)/(d): lock and verify -- may raise; a caller-visible crash
        # here, or a False from verify_locked with no exception at all, both
        # leave the job at 'placing' rather than 'complete' --
        # resume_unlocked_conversions is what advances it from here.
        lock.apply_readonly_lock(final_path)
        confirmed = lock.verify_locked(final_path)

        with db.transaction(conn):
            if confirmed:
                conn.execute(
                    "UPDATE conversions SET locked_confirmed_at = ? WHERE id = ?", (_now_iso(), conversion_id),
                )
                conn.execute(
                    "UPDATE conversion_jobs SET status = 'complete', finished_at = ? WHERE id = ?",
                    (_now_iso(), job_id),
                )
            # else: leave status = 'placing'. reclaim_stale_jobs (Task 7)
            # already knows not to reset a 'placing' job back to 'pending'
            # once its conversion has landed -- only
            # resume_unlocked_conversions advances it further from here.
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=5)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def resume_unlocked_conversions(conn, cfg) -> list[int]:
    """Re-attempts lock+verify for any 'current' conversion whose write
    completed but whose lock was never confirmed -- never reconverts. Also
    advances the associated conversion_jobs row to 'complete' once the lock
    actually lands, since process_job deliberately left it at 'placing'.

    Each row's lock attempt is isolated in its own try/except: this function
    IS the crash-recovery mechanism, so one row whose icacls call fails
    (lock.apply_readonly_lock uses check=True and raises CalledProcessError
    on any icacls failure) must not abort the whole sweep and strand every
    OTHER unlocked conversion in the same batch -- and every future wake,
    since nothing would otherwise mark or skip the failing row. A failure is
    logged as an events row (mirroring gauntlet.run_gate2's
    naming_collision_resolved pattern) and the sweep moves on."""
    rows = conn.execute(
        "SELECT id, output_path, job_id, source_file_id FROM conversions "
        "WHERE status = 'current' AND locked_confirmed_at IS NULL"
    ).fetchall()
    resumed = []
    for conversion_id, output_path, job_id, source_file_id in rows:
        final_path = cfg.converted_root / output_path
        if not final_path.exists():
            continue
        try:
            lock.apply_readonly_lock(final_path)
            confirmed = lock.verify_locked(final_path)
        except Exception as exc:
            with db.transaction(conn):
                conn.execute(
                    "INSERT INTO events (ts, event_type, source_file_id, conversion_id, details_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        dt.datetime.now(dt.timezone.utc).isoformat(),
                        "resume_lock_failed",
                        source_file_id,
                        conversion_id,
                        json.dumps({"error": str(exc)}),
                    ),
                )
            continue
        if confirmed:
            now = dt.datetime.now(dt.timezone.utc).isoformat()
            with db.transaction(conn):
                conn.execute(
                    "UPDATE conversions SET locked_confirmed_at = ? WHERE id = ?", (now, conversion_id),
                )
                if job_id is not None:
                    conn.execute(
                        "UPDATE conversion_jobs SET status = 'complete', finished_at = ? "
                        "WHERE id = ? AND status != 'complete'",
                        (now, job_id),
                    )
            resumed.append(conversion_id)
    return resumed
