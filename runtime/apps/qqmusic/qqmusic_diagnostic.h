#ifndef QQMUSIC_DIAGNOSTIC_H
#define QQMUSIC_DIAGNOSTIC_H
/* Numeric transport facts only. Never copy a URL, header, token or response. */
enum qq_connection_step {QQ_STEP_UNKNOWN,QQ_STEP_LOCAL,QQ_STEP_WIFI,QQ_STEP_DNS,QQ_STEP_TCP,QQ_STEP_TLS,QQ_STEP_HTTP,QQ_STEP_REPLY,QQ_STEP_CLOCK};
struct qq_connection_diagnostic {int endpoint,step,error,dns,tls,http;unsigned clock_year,clock_month,clock_day,clock_hour,clock_minute,server_hour,server_minute;int clock_skew_seconds;};
#endif
