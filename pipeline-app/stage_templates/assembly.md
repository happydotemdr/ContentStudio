/{{ skill }}

Read these upstream artifacts and produce the assembly/edit plan:
- script: `{{ inputs['scripting'] }}` (beat timing, Delivery notes)
- styleboard — its BINDINGS line resolves every `{style:...}` / `{char:...}` slot in the
  prompt sheet against `docs/style-library.md`: `{{ inputs['styleboard'] }}`
- voiceover brief: `{{ inputs['voiceover'] }}`
- visual prompt sheet: `{{ inputs['visual'] }}`
{% if 'music' in inputs %}
- music bed brief: `{{ inputs['music'] }}` — use its bed arc, hook hold-out and asset
  filename in the loudness/mix section.
{% else %}
No music bed brief exists for this Short. Carry the rights-note checkpoint unchanged — an
absent bed is a legitimate outcome, not a blocker.
{% endif %}
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}`. If it carries a
"constraints that survive to publish" line, honor it in the caption/overlay treatment and
restate it verbatim in this edit plan's own notes.
{% endif %}
{{ user_message }}

Write your final edit plan to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).
