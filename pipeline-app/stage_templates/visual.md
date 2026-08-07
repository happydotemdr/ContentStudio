/{{ skill }}

Read the following upstream artifacts and produce the visual prompt sheet: per-beat
Midjourney stills, any i2v (image-to-video) prompts for beats that need real motion, and
the cover/thumbnail decision.
{% for f in input_files %}
- `{{ f }}`
{% endfor %}

The styleboard artifact among those inputs owns the WORLD LOCK and the slot declarations.
Inherit them; do not re-emit the WORLD LOCK block into your sheet, and write every style
reference as a `{style:...}` slot rather than a literal `--sref` code.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward
any citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final prompt sheet to `{{ raw_output_path }}` (overwrite it completely each
time you produce a new draft).
