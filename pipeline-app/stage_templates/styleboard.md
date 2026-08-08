/{{ skill }}

Read the script at `{{ input_file }}` and lock this Short's two visual worlds: the
Register A/present world, the Register B/source-era world, the motif that crosses both,
and which Style Library entry each register binds to.

The Style Library is `docs/style-library.md`. Read it before you bind anything — it is the
only record of which worlds already have an entry.
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — its thinker,
source and motif populate the register_b_* keys and `motif` directly rather than being
invented here.
{% endif %}
{{ user_message }}

Do NOT write any shot prompts and do NOT invent an `--sref` code. If `docs/style-library.md`
has no entry for a world, raise it under DISCOVERY REQUESTS — but check the file first, so
the request is a finding rather than a guess.

Write your final styleboard to `{{ raw_output_path }}` (overwrite it completely each time
you produce a new draft).
