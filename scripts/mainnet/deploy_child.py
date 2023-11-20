#!/usr/bin/python3

from ape import project

from deployment.constants import (
    CONSTRUCTOR_PARAMS_DIR,
    OZ_DEPENDENCY,
)
from deployment.params import Deployer

VERIFY = False # FIXMEEEEEEE
CONSTRUCTOR_PARAMS_FILEPATH = CONSTRUCTOR_PARAMS_DIR / "mainnet" / "child.yml"


def main():

    deployer = Deployer.from_yaml(filepath=CONSTRUCTOR_PARAMS_FILEPATH, verify=VERIFY)

    polygon_child = deployer.deploy(project.PolygonChild)

    taco_child_application = deployer.deploy(project.TACoChildApplication)

    deployer.transact(polygon_child.setChildApplication, taco_child_application.address)

    # TBD: proxy_admin.transferOwnership(Council) o mejor hacerlo en el constructor del proxy
    # TBD: deployer.transact(polygon_child.renounceOwnership)

    coordinator = deployer.deploy(project.Coordinator)

    deployer.transact(taco_child_application.initialize, coordinator.address)

    

    # Grant TREASURY_ROLE to Treasury Guild Multisig on Polygon (0xc3Bf49eBA094AF346830dF4dbB42a07dE378EeB6)
    TREASURY_ROLE = coordinator.TREASURY_ROLE()
    deployer.transact(coordinator.grantRole, TREASURY_ROLE, deployer.constants.TREASURY_GUILD_ON_POLYGON)

    # Grant INITIATOR_ROLE to Integrations Guild and BetaProgramInitiator
    INITIATOR_ROLE = coordinator.INITIATOR_ROLE()
    deployer.transact(coordinator.grantRole, INITIATOR_ROLE, deployer.constants.TREASURY_GUILD_ON_POLYGON)  # FIXME
    # Change Coordinator admin to Council on Polygon

    global_allow_list = deployer.deploy(project.GlobalAllowList)

    deployments = [
        polygon_child,
        taco_child_application,
        coordinator,
        global_allow_list,
    ]

    deployer.finalize(deployments=deployments)
