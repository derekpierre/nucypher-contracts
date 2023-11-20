#!/usr/bin/python3

from ape import project

from deployment.constants import (
    CONSTRUCTOR_PARAMS_DIR,
    OZ_DEPENDENCY,
)
from deployment.params import Deployer

VERIFY = True
CONSTRUCTOR_PARAMS_FILEPATH = CONSTRUCTOR_PARAMS_DIR / "mainnet" / "root.yml"


def main():

    deployer = Deployer.from_yaml(
        filepath=CONSTRUCTOR_PARAMS_FILEPATH,
        verify=VERIFY
    )

    _ = deployer.deploy(project.TACoApplication)  # FIXME

    proxy = deployer.deploy(OZ_DEPENDENCY.TransparentUpgradeableProxy)
    taco_application = deployer.proxy(project.TACoApplication, proxy)

    deployer.transact(taco_application.initialize)

    polygon_root = deployer.deploy(project.PolygonRoot)
    deployer.transact(taco_application.setChildApplication, polygon_root.address)

    deployer.transact(taco_application.transferOwnership, deployer.constants["THRESHOLD_COUNCIL"])

    deployments = [
        # proxy only (implementation has same contract name so not included)
        taco_application,
        polygon_root,
    ]

    deployer.finalize(deployments=deployments)
