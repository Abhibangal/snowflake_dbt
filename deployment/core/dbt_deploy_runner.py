"""
Author  : Abhijit Bangal
Project : Snowflake CI/CD Framework

Deploy the local dbt project to Snowflake with `snow dbt deploy`.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from jinja2 import Environment

from deployment.core.jinja_vars import (
    build_databases,
    build_dbt_vars,
    build_warehouses,
    get_database_layers,
)


def _snow_executable() -> str:
    """Return the Snowflake CLI path installed in the current environment."""

    executable = shutil.which("snow")

    if executable:
        return executable

    venv_executable = Path(sys.executable).parent / "snow"

    if venv_executable.exists():
        return str(venv_executable)

    raise RuntimeError(
        "Snowflake CLI (`snow`) not found. Install requirements.txt before deploying."
    )


class DbtDeployRunner:
    """Render env-specific dbt YAML and publish the dbt project object."""

    COPY_IGNORE_NAMES = frozenset(
        {
            "target",
            "dbt_packages",
            "dbt_modules",
            "logs",
            "__pycache__",
            ".user.yml",
        }
    )

    @staticmethod
    def _copy_ignore(src, names, *unused):
        """Ignore dbt artifacts. *unused keeps this compatible with Python 3.14 copytree."""

        return [name for name in names if name in DbtDeployRunner.COPY_IGNORE_NAMES]

    RENDER_SUFFIXES = {".yml", ".yaml"}

    def __init__(self, deployment_config, logger, environment, dry_run=False):
        self.deployment_config = deployment_config
        self.logger = logger
        self.environment = environment
        self.dry_run = dry_run

    def execute(self):
        """Upload the dbt project and create or version the Snowflake object."""

        if not self.deployment_config.get("features", {}).get("dbt_deploy", False):
            self.logger.info("dbt deploy disabled.")
            return

        dbt_config = self.deployment_config.get("dbt", {})
        source_dir = Path(dbt_config.get("project_dir", "dbt"))

        if not (source_dir / "dbt_project.yml").is_file():
            raise FileNotFoundError(
                f"dbt project not found at {source_dir / 'dbt_project.yml'}."
            )

        dbt_vars = build_dbt_vars(self.environment, self.deployment_config)
        render_vars = self._render_vars(dbt_vars)

        self.logger.info(
            f"Project : {dbt_vars['dbt_project_name']} -> "
            f"{dbt_vars['dbt_database']}.{dbt_vars['dbt_schema']} "
            f"(target={dbt_vars['dbt_target']})"
        )

        with tempfile.TemporaryDirectory(prefix="dbt-deploy-") as temp_dir:
            rendered_dir = Path(temp_dir) / "project"
            shutil.copytree(
                source_dir,
                rendered_dir,
                ignore=self._copy_ignore,
                dirs_exist_ok=False,
            )
            self._render_project_files(rendered_dir, render_vars)

            command = self._build_command(dbt_config, dbt_vars, rendered_dir)

            if self.dry_run:
                self.logger.info(
                    "dbt deploy dry-run: skipping `snow dbt deploy`. Command would be:"
                )
                self.logger.info(" ".join(command))
                return

            self._run(command)

        self.logger.info("snow dbt deploy finished.")

    def _render_vars(self, dbt_vars: dict) -> dict:
        databases = build_databases(
            self.environment,
            get_database_layers(self.deployment_config),
        )
        warehouses = build_warehouses(self.environment, self.deployment_config)

        return {
            "databases": databases,
            "warehouses": warehouses,
            "environment": self.environment,
            **dbt_vars,
        }

    def _render_project_files(self, project_dir: Path, render_vars: dict) -> None:
        """
        Replace {{ databases.* }} from deployment.yml using the branch environment.
        Only YAML is rendered so model SQL like {{ ref() }} is left intact.
        """

        jinja_env = Environment()

        for path in sorted(project_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in self.RENDER_SUFFIXES:
                continue

            original = path.read_text(encoding="utf-8")
            if "{{" not in original:
                continue

            rendered = jinja_env.from_string(original).render(**render_vars)
            path.write_text(
                rendered + ("" if rendered.endswith("\n") else "\n"),
                encoding="utf-8",
            )
            self.logger.info(
                f"Rendered dbt YAML from deployment.yml ({self.environment}): "
                f"{path.relative_to(project_dir)}"
            )

    def _build_command(
        self,
        dbt_config: dict,
        dbt_vars: dict,
        source_dir: Path,
    ) -> list[str]:
        snowflake_settings = self.deployment_config["snowflake"]

        command = [
            _snow_executable(),
            "dbt",
            "deploy",
            dbt_vars["dbt_project_name"],
            "--source",
            str(source_dir),
            "--profiles-dir",
            str(source_dir),
            "--default-target",
            dbt_vars["dbt_target"],
            "--temporary-connection",
            "--account",
            snowflake_settings["account"],
            "--user",
            snowflake_settings["user"],
            "--authenticator",
            "SNOWFLAKE_JWT",
            "--private-key-file",
            snowflake_settings["private_key_path"],
            "--role",
            snowflake_settings["role"],
            "--warehouse",
            snowflake_settings["warehouse"],
            "--database",
            dbt_vars["dbt_database"],
            "--schema",
            dbt_vars["dbt_schema"],
        ]

        dbt_version = dbt_config.get("dbt_version")
        if dbt_version:
            command.extend(["--dbt-version", str(dbt_version)])

        if dbt_config.get("install_local_deps"):
            command.append("--install-local-deps")

        for integration in dbt_config.get("external_access_integrations") or []:
            command.extend(["--external-access-integration", integration])

        return command

    def _run(self, command: list[str]) -> None:
        snowflake_settings = self.deployment_config["snowflake"]
        env = os.environ.copy()

        passphrase = snowflake_settings.get("private_key_passphrase", "")
        passphrase = passphrase.strip() if isinstance(passphrase, str) else ""

        if passphrase:
            env["SNOWFLAKE_PRIVATE_KEY_FILE_PWD"] = passphrase

        self.logger.info(
            f"Running snow dbt deploy for {command[3]} from rendered project files."
        )

        result = subprocess.run(
            command,
            text=True,
            env=env,
            capture_output=True,
        )

        if result.stdout:
            for line in result.stdout.splitlines():
                self.logger.info(line)

        if result.returncode != 0:
            if result.stderr:
                for line in result.stderr.splitlines():
                    self.logger.error(line)

            raise RuntimeError(
                "snow dbt deploy failed. Review Snowflake CLI output above."
            )
