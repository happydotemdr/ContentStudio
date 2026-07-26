/{{ skill }}

Read the following upstream artifacts and produce the assembly/edit plan:
{% for f in input_files %}
- `{{ f }}`
{% endfor %}

{{ user_message }}

Write your final edit plan to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).