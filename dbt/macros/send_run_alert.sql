{% macro send_run_alert() %}
    {#- flags.WHICH gates alerting to real data runs only. on-run-end also fires
        on compile/parse (what `snow dbt deploy` does), so without this guard every
        deployment would send an email and any alert error would fail the deploy. -#}
    {% if execute and flags.WHICH in ('run', 'build') %}
        {%- set alert_schema = var('log_schema', 'UTILS') -%}
        {%- set log_table = log_db() ~ '.' ~ alert_schema ~ '.' ~ var('log_table', 'LOG_HISTORY') -%}

        {#- get the JOB_IDs of today's latest-failed objects -#}
        {% set failed_sql %}
            SELECT JOB_ID
            FROM (
                SELECT JOB_ID, STATUS
                FROM {{ log_table }}
                WHERE START_TIME::DATE = CURRENT_DATE()
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY SP_NAME, SP_DATABASE, SP_SCHEMA
                    ORDER BY START_TIME DESC) = 1
            ) A
            WHERE A.STATUS = 'FAILED'
        {% endset %}

        {% set failed = run_query(failed_sql) %}

        {% if failed and failed.rows | length > 0 %}
            {#- one failure alert per failed job -#}
            {% for row in failed.rows %}
                {% set c %}
                    call {{ log_db() }}.{{ alert_schema }}.SEND_FAILURE_ALERT('{{ row[0] }}')
                {% endset %}
                {% do run_query(c) %}
            {% endfor %}
        {% else %}
            {#- no failures: single success alert. But what does SUCCESS take? -#}
            {% set c %}
                call {{ log_db() }}.{{ alert_schema }}.SEND_SUCCESS_ALERT('{{ invocation_id }}')
            {% endset %}
            {% do run_query(c) %}
        {% endif %}
    {% endif %}
{% endmacro %}