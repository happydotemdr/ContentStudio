/{{ skill }}

Read these and produce the multi-surface post copy:
- script (hook language, AEO specifics): `{{ inputs['scripting'] }}`
- packaging direction (working title / angle): `{{ inputs['ideation'] }}`
- edit plan: `{{ inputs['assembly'] }}`
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}`. If it carries a
"constraints that survive to publish" line, honor it verbatim in the post copy.
{% endif %}
{{ user_message }}

Write your final post copy to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).
