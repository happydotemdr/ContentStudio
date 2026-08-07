/{{ skill }}

Read the script at `{{ input_file }}` and lock this Short's two visual worlds: the
Register A/present world, the Register B/source-era world, the motif that crosses both,
and which Style Library entry each register binds to.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — its thinker,
source and motif populate the register_b_* keys and `motif` directly rather than being
invented here.
{% endif %}
{{ user_message }}

Do NOT write any shot prompts and do NOT invent an `--sref` code. If a world has no
Style Library entry yet, raise it under DISCOVERY REQUESTS.

Write your final styleboard to `{{ raw_output_path }}` (overwrite it completely each time
you produce a new draft).
