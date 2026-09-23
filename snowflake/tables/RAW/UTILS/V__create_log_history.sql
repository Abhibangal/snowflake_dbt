create table if not exists LOG_HISTORY (
    JOB_ID            string,
    SP_NAME           string,
    SP_DATABASE       string,
    SP_SCHEMA         string,
    INPUT_PARAMS      variant,
    LOG_LEVEL         string,
    START_TIME        timestamp_ntz,
    STATUS            string,        -- SUCCESS / FAILED / SKIPPED
    EXECUTED_BY       string,
    END_TIME          timestamp_ntz,
    DURATION_SECONDS  float,
    ROWS_PROCESSED    number,
    MESSAGE           string
);