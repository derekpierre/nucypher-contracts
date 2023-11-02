#!/usr/bin/python3

from ape import project
from deployment.constants import CONSTRUCTOR_PARAMS_DIR, OZ_DEPENDENCY
from deployment.params import Deployer

VERIFY = False
CONSTRUCTOR_PARAMS_FILEPATH = CONSTRUCTOR_PARAMS_DIR / "dashboard" / "root.yml"


def main():
    """
    This script deploys only the TACo Root Application for Dashboard development.

    """

    deployer = Deployer.from_yaml(filepath=CONSTRUCTOR_PARAMS_FILEPATH, verify=VERIFY)
    proxy = deployer.deploy(OZ_DEPENDENCY.TransparentUpgradeableProxy)
    taco_application = deployer.proxy(project.TACoApplication, proxy)

    deployments = [
        taco_application,
    ]

    deployer.finalize(deployments=deployments)
