# Snowflake CI/CD Framework

Author : Abhijit Bangal

---

# Overview

This repository contains a reusable CI/CD framework for deploying Snowflake database objects and external Python ingestion code using GitHub Actions and the Snowflake SchemaChange library.

The framework has been designed with the following objectives:

- Single deployment framework for all Snowflake projects
- Environment independent SQL scripts
- Git based version control
- Automated deployments
- Automatic validation before deployment
- Support for Snowpark projects
- Support for external Python ingestion framework
- Metadata driven folder structure
- Config-driven grants per environment and layer (RAW / TRANSFORM / CONSUMPTION)
- Easy onboarding for new developers
- Scalable repository structure

The framework follows Infrastructure as Code (IaC) principles where every Snowflake object is stored in Git and deployed automatically using GitHub Actions.

---

# High Level Architecture

```
                GitHub Repository

                       │

         Merge into dev / main branch

                       │

              GitHub Actions Trigger

                       │

                 PR Validation

                       │

        Validate Repository Structure

                       │

        Validate SchemaChange Naming

                       │

                Deploy Pipeline

                       │

            Connect to Snowflake

                       │

      ALTER GIT REPOSITORY FETCH

                       │

          snow dbt deploy

                       │

          Execute SchemaChange

                       │

            Deploy Snowflake Objects

                       │

             Update Change History
```

---

# How It Works

This is the end-to-end flow from developer commit to Snowflake deployment.

## 1. Developer workflow

> **Conventions & Snowpark setup:** See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for file naming rules, Snowpark SP layout, and do's / don'ts.

1. Create a **feature branch** from `dev` or `main`.
2. Add or update SQL migrations under `snowflake/<object_type>/<database>/<schema>/`.
3. Open a **Pull Request** targeting `dev` or `main`.

## 2. Pull Request (before merge)

When a PR is opened or updated against `dev` or `main`, **PR Validation** runs automatically.

It checks:

- Repository folder structure
- Migration file naming (`V__*.sql` placeholders, `R__*.sql`)
- Duplicate version numbers among already-assigned `V*.*.*__*.sql` files
- No edits to already-deployed versioned migrations
- `access_roles` configuration when grant scripts exist
- No hardcoded `DEV_RAW` / `PROD_RAW` in views or dynamic tables (use `{{ databases.RAW }}`)
- No hardcoded `WH_DEV_*` / `WH_PROD_*` in dynamic tables or tasks (use `{{ warehouses.ELT }}`)
- `snowflake/streamlit/` and `snowflake/streamlit_apps/` structure when Streamlit apps exist
- Streamlit SQL uses `{{ git_repository }}`, `{{ git_branch }}`, and `{{ warehouses.* }}` (no hardcoded paths or warehouses)

This step does **not** connect to Snowflake. It blocks bad changes before merge.

## 3. Merge triggers deployment

When the PR is **merged** into `dev` or `main`, GitHub pushes to that branch and **Deploy** runs automatically.

| Branch merged into | Snowflake environment | Example database |
|---|---|---|
| `dev` | DEV | `DEV_RAW`, `DEV_TRANSFORM` |
| `main` | PROD | `PROD_RAW`, `PROD_TRANSFORM` |

Direct pushes to `dev` or `main` also trigger deploy (avoid — use PRs only).

## 4. What deploy does

1. **Validate** the repository again.
2. **Assign migration versions** — rename `V__*.sql` placeholders to the next repo-wide version (e.g. `V__create_emp.sql` → `V3.2.0__create_emp.sql`) and commit back to the branch.
3. **Connect** to Snowflake using GitHub secrets.
4. **Fetch** the Snowflake Git Repository (if enabled — for Snowpark SPs and Streamlit apps).
5. **Deploy the dbt project** with `snow dbt deploy` (creates or versions the Snowflake dbt project object from `dbt/`).
6. **Run SchemaChange** per folder target (tasks can `EXECUTE DBT PROJECT` because the object already exists):
   - Folder path `snowflake/tasks/TRANSFORM/POSTGRES/` → deploys to `DEV_TRANSFORM.POSTGRES`
   - Object types run in order: file formats → stages → streams → functions → … → **tasks** (`EXECUTE DBT PROJECT`) → snowpark → **streamlit** → **grants**
   - **Tables and views are not deployed by SchemaChange** — they are created by dbt models under `dbt/models/`
7. **Record** applied migrations in the change history table (`CONFIG_DB.SCHEMACHANGE.DEV_CHANGE_HISTORY` or PROD equivalent).

Each migration runs **once**. Repeatable scripts (`R__*.sql`) re-run only when their content changes.

## 5. Key rules

- Never commit directly to `dev` or `main` — always use a PR.
- Never edit a deployed `V*.sql` file — add a new **`V__description.sql`** placeholder instead.
- **Do not pick version numbers manually** — use `V__*.sql` placeholders; the deploy workflow assigns `V*.*.*__*.sql` automatically.
- Version numbers must be **unique across the entire repository** (enforced when versions are assigned).
- New database/schema folders are picked up automatically — no config changes needed.
- **Grants belong in `snowflake/grants/`** — do not add `GRANT` statements to table or stored procedure DDL files.
- **Streamlit Python** lives in `snowflake/streamlit_apps/`; **`CREATE STREAMLIT` SQL** lives in `snowflake/streamlit/`.
- Do not hardcode Git paths or `WH_DEV_*` / `WH_PROD_*` warehouse names in Streamlit SQL.

---

# dbt Projects on Snowflake

CI publishes `dbt/` with `snow dbt deploy` **before** SchemaChange. SchemaChange then creates `TASK_EXECUTE_DBT`, which runs `EXECUTE DBT PROJECT`.

| What | Where |
|---|---|
| dbt project | `dbt/` (`dbt_project.yml`, models, `profiles.yml` template) |
| Deploy config | `deployment/config/deployment.yml` → `dbt:` |
| Task that runs dbt | `snowflake/tasks/TRANSFORM/POSTGRES/R__task_execute_dbt.sql` |

On `dev` the object is `DEV_TRANSFORM.POSTGRES.DBT` (target `dev`). On `main` it is `PROD_TRANSFORM.POSTGRES.DBT` (target `prod`). Jinja in `dbt_project.yml` and `profiles.yml` (`{{ databases.* }}`, `{{ warehouses.ELT }}`) is rendered at deploy time — model SQL `{{ ref() }}` is not touched.

---

# Streamlit in Snowflake (SiS)

Streamlit apps follow the same two-artifact pattern as Snowpark stored procedures:

| What | Where | Deployed by |
|---|---|---|
| Python app code | `snowflake/streamlit_apps/<DB>/<SCHEMA>/<APP_NAME>/` | Snowflake Git Repository (referenced in SQL) |
| `CREATE STREAMLIT` SQL | `snowflake/streamlit/<DB>/<SCHEMA>/R__*.sql` | SchemaChange |
| Grants (optional) | `snowflake/grants/<DB>/<SCHEMA>/R__*.sql` | SchemaChange (last) |

> **Conventions:** See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for Streamlit naming rules and PR checklist.

## Folder structure

```
snowflake/
├── streamlit/CONSUMPTION/CUSTOMER_HUB/
│   └── R__create_customer_dashboard.sql
│
└── streamlit_apps/CONSUMPTION/CUSTOMER_HUB/
    └── CUSTOMER_DASHBOARD/
        └── streamlit_app.py
```

| Path | Deploy target (on `dev`) |
|---|---|
| `snowflake/streamlit/CONSUMPTION/CUSTOMER_HUB/` | `DEV_CONSUMPTION.CUSTOMER_HUB` |
| Git path for Python | `@<git_repo>/branches/dev/snowflake/streamlit_apps/CONSUMPTION/CUSTOMER_HUB/CUSTOMER_DASHBOARD/` |

On **main**, `{{ git_branch }}` resolves to `main` and the database becomes `PROD_CONSUMPTION`.

## Example Streamlit SQL

```sql
-- snowflake/streamlit/CONSUMPTION/CUSTOMER_HUB/R__create_customer_dashboard.sql

CREATE OR REPLACE STREAMLIT CUSTOMER_DASHBOARD
  FROM @{{ git_repository }}/branches/{{ git_branch }}/snowflake/streamlit_apps/CONSUMPTION/CUSTOMER_HUB/CUSTOMER_DASHBOARD/
  MAIN_FILE = 'streamlit_app.py'
  QUERY_WAREHOUSE = {{ warehouses.DEVELOPER }};
```

## Example Python app

```python
# snowflake/streamlit_apps/CONSUMPTION/CUSTOMER_HUB/CUSTOMER_DASHBOARD/streamlit_app.py

import streamlit as st
from snowflake.snowpark.context import get_active_session

session = get_active_session()
st.title("Customer Dashboard")

df = session.sql("SELECT * FROM CUSTOMERS LIMIT 100").to_pandas()
st.dataframe(df)
```

## Deploy flow

1. Developer pushes Python to `streamlit_apps/` and SQL to `streamlit/`.
2. PR validation checks folder structure and file naming.
3. On merge to `dev` or `main`:
   - `ALTER GIT REPOSITORY ... FETCH` runs (refreshes Python from Git).
   - SchemaChange deploys `CREATE STREAMLIT` SQL.
   - Grants deploy last (if any).

## Rules

- Use **`R__*.sql`** for Streamlit DDL (repeatable — re-runs when content changes).
- Keep **Python** in `streamlit_apps/`; keep **SQL** in `streamlit/`.
- Use **`{{ git_repository }}`** and **`{{ git_branch }}`** in SQL — never hardcode `dev` / `main` paths.
- Use **`{{ warehouses.DEVELOPER }}`** or **`{{ warehouses.ELT }}`** for `QUERY_WAREHOUSE` — never hardcode `WH_DEV_*` / `WH_PROD_*`.
- Folder names must be valid Snowflake identifiers: `CUSTOMER_DASHBOARD`, not `customer-dashboard`.
- Put **GRANT USAGE ON STREAMLIT** in `snowflake/grants/`, not inside the Streamlit SQL file.

## Optional grant example

```sql
-- snowflake/grants/CONSUMPTION/CUSTOMER_HUB/R__grant_customer_dashboard.sql

GRANT USAGE ON STREAMLIT CUSTOMER_DASHBOARD TO ROLE {{ grant_role }};
```

---

# Grants Management

Object privileges and ownership transfers are managed in Git under the **`grants`** folder and deployed **last**, after all objects exist.

## Folder structure

```
snowflake/grants/<database_layer>/<schema>/R__<description>.sql
```

Examples:

```
snowflake/grants/RAW/CUSTOMER_HUB/R__grant_emp_dept_sp.sql
snowflake/grants/TRANSFORM/HUBSPOT/R__grant_transform_objects.sql
```

The folder path uses the same database/schema mapping as other object types:

| Path | Deploy target (on `dev`) |
|---|---|
| `snowflake/grants/RAW/CUSTOMER_HUB/` | `DEV_RAW.CUSTOMER_HUB` |
| `snowflake/grants/TRANSFORM/HUBSPOT/` | `DEV_TRANSFORM.HUBSPOT` |

## Access roles (AR) per environment, layer, and schema

Grant target roles are **not hardcoded** in SQL. They are built automatically from the grants folder path and branch:

```text
AR_{ENV}_{LAYER}_{SCHEMA}_{PRIVILEGE}
```

| Part | Source | Example |
|---|---|---|
| `ENV` | Branch (`dev` → DEV, `main` → PROD) | `DEV` |
| `LAYER` | Database layer folder | `RAW`, `TRF`, `CON` |
| `SCHEMA` | Schema folder | `CUSTOMERHUB`, `HUBSPOT` |
| `PRIVILEGE` | Config default or Jinja | `RW`, `RO`, `ALL` |

Example: `snowflake/grants/RAW/CUSTOMER_HUB/` on **dev** → `AR_DEV_RAW_CUSTOMERHUB_RW`

Layer and schema abbreviations are configured in `deployment/config/deployment.yml`:

```yaml
access_roles:
  default_privilege: RW
  layer_codes:
    RAW: RAW
    TRANSFORM: TRF
    CONSUMPTION: CON
  schema_codes:
    CUSTOMER_HUB: CUSTOMERHUB
    HUBSPOT: HUBSPOT
    QUICKBOOKS: QUICKBOOKS
    ASANA: ASANA
    UTILS: SDT
```

Warehouses for dynamic tables and tasks are configured separately:

```yaml
warehouses:
  DEVELOPER:
    DEV: WH_DEV_DEVELOPER_XS
    PROD: WH_PROD_DEVELOPER_XS
  ELT:
    DEV: WH_DEV_ELT_XS
    PROD: WH_PROD_ELT_XS
```

| Privilege | Meaning |
|---|---|
| `ALL` | Full access to schema |
| `RW` | Read-write (default for `{{ grant_role }}`) |
| `RO` | Read-only |

## Jinja in grant scripts

SchemaChange injects these variables at deploy time:

| Variable | Description |
|---|---|
| `{{ git_repository }}` | Snowflake Git Repository object — use in **Streamlit** `FROM` paths and Snowpark SP `IMPORTS` |
| `{{ git_branch }}` | `dev` or `main` — use in **Streamlit** and Snowpark Git paths |
| `{{ grant_role }}` | Default access role for current grants folder (RW) — **recommended** |
| `{{ access_role }}` | Same as `{{ grant_role }}` |
| `{{ access_roles.RW }}` | Read-write role for current layer + schema |
| `{{ access_roles.RO }}` | Read-only role for current layer + schema |
| `{{ access_roles.ALL }}` | Full access role for current layer + schema |
| `{{ environment }}` | `DEV` or `PROD` |
| `{{ databases.RAW }}` | Resolves to `DEV_RAW` or `PROD_RAW` — use in **views / dynamic tables** |
| `{{ databases.TRANSFORM }}` | Resolves to `DEV_TRANSFORM` or `PROD_TRANSFORM` |
| `{{ databases.CONSUMPTION }}` | Resolves to `DEV_CONSUMPTION` or `PROD_CONSUMPTION` |
| `{{ warehouses.DEVELOPER }}` | Resolves to `WH_DEV_DEVELOPER_XS` or `WH_PROD_DEVELOPER_XS` — use in **dynamic tables / tasks / Streamlit** |
| `{{ warehouses.ELT }}` | Resolves to `WH_DEV_ELT_XS` or `WH_PROD_ELT_XS` — use in **dynamic tables / tasks / Streamlit** |

Example Streamlit app:

```sql
CREATE OR REPLACE STREAMLIT CUSTOMER_DASHBOARD
  FROM @{{ git_repository }}/branches/{{ git_branch }}/snowflake/streamlit_apps/CONSUMPTION/CUSTOMER_HUB/CUSTOMER_DASHBOARD/
  MAIN_FILE = 'streamlit_app.py'
  QUERY_WAREHOUSE = {{ warehouses.DEVELOPER }};
```

Example dynamic table:

```sql
CREATE OR REPLACE DYNAMIC TABLE DT_CUSTOMER_ORDERS
  TARGET_LAG = '1 hour'
  WAREHOUSE = {{ warehouses.ELT }}
AS
SELECT * FROM {{ databases.RAW }}.HUBSPOT.ORDERS;
```

Example task:

```sql
CREATE OR REPLACE TASK TASK_REFRESH_ORDERS
  WAREHOUSE = {{ warehouses.ELT }}
  SCHEDULE = 'USING CRON 0 * * * * UTC'
AS
  CALL SOME_PROC();
```

Example cross-layer view:

```sql
CREATE OR REPLACE VIEW VW_CUSTOMERS AS
SELECT * FROM {{ databases.RAW }}.HUBSPOT.CUSTOMERS;
```

On **dev** deploy this renders as `DEV_RAW.HUBSPOT.CUSTOMERS`; on **main** as `PROD_RAW.HUBSPOT.CUSTOMERS`.

Example grant script:

```sql
-- snowflake/grants/RAW/CUSTOMER_HUB/R__grant_emp_dept_sp.sql

GRANT OWNERSHIP ON PROCEDURE EMP_DEPT_SP()
    TO ROLE {{ grant_role }}
    COPY CURRENT GRANTS;
```

On a **dev** deploy this renders as:

```sql
GRANT OWNERSHIP ON PROCEDURE EMP_DEPT_SP()
    TO ROLE AR_DEV_RAW_CUSTOMERHUB_RW
    COPY CURRENT GRANTS;
```

## Rules

- Use **`R__*.sql`** repeatable scripts for grants (re-applied when content changes).
- Keep **`CREATE`** DDL in object folders (`tables/`, `storedprocedures/`, etc.).
- Keep **`GRANT`** / **`GRANT OWNERSHIP`** in `snowflake/grants/` only.
- Use `COPY CURRENT GRANTS` (not `COPY GRANTS`) for ownership transfers in Snowflake.
- PR validation checks that `access_roles` is configured when grant scripts exist.

---

# Repository Structure

```
snowflake-cicd/

│

├── .github/
│   └── workflows/
│       ├── deploy.yml
│       └── pr-validation.yml
│

├── deployment/
│
│   ├── config/
│   │      deployment.yml
│   │      schemachange-config.yml
│
│   ├── core/
│   │      logger.py
│   │      snowflake_connection.py
│   │      git_repository.py
│   │      schemachange_runner.py
│
│   ├── validation/
│   │      validate.py
│   │      validate_project_structure.py
│   │      validate_version_format.py
│   │      validate_grant_roles.py
│
│   └── deploy.py
│

├── snowflake/
│   ├── tables/
│   ├── views/
│   ├── storedprocedures/
│   ├── functions/
│   ├── streams/
│   ├── tasks/
│   ├── dynamic_tables/
│   ├── stages/
│   ├── file_formats/
│   ├── pipes/
│   ├── grants/
│   ├── snowpark/
│   ├── streamlit/
│   └── streamlit_apps/
│
├── python/
│
├── requirements.txt
│
├── README.md
│
└── .gitignore
```

---

# Repository Branch Strategy

Only two long-lived branches are maintained.

```
main

Production Environment
```

```
dev

Development Environment
```

No direct commits are allowed.

Every change must be submitted through a Pull Request.

---

# Environment Mapping

| Git Branch | Snowflake Environment |
|------------|----------------------|
| dev | DEV |
| main | PROD |

Example

Developer merges into

```
dev
```

Framework automatically deploys into

```
DEV
```

If merged into

```
main
```

Framework deploys into

```
PROD
```

No manual environment selection is required.

---

# Deployment Workflow

The deployment process consists of the following stages.

Step 1

Developer creates a Feature Branch.

↓

Step 2

Developer commits Snowflake SQL.

↓

Step 3

Developer raises Pull Request.

↓

Step 4

PR Validation runs.

↓

Step 5

Repository validations pass.

↓

Step 6

Pull Request merged into dev/main.

↓

Step 7

Deployment workflow starts.

↓

Step 8

Snowflake Git Repository fetches latest code.

↓

Step 9

SchemaChange deploys new migrations.

↓

Step 10

Deployment completed.

---

# Why SchemaChange?

SchemaChange is an open-source migration tool developed specifically for Snowflake.

It provides:

- Version controlled deployments
- Automatic migration tracking
- Rollback protection
- Repeatable scripts
- Ordered execution
- Deployment history

Instead of manually executing SQL scripts, SchemaChange ensures that every migration executes only once.

```
V1.0.0__create_customer.sql
```

will never execute again after successful deployment.

The execution history is maintained inside the SchemaChange History Table.

```
CHANGE_HISTORY
```
# SchemaChange Overview

SchemaChange is a database migration framework specifically designed for Snowflake.

Instead of manually executing SQL scripts, SchemaChange keeps track of every deployed migration inside a Change History table.

Whenever a deployment starts, SchemaChange performs the following steps:

1. Scan all SQL migration files.
2. Compare them against the Change History table.
3. Identify new migrations.
4. Execute only pending migrations.
5. Record successful execution in the Change History table.

This guarantees that a migration executes only once.

---

# How SchemaChange Works

Example

Repository contains:

```
V1.0.0__create_customer.sql

V1.0.1__add_customer_email.sql

V2.0.0__create_orders.sql
```

Suppose the Change History table contains

```
V1.0.0
```

During deployment,

SchemaChange will execute

```
V1.0.1__add_customer_email.sql

V2.0.0__create_orders.sql
```

and ignore

```
V1.0.0__create_customer.sql
```

because it has already been deployed.

---

# SchemaChange History Table

Every successful migration is recorded inside the Change History table.

Example

| Version | Description | Installed On |
|----------|-------------|--------------|
| V1.0.0 | create_customer | 2026-01-10 |
| V1.0.1 | add_customer_email | 2026-01-12 |
| V2.0.0 | create_orders | 2026-01-15 |

The framework maintains separate history tables for every environment.

Development

```
CONFIG_DB.SCHEMACHANGE.DEV_CHANGE_HISTORY
```

Production

```
CONFIG_DB.SCHEMACHANGE.PROD_CHANGE_HISTORY
```

This ensures that DEV and PROD deployments remain completely independent.

---

# Migration Types

SchemaChange supports two migration types.

## 1. Versioned Migration

Executed only once.

### Developer naming (what you commit in your PR)

Use a **placeholder** — no version number:

```
V__<description>.sql
```

Examples:

```
V__create_customer.sql
V__add_customer_email.sql
V__create_orders.sql
```

The **deploy workflow** renames these automatically before SchemaChange runs, for example:

```
V__create_customer.sql  →  V3.2.0__create_customer.sql
```

You do **not** need to calculate the next version number.

### Final naming (after deploy assigns versions)

```
V<version>__<description>.sql
```

Examples (assigned by CI):

```
V1.0.0__create_customer.sql
V1.0.1__add_customer_email.sql
V2.0.0__create_orders.sql
V2.0.1__add_order_date.sql
```

These files are executed exactly once.

### How version assignment works

1. Developer merges a PR containing `V__*.sql` file(s).
2. Deploy workflow runs `python -m deployment.assign_versions`.
3. Each placeholder gets the next **repo-wide** version (higher than any existing `V*.*.*` in the repository).
4. Workflow commits the renamed files (`ci: assign migration version numbers`).
5. SchemaChange deploys using the final versioned filenames.

Optional starting points for the **first** migration in a new schema are configured in `deployment/config/deployment.yml`:

```yaml
version_prefixes:
  RAW:
    CUSTOMER_HUB: "1.0.0"
    HUBSPOT: "2.0.0"
    QUICKBOOKS: "3.0.0"
```

After the first migration exists, new versions always increment from the current repository maximum.

---

## 2. Repeatable Migration

Executed whenever the file content changes.

Naming Convention

```
R__<description>.sql
```

Examples

```
R__customer_view.sql

R__sales_summary_view.sql

R__grant_emp_dept_sp.sql
```

Typical use cases

- Views
- Secure Views
- Materialized Views
- Stored Procedures
- Functions
- **Grants** (use `snowflake/grants/` — see [Grants Management](#grants-management))

Repeatable migrations are not version based.

Instead, SchemaChange calculates a checksum.

Whenever the checksum changes,

the migration executes again.

---

# Custom Versioning Strategy

Developers commit **`V__description.sql` placeholders**. The CI/CD pipeline assigns explicit **`V*.*.*__description.sql`** names before deploy.

The assigned numbers follow this convention:

```
V1.0.0
```

Each digit has a specific meaning.

```
V<SourceSystem>.<TableNumber>.<ChangeNumber>
```

---

Example

```
V1.0.0
```

means

```
Source System = 1

Table Number = 0

Change Number = 0
```

Suppose

Source System

```
Postgres
```

is assigned

```
1
```

First table

```
Customer
```

becomes

```
V1.0.0__create_customer.sql
```

Later,

developer adds

```
EMAIL
```

column.

They add a new placeholder in their PR:

```
V__add_customer_email.sql
```

After merge, CI assigns something like:

```
V1.0.1__add_customer_email.sql
```

Another change

```
PHONE
```

becomes

```
V1.0.2__add_customer_phone.sql
```

---

Now suppose

Orders

is the second table from Postgres.

Migration

```
V1.1.0__create_orders.sql
```

Later

```
ORDER_DATE
```

```
V1.1.1__add_order_date.sql
```

---

Suppose another source system

```
HubSpot
```

is assigned

```
2
```

Customer table

```
V2.0.0__create_customer.sql
```

Orders

```
V2.1.0__create_orders.sql
```

---

# Advantages

Using this convention,

a developer can immediately identify

- Source System
- Table
- Number of changes

without opening the SQL file.

---

# Version Allocation Strategy

| Source System | Version Range |
|--------------|---------------|
| Postgres | V1.x.x |
| HubSpot | V2.x.x |
| Salesforce | V3.x.x |
| SAP | V4.x.x |
| Oracle | V5.x.x |

This convention keeps migrations organized as the project grows.

---

# Naming Examples

## Create Table

```
V1.0.0__create_customer.sql
```

## Add Column

```
V1.0.1__add_customer_email.sql
```

## Modify Column

```
V1.0.2__modify_customer_name.sql
```

## Add Constraint

```
V1.0.3__add_customer_pk.sql
```

## Drop Column

```
V1.0.4__drop_customer_phone.sql
```

## New Table

```
V1.1.0__create_orders.sql
```

---

# Important Rules

✔ Never modify an already deployed Versioned Migration.

❌ Wrong

```
V1.0.0__create_customer.sql
```

editing after deployment.

✔ Correct

Create

```
V1.0.1__add_customer_email.sql
```

instead.

Versioned migrations are immutable.

Once deployed,

they should never be edited.
# Repository Structure

```
snowflake-cicd/

│
├── .github/
│   └── workflows/
│       ├── deploy.yml
│       └── pr-validation.yml
│
├── deployment/
│   ├── config/
│   │   ├── deployment.yml
│   │   └── schemachange-config.yml
│   │
│   ├── core/
│   │   ├── logger.py
│   │   ├── snowflake_connection.py
│   │   ├── git_repository.py
│   │   └── schemachange_runner.py
│   │
│   ├── validation/
│   │   ├── validate.py
│   │   ├── validate_project_structure.py
│   │   └── validate_version_format.py
│   │
│   └── deploy.py
│
├── snowflake/
│   ├── tables/
│   ├── views/
│   ├── storedprocedures/
│   ├── functions/
│   ├── streams/
│   ├── tasks/
│   ├── dynamic_tables/
│   ├── stages/
│   ├── file_formats/
│   ├── pipes/
│   ├── grants/
│   ├── snowpark/
│   ├── streamlit/
│   └── streamlit_apps/
│
├── python/
│   ├── framework/
│   ├── connectors/
│   ├── jobs/
│   ├── config/
│   └── utils/
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Repository Folder Description

| Folder | Purpose |
|---------|----------|
| `.github/workflows` | GitHub Actions workflows for PR validation and deployment |
| `deployment` | Complete CI/CD deployment framework |
| `deployment/config/deployment.yml` | Snowflake connection, deployment order, **access_roles**, **version_prefixes**, **warehouses** |
| `snowflake` | All Snowflake objects managed by SchemaChange |
| `snowflake/grants` | Repeatable grant/ownership scripts (deployed last) |
| `snowflake/streamlit` | `CREATE STREAMLIT` SQL (deployed via SchemaChange) |
| `snowflake/streamlit_apps` | Streamlit Python app code (sourced from Snowflake Git Repository) |
| `python` | External ingestion framework (runs outside Snowflake) |
| `requirements.txt` | Python dependencies for GitHub Actions |
| `.gitignore` | Ignore local, log, and sensitive files |
| `README.md` | Project documentation and developer guide |

---

This structure keeps responsibilities clear:

- **deployment/** → CI/CD engine
- **snowflake/** → Snowflake database objects
- **snowflake/grants/** → Privileges and ownership (config-driven roles)
- **python/** → External ingestion code
- **.github/** → GitHub automation

---