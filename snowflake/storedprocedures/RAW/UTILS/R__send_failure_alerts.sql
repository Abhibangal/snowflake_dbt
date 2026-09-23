CREATE OR REPLACE PROCEDURE SEND_FAILURE_ALERT("JOB_ID" VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS '
DECLARE
    v_sp_name VARCHAR;
    v_error_msg VARCHAR;
    v_duration FLOAT;
    v_email_subject VARCHAR;
    v_email_body VARCHAR;
BEGIN
    -- 1. Fetch job details from the LOG_HISTORY table
    SELECT SP_NAME, COALESCE(MESSAGE, ''Unknown Error''), COALESCE(DURATION_SECONDS, 0)
    INTO :v_sp_name, :v_error_msg, :v_duration
    FROM {{ databases.RAW }}.UTILS.LOG_HISTORY
    WHERE JOB_ID = :JOB_ID;

    -- 2. Construct the email components
    v_email_subject := ''❌ MDC Alert: '' || :v_sp_name || '' FAILED'';
    
    -- Notice the "margin: auto;" added to the first div to center the email
    v_email_body := ''
    <div style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; max-width: 600px; margin: auto;">
        <div style="background-color: #dc3545; padding: 15px; color: white; text-align: center;">
            <h2 style="margin: 0;">Procedure Execution Failed</h2>
        </div>
        <div style="padding: 20px; color: #333;">
            <p><strong>Job ID:</strong> '' || :JOB_ID || ''</p>
            <p><strong>Procedure:</strong> '' || :v_sp_name || ''</p>
            <p><strong>Duration:</strong> '' || :v_duration || '' seconds</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 15px 0;">
            <p><strong>Error Details:</strong></p>
            <p style="background: #f8f9fa; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 12px; color: #dc3545;">'' 
            || :v_error_msg || ''
            </p>
        </div>
    </div>'';

    -- 3. Trigger the Snowflake Email Integration
    CALL SYSTEM$SEND_EMAIL(
        ''EMAIL_NOTIFY_INTEGRATION'',
        ''abhij.it.bangal92@gmail.com'',
        :v_email_subject,
        :v_email_body,
        ''text/html''
    );

    RETURN ''Failure alert sent successfully.'';
END;
';