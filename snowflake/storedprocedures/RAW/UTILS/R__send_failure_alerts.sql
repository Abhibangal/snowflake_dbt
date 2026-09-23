CREATE OR REPLACE PROCEDURE SEND_FAILURE_ALERT("JOB_ID" VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    v_found         NUMBER;
    v_sp_name       VARCHAR;
    v_error_msg     VARCHAR;
    v_duration      FLOAT;
    v_email_subject VARCHAR;
    v_email_body    VARCHAR;
BEGIN
    -- Unlike the success alert, this one is called with a real JOB_ID taken
    -- straight out of LOG_HISTORY (see the send_run_alert macro), so an exact
    -- match is correct here - one failed job produces one alert.
    --
    -- Aggregates are used so this always returns exactly one row: that gives a
    -- row count for the guard below, and COALESCE keeps every value non-NULL.
    -- In SQL a single NULL in a concatenation makes the ENTIRE string NULL, and
    -- a NULL subject/body makes SYSTEM$SEND_EMAIL raise STATEMENT_ERROR, which
    -- would fail the whole dbt run because this runs from an on-run-end hook.
    SELECT COUNT(*),
           COALESCE(MAX(SP_NAME), 'unknown job'),
           COALESCE(MAX(MESSAGE), 'Unknown Error'),
           COALESCE(MAX(DURATION_SECONDS), 0)
      INTO :v_found, :v_sp_name, :v_error_msg, :v_duration
      FROM {{ databases.RAW }}.UTILS.LOG_HISTORY
     WHERE JOB_ID = :JOB_ID;

    IF (:v_found = 0) THEN
        RETURN 'No log row found for JOB_ID - failure alert skipped.';
    END IF;

    v_email_subject := '❌ MDC Alert: ' || :v_sp_name || ' FAILED';

    v_email_body := '
    <div style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; max-width: 600px; margin: auto;">
        <div style="background-color: #dc3545; padding: 15px; color: white; text-align: center;">
            <h2 style="margin: 0;">Procedure Execution Failed</h2>
        </div>
        <div style="padding: 20px; color: #333;">
            <p><strong>Job ID:</strong> ' || COALESCE(:JOB_ID, 'n/a') || '</p>
            <p><strong>Procedure:</strong> ' || :v_sp_name || '</p>
            <p><strong>Duration:</strong> ' || ROUND(:v_duration, 2) || ' seconds</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 15px 0;">
            <p><strong>Error Details:</strong></p>
            <p style="background: #f8f9fa; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 12px; color: #dc3545;">'
            || :v_error_msg || '
            </p>
        </div>
    </div>';

    CALL SYSTEM$SEND_EMAIL(
        'EMAIL_NOTIFY_INTEGRATION',
        'abhij.it.bangal92@gmail.com',
        :v_email_subject,
        :v_email_body,
        'text/html'
    );

    RETURN 'Failure alert sent successfully.';
END;
$$;
