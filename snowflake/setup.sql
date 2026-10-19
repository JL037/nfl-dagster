-- One-time Snowflake setup for nfl-dagster.
-- Run in a Snowsight SQL worksheet as ACCOUNTADMIN. Safe to re-run.
--
-- Creates:
--   NFL_WH     an X-Small warehouse that suspends after 60s idle (you pay only while queries run)
--   NFL        a database that NFL_ROLE owns, so dbt can create its own schemas inside it
--   NFL.RAW    where Dagster loads the raw Parquet files
--   NFL_ROLE   everything the pipeline needs, nothing more
--   NFL_SVC    a service user for Dagster and dbt: key-pair auth only, no password
--   NFL_DAGSTER_PLUS_SVC  the same, for Dagster+ Serverless (its own key; see below)
--   NFL_MONITOR a credit cap that suspends the warehouse if usage runs away
--   NFL_DEV    created later by `make clone-dev`, as a zero-copy clone of NFL
--
-- Before running: replace <YOUR_USERNAME>, <PUBLIC_KEY> and <DAGSTER_PLUS_PUBLIC_KEY> below.
-- <PUBLIC_KEY> is the body of your .pub file without the BEGIN/END lines.

use role accountadmin;

-- Compute
create warehouse if not exists nfl_wh
    warehouse_size = xsmall
    auto_suspend = 60
    auto_resume = true
    initially_suspended = true;

-- Spend guardrail: suspend the warehouse after 10 credits in a month.
create resource monitor if not exists nfl_monitor
    with credit_quota = 10
    frequency = monthly
    start_timestamp = immediately
    triggers
        on 80 percent do notify
        on 100 percent do suspend;
alter warehouse nfl_wh set resource_monitor = nfl_monitor;

-- Role, granted up to SYSADMIN so admins can still see everything it creates.
create role if not exists nfl_role;
grant role nfl_role to role sysadmin;
grant usage, operate on warehouse nfl_wh to role nfl_role;

-- Storage: the role owns the database, so it can create the schemas dbt builds into.
create database if not exists nfl;
grant ownership on database nfl to role nfl_role copy current grants;

-- Service user for the pipeline.
create user if not exists nfl_svc
    type = service
    default_role = nfl_role
    default_warehouse = nfl_wh
    default_namespace = nfl.raw
    comment = 'nfl-dagster pipeline (Dagster + dbt)';
alter user nfl_svc set rsa_public_key = '<PUBLIC_KEY>';
grant role nfl_role to user nfl_svc;

-- Service user for Dagster+ Serverless (production runs off the laptop). A user holds at most
-- two public keys, and NFL_SVC's are one per machine, so Dagster+ gets its own user: same role,
-- its own key, and it can be disabled or rotated without touching either machine. Its private
-- key goes into Dagster+ as SNOWFLAKE_PRIVATE_KEY (the PEM text; there's no key file there).
create user if not exists nfl_dagster_plus_svc
    type = service
    default_role = nfl_role
    default_warehouse = nfl_wh
    default_namespace = nfl.raw
    comment = 'nfl-dagster pipeline on Dagster+ Serverless';
alter user nfl_dagster_plus_svc set rsa_public_key = '<DAGSTER_PLUS_PUBLIC_KEY>';
grant role nfl_role to user nfl_dagster_plus_svc;

-- Let your own login use the role too, to browse the data in Snowsight.
grant role nfl_role to user <YOUR_USERNAME>;

-- Let the role create databases, so it can own the dev clone (NFL_DEV) it creates with
-- `make clone-dev`: create or replace database NFL_DEV clone NFL.
grant create database on account to role nfl_role;

-- The raw schema, created as the role so the role owns it.
use role nfl_role;
create schema if not exists nfl.raw;
