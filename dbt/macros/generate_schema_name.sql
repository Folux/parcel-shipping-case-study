{#
  Use a model's configured +schema as an ABSOLUTE schema name (e.g. "gold"),
  instead of dbt's default behavior of prefixing it with the target schema
  (which would produce "silver_gold"). Models without a +schema fall back to
  the target schema (silver) from the bundle's dbt task.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
