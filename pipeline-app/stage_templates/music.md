/{{ skill }}

Read the following upstream artifacts and produce the music bed brief:
{% for f in input_files %}
- `{{ f }}`
{% endfor %}
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward any
citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final brief to `{{ raw_output_path }}` (overwrite it completely each time you produce a
new draft).
