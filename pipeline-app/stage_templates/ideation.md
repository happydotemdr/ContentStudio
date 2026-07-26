/{{ skill }}

{% if grounding_pointer %}
A companion grounding artifact for this Short is available at `{{ grounding_pointer }}`. Read it
and prefer an angle consistent with its archetype/angle hint, per shorts-ideation's "Optional
input" section.
{% endif %}
Raw idea: {{ user_message }}

Write your final concept brief to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).