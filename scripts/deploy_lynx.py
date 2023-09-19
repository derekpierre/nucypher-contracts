#!/usr/bin/python3
import os
from pathlib import Path

from ape import project
from ape.cli import get_user_selected_account
from scripts.deployment import DeploymentConfig
from scripts.registry import registry_from_ape_deployments

PUBLISH = False

# TODO cleanup; uniqueness, existence etc.
DEPLOYMENT_REGISTRY_FILEPATH = Path(".").parent / "artifacts" / "lynx_testnet_registry.json"

CONFIG_FILE = Path(__file__).parent / "configs" / "lynx_config.json"


def main():
    """
    This script deploys the Lynx TACo Root Application,
    Lynx TACo Child Application, Lynx Ritual Token, and Lynx Coordinator.

    September 18, 2023, Goerli Deployment:
    ape run testnet deploy_lynx --network ethereum:goerli:<INFURA_URI>
    'LynxRootApplication' deployed to: 0x39F1061d68540F7eb57545C4C731E0945c167016
    'LynxTACoChildApplication' deployed to: 0x892a548592bA66dc3860F75d76cDDb488a838c35
    'Coordinator' deployed to: 0x18566d4590be23e4cb0a8476C80C22096C8c3418

    September 18, 2023, Mumbai Deployment:
     ape run testnet deploy_lynx --network polygon:mumbai:<INFURA_URI>
    'LynxRootApplication' deployed to: 0xb6400F55857716A3Ff863e6bE867F01F23C71793
    'LynxTACoChildApplication' deployed to: 0x3593f90b19F148FCbe7B00201f854d8839F33F86
    'Coordinator' deployed to: 0x4077ad1CFA834aEd68765dB0Cf3d14701a970a9a


    """

    try:
        import ape_etherscan  # noqa: F401
    except ImportError:
        raise ImportError("Please install the ape-etherscan plugin to use this script.")
    if not os.environ.get("ETHERSCAN_API_KEY"):
        raise ValueError("ETHERSCAN_API_KEY is not set.")

    deployer = get_user_selected_account()

    config = DeploymentConfig.from_file(CONFIG_FILE)
    config_context = {}

    # Lynx TACo Root Application
    LynxRootApplication = deployer.deploy(
        project.LynxRootApplication,
        *config.get_constructor_params(
            container=project.LynxRootApplication, context=config_context
        ),
        publish=PUBLISH,
    )
    config_context[LynxRootApplication.contract_type.name] = LynxRootApplication

    # Lynx TACo Child Application
    LynxTACoChildApplication = deployer.deploy(
        project.LynxTACoChildApplication,
        *config.get_constructor_params(
            container=project.LynxTACoChildApplication, context=config_context
        ),
        publish=PUBLISH,
    )
    config_context[LynxTACoChildApplication.contract_type.name] = LynxTACoChildApplication

    LynxRootApplication.setChildApplication(
        LynxTACoChildApplication.address,
        sender=deployer,
        publish=PUBLISH,
    )

    # Lynx Ritual Token
    LynxRitualToken = deployer.deploy(
        project.LynxRitualToken,
        *config.get_constructor_params(container=project.LynxRitualToken, context=config_context),
        publish=PUBLISH,
    )
    config_context[LynxRitualToken.contract_type.name] = LynxRitualToken

    # Lynx Coordinator
    Coordinator = deployer.deploy(
        project.Coordinator,
        *config.get_constructor_params(container=project.Coordinator, context=config_context),
        publish=PUBLISH,
    )
    config_context[Coordinator.contract_type.name] = Coordinator

    LynxTACoChildApplication.setCoordinator(Coordinator.address, sender=deployer)

    # list deployments
    deployments = list(config_context.values())

    registry_from_ape_deployments(
        deployments=deployments, output_filepath=DEPLOYMENT_REGISTRY_FILEPATH
    )
