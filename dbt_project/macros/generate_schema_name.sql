-- By default dbt prefixes custom schemas with the target schema (ANALYTICS_STAGING).
-- Use the custom schema name as-is instead, so models land in NFL.STAGING and NFL.MARTS,
-- next to NFL.RAW. Models without a custom schema still go to the profile's schema.
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim | upper }}
    {%- endif -%}
{%- endmacro %}
