/{{ skill }}

Read the script at `{{ inputs['scripting'] }}` and produce the ElevenLabs voiceover production brief.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward any
citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final brief to `{{ raw_output_path }}` (overwrite it completely each time you produce a
new draft).