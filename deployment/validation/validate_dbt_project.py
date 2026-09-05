"""
Author  : Abhijit Bangal
Project : Snowflake CI/CD Framework

Validate the dbt project layout used by snow dbt deploy.
"""

from pathlib import Path


class DbtProjectValidator:

    def __init__(self, logger, deployment_config):
        self.logger = logger
        self.deployment_config = deployment_config

    def validate(self):
        if not self.deployment_config.get("features", {}).get("dbt_deploy", False):
            self.logger.info("dbt deploy disabled; skipping dbt project validation.")
            return

        self.logger.info("Validating dbt project for Snowflake deploy...")

        dbt_config = self.deployment_config.get("dbt", {})
        project_dir = Path(dbt_config.get("project_dir", "dbt"))
        missing = []

        if not project_dir.is_dir():
            missing.append(str(project_dir))
        else:
            for filename in ("dbt_project.yml", "profiles.yml"):
                path = project_dir / filename
                if not path.is_file():
                    missing.append(str(path))

            for folder in (
                "models",
                "models/raw",
                "models/transform",
                "models/consumption",
            ):
                path = project_dir / folder
                if not path.is_dir():
                    missing.append(str(path))

        task_dir = Path("snowflake") / "tasks" / dbt_config.get(
            "database_layer", "TRANSFORM"
        ) / dbt_config.get("schema", "POSTGRES")
        if not task_dir.is_dir():
            missing.append(str(task_dir))
        elif not any(task_dir.glob("R__*.sql")):
            missing.append(f"{task_dir} (missing R__*.sql task script)")

        if missing:
            self.logger.error(
                "dbt project validation failed. snow dbt deploy requires these paths:"
            )
            for path in missing:
                self.logger.error(path)
            raise ValueError("dbt project validation failed.")

        project_name = dbt_config.get("project_name", "DBT")
        schema = dbt_config.get("schema", "POSTGRES")
        self.logger.info(
            f"dbt project validation successful ({project_dir}, "
            f"object={project_name}, schema={schema})."
        )
