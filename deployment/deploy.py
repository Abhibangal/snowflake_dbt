"""
Author  : Abhijit Bangal
Project : Snowflake CI/CD Framework

Deployment Entry Point
"""

import argparse
import os
import sys

from deployment.core.config_loader import load_yaml
from deployment.core.logger import Logger
from deployment.validation.validate import Validator


def parse_args():
    parser = argparse.ArgumentParser(
        description="Deploy Snowflake objects using SchemaChange."
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run repository validations without connecting to Snowflake.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and run SchemaChange in dry-run mode.",
    )
    parser.add_argument(
        "--environment",
        choices=["DEV", "PROD"],
        help="Override environment detection (defaults to branch mapping).",
    )
    parser.add_argument(
        "--base-ref",
        help="Git base ref for immutable migration validation (PR workflows).",
    )
    parser.add_argument(
        "--skip-version-assign",
        action="store_true",
        help="Skip automatic V__ version assignment (validation-only / dry runs).",
    )
    parser.add_argument(
        "--assign-versions-only",
        action="store_true",
        help="Assign V__ migration versions and exit without deploying.",
    )
    return parser.parse_args()


def determine_environment(override=None):
    if override:
        return override

    branch = os.getenv("GITHUB_REF_NAME")

    if not branch:
        github_ref = os.getenv("GITHUB_REF", "")
        branch = github_ref.rsplit("/", maxsplit=1)[-1]

    if branch == "dev":
        return "DEV"

    if branch == "main":
        return "PROD"

    raise ValueError(
        f"Unsupported branch '{branch}'. Deployments are allowed only from "
        "dev or main, or pass --environment explicitly."
    )


def main():
    args = parse_args()

    deployment_config = load_yaml("deployment/config/deployment.yml")
    schemachange_config = load_yaml(
        "deployment/config/schemachange-config.yml"
    )

    log_level = deployment_config.get("logging", {}).get("level", "INFO")
    logger = Logger(log_level=log_level)

    logger.info("-----------------------------------------")
    logger.info("Snowflake Deployment Started")
    logger.info("-----------------------------------------")

    should_assign_versions = (
        not args.skip_version_assign
        and not args.validate_only
    ) or args.assign_versions_only

    if should_assign_versions:
        from deployment.core.version_assigner import VersionAssigner

        VersionAssigner(logger, deployment_config).assign()

    if args.assign_versions_only:
        logger.info("Version assignment completed successfully.")
        return

    if deployment_config.get("features", {}).get("validate_before_deploy", True):
        Validator(logger, base_ref=args.base_ref).validate()

    if args.validate_only:
        logger.info("Validation-only run completed successfully.")
        return

    from deployment.core.dbt_deploy_runner import DbtDeployRunner
    from deployment.core.git_repository import GitRepository
    from deployment.core.schemachange_runner import SchemaChangeRunner
    from deployment.core.snowflake_connection import SnowflakeConnection

    environment = determine_environment(args.environment)
    logger.info(f"Deployment Environment : {environment}")

    snowflake = None

    try:
        fetch_git_enabled = deployment_config.get("features", {}).get(
            "fetch_git_repository",
            False,
        )

        def fetch_git_repository():
            nonlocal snowflake

            snowflake = SnowflakeConnection(deployment_config, logger)
            snowflake.connect()

            try:
                GitRepository(snowflake, logger, deployment_config).fetch()
            finally:
                snowflake.close()
                snowflake = None

        if fetch_git_enabled:
            fetch_git_repository()

        dry_run = args.dry_run or deployment_config["schemachange"].get(
            "dry_run",
            False,
        )

        if deployment_config.get("features", {}).get("dbt_deploy", False):
            logger.info("-----------------------------------------")
            logger.info("dbt Deployment Started")
            logger.info("-----------------------------------------")

            DbtDeployRunner(
                deployment_config,
                logger,
                environment,
                dry_run=dry_run,
            ).execute()

            logger.info("-----------------------------------------")
            logger.info("dbt Deployment Completed Successfully")
            logger.info("-----------------------------------------")

        logger.info("-----------------------------------------")
        logger.info("Snowflake Object Deployment Started")
        logger.info("-----------------------------------------")

        schemachange = SchemaChangeRunner(
            deployment_config,
            schemachange_config,
            logger,
            environment,
            dry_run=dry_run,
            git_refetch_callback=(
                fetch_git_repository if fetch_git_enabled else None
            ),
        )
        schemachange.execute()

        logger.info("-----------------------------------------")
        logger.info("Snowflake Object Deployment Completed Successfully")
        logger.info("-----------------------------------------")

    finally:
        if snowflake is not None:
            snowflake.close()

    logger.info("-----------------------------------------")
    logger.info("Deployment Completed Successfully")
    logger.info("-----------------------------------------")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Deployment failed: {exc}", file=sys.stderr)
        sys.exit(1)
