-- Runs the dbt project object published by `snow dbt deploy` in CI.
-- dbt_* and warehouses.* are injected at SchemaChange deploy time.

CREATE OR ALTER TASK TASK_EXECUTE_DBT
    WAREHOUSE = {{ warehouses.ELT }}
    SCHEDULE = 'USING CRON 0 2 * * * UTC'
    COMMENT = 'Execute deployed dbt project {{ dbt_project_name }}'
AS
    EXECUTE DBT PROJECT {{ dbt_database }}.{{ dbt_schema }}.{{ dbt_project_name }}
        ARGS = '{{ dbt_args }}';

ALTER TASK TASK_EXECUTE_DBT RESUME;
