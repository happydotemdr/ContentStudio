from pathlib import Path

import jinja2

# T4 (not this task) adds StrictUndefined and enforces this as the frozen
# kickoff-context key set. Declared here early because T3's conformance test
# needs to import it to assert every template stays within it (A-08's static
# half). See P4-handoff task-3-brief.md / task-4-brief.md.
KICKOFF_CONTEXT_KEYS = frozenset(
    {"skill", "user_message", "grounding_pointer", "inputs", "raw_output_path"}
)


def _environment(templates_dir: Path) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_kickoff_prompt(templates_dir: Path, stage_id: str, context: dict) -> str:
    env = _environment(templates_dir)
    template = env.get_template(f"{stage_id}.md")
    return template.render(**context)
