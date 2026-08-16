/{{ skill }}

Read the following upstream artifacts and produce the music bed brief:
- script (beat timings): `{{ inputs['scripting'] }}`
- voiceover brief — its tone-per-beat call is what the tone-contradiction check runs
  against: `{{ inputs['voiceover'] }}`
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward any
citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final brief to `{{ raw_output_path }}` (overwrite it completely each time you produce a
new draft).
