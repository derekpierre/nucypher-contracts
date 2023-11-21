#!/usr/bin/python3

from ape import project

from deployment.constants import CONSTRUCTOR_PARAMS_DIR
from deployment.params import Deployer

VERIFY = False  # TODO: switch to True for mainnet deployment?
CONSTRUCTOR_PARAMS_FILEPATH = CONSTRUCTOR_PARAMS_DIR / "mainnet" / "child.yml"

# Threshold Network - References:
# - https://docs.threshold.network/resources/contract-addresses/mainnet/threshold-dao
TREASURY_GUILD_ON_POLYGON = "0xc3Bf49eBA094AF346830dF4dbB42a07dE378EeB6"


def main():
    deployer = Deployer.from_yaml(filepath=CONSTRUCTOR_PARAMS_FILEPATH, verify=VERIFY)

    polygon_child = deployer.deploy(project.PolygonChild)

    taco_child_application = deployer.deploy(project.TACoChildApplication)

    deployer.transact(polygon_child.setChildApplication, taco_child_application.address)

    # TBD: deployer.transact(polygon_child.renounceOwnership)

    coordinator = deployer.deploy(project.Coordinator)
    deployer.transact(taco_child_application.initialize, coordinator.address)

    # Grant TREASURY_ROLE to Treasury Guild Multisig on Polygon
    TREASURY_ROLE = coordinator.TREASURY_ROLE()
    deployer.transact(coordinator.grantRole, TREASURY_ROLE, TREASURY_GUILD_ON_POLYGON)

    # Grant INITIATOR_ROLE to Integrations Guild and BetaProgramInitiator
    INITIATOR_ROLE = coordinator.INITIATOR_ROLE()
    deployer.transact(coordinator.grantRole, INITIATOR_ROLE, TREASURY_GUILD_ON_POLYGON)

    # Change Coordinator admin to Council on Polygon
    # TODO: David is that what you intended by the above comment?
    #  Not sure the length of the default delay in transferring admin role
    deployer.transact(coordinator.beginDefaultAdminTransfer, TREASURY_GUILD_ON_POLYGON)

    global_allow_list = deployer.deploy(project.GlobalAllowList)

    deployments = [
        polygon_child,
        taco_child_application,
        coordinator,
        global_allow_list,
    ]

    deployer.finalize(deployments=deployments)
