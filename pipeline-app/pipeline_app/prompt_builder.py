from pathlib import Path

import jinja2


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
