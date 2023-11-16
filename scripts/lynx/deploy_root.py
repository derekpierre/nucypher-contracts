#!/usr/bin/python3

from ape import project

from deployment.constants import CONSTRUCTOR_PARAMS_DIR
from deployment.params import Deployer

VERIFY = False
CONSTRUCTOR_PARAMS_FILEPATH = CONSTRUCTOR_PARAMS_DIR / "lynx" / "root.yml"


def main():
    """
    This script deploys only the Proxied Lynx TACo Root Application.

    September 25, 2023, Deployment:
    ape-run deploy_lynx_root --network etherscan:goerli:infura
    ape-etherscan             0.6.10
    ape-infura                0.6.3
    ape-polygon               0.6.5
    ape-solidity              0.6.9
    eth-ape                   0.6.20

    November 16, 2023, Update:
    ape-etherscan             0.6.10
    ape-infura                0.6.4
    ape-polygon               0.6.6
    ape-solidity              0.6.9
    eth-ape                   0.6.20
    """

    deployer = Deployer.from_yaml(filepath=CONSTRUCTOR_PARAMS_FILEPATH, verify=VERIFY)

    # reward_token = deployer.deploy(project.LynxStakingToken)

    mock_threshold_staking = project.TestnetThresholdStaking.at(
        "0xcdD63981c8f4a2A684d102f7d7693A1c326CDd33"
    )  # deployer.deploy(project.TestnetThresholdStaking)

    taco_application = deployer.deploy(project.TACoApplication)

    deployer.transact(mock_threshold_staking.setApplication, taco_application.address)

    mock_polygon_root = deployer.deploy(project.MockPolygonRoot)
    deployer.transact(taco_application.setChildApplication, mock_polygon_root.address)

    deployments = [
        # reward_token,
        # mock_threshold_staking,
        taco_application,
        mock_polygon_root,
    ]

    deployer.finalize(deployments=deployments)
