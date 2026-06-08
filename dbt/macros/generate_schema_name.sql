{#
  Standard dbt override (this is the documented extension point, not a hack):
  https://docs.getdbt.com/docs/build/custom-schemas#changing-the-way-dbt-generates-a-schema-name

  By default dbt PREFIXES a model's +schema with the target schema
  ("silver" + "gold" -> "silver_gold"). This override makes +schema an
  ABSOLUTE name instead, so each layer lands in exactly the schema it declares
  (silver -> silver, gold -> gold). Models without a +schema fall back to the
  target schema from the bundle's dbt task.

  Safe here because each deploy goes to an isolated workspace (bundle
  mode: development) — the multi-developer collision the docs warn about
  doesn't apply.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
