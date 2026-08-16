/{{ skill }}

Read the concept brief at `{{ inputs['ideation'] }}` and write the shot-ready script per
shorts-scripting.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward any
citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final script to `{{ raw_output_path }}` (overwrite it completely each time you produce
a new draft).