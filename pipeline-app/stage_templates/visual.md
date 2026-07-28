/{{ skill }}

Read the script at `{{ input_file }}` and produce the visual prompt sheet: per-beat Midjourney
stills, any i2v (image-to-video) prompts for beats that need real motion, and the cover/thumbnail
decision.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward any
citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final prompt sheet to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).