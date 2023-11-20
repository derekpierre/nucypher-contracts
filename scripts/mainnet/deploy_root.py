#!/usr/bin/python3

from ape import project

from deployment.constants import CONSTRUCTOR_PARAMS_DIR
from deployment.params import Deployer

VERIFY = False  # TODO enable for mainnet?
CONSTRUCTOR_PARAMS_FILEPATH = CONSTRUCTOR_PARAMS_DIR / "mainnet" / "root.yml"

THRESHOLD_COUNCIL_ETH_MAINNET = "0x9F6e831c8F8939DC0C830C6e492e7cEf4f9C2F5f"


def main():
    deployer = Deployer.from_yaml(filepath=CONSTRUCTOR_PARAMS_FILEPATH, verify=VERIFY)

    taco_application = deployer.deploy(project.TACoApplication)

    polygon_root = deployer.deploy(project.PolygonRoot)

    # Need to set child application before transferring ownership
    deployer.transact(taco_application.setChildApplication, polygon_root.address)
    deployer.transact(taco_application.transferOwnership, THRESHOLD_COUNCIL_ETH_MAINNET)

    deployments = [
        taco_application,
        polygon_root,
    ]

    deployer.finalize(deployments=deployments)
