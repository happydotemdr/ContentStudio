from pathlib import Path

import jinja2

# The complete kickoff context. Frozen: turn_service supplies exactly these and
# render_kickoff_prompt refuses anything else, so a template can never quietly
# consume a name nobody passes (A-08) and a supplied-but-unreferenced key can
# never be discarded in silence the way grounding_pointer was (A-04).
KICKOFF_CONTEXT_KEYS = frozenset(
    {"skill", "user_message", "grounding_pointer", "inputs", "raw_output_path"}
)


def _environment(templates_dir: Path) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        # StrictUndefined, not the default: an operator-edited template that
        # misspells a variable must raise at render time rather than emit a
        # kickoff prompt with the write instruction silently missing.
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_kickoff_prompt(templates_dir: Path, stage_id: str, context: dict) -> str:
    supplied = set(context)
    missing = sorted(KICKOFF_CONTEXT_KEYS - supplied)
    if missing:
        raise ValueError(f"kickoff context for '{stage_id}' is missing {missing}")
    unknown = sorted(supplied - KICKOFF_CONTEXT_KEYS)
    if unknown:
        raise ValueError(f"kickoff context for '{stage_id}' has unknown keys {unknown}")
    env = _environment(templates_dir)
    return env.get_template(f"{stage_id}.md").render(**context)


def sample_context(stage_def, raw_output_path: str = "runs/SAMPLE/raw_output.md") -> dict:
    """A dummy context shaped exactly like the real one, for trial-rendering an
    edited template before it reaches disk."""
    return {
        "skill": stage_def.skill,
        "user_message": "SAMPLE",
        "grounding_pointer": "rgs-briefs/SAMPLE.md",
        "inputs": {sid: f"runs/SAMPLE/{sid}/artifact.v1.md" for sid in stage_def.all_depends_on},
        "raw_output_path": raw_output_path,
    }


def validate_template_source(source: str, context: dict) -> None:
    """Trial-render an edited template. Raises TemplateSyntaxError or
    UndefinedError; returns None on success. Callers that write templates to
    disk should call this first."""
    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined, trim_blocks=True, lstrip_blocks=True
    )
    env.from_string(source).render(**context)
