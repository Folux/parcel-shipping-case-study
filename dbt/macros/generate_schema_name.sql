{#
  Use a model's configured +schema as an ABSOLUTE schema name (e.g. "gold_dbt"),
  instead of dbt's default behavior of prefixing it with the target schema
  (which would produce "silver_dbt_gold_dbt"). Models without a +schema fall
  back to the target schema from the bundle's dbt task.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
