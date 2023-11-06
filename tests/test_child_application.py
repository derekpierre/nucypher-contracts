"""
This file is part of nucypher.

nucypher is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

nucypher is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with nucypher.  If not, see <https://www.gnu.org/licenses/>.
"""
import ape
import pytest
from ape.utils import ZERO_ADDRESS
from eth_utils import to_checksum_address
from web3 import Web3

OPERATOR_SLOT = 0
CONFIRMATION_SLOT = 2

MIN_AUTHORIZATION = Web3.to_wei(40_000, "ether")


@pytest.fixture()
def root_application(project, creator):
    contract = project.RootApplicationForTACoChildApplicationMock.deploy(sender=creator)
    return contract


@pytest.fixture()
def child_application(project, creator, root_application, oz_dependency):
    contract = project.TACoChildApplication.deploy(
        root_application.address, MIN_AUTHORIZATION, sender=creator
    )

    proxy = oz_dependency.TransparentUpgradeableProxy.deploy(
        contract.address,
        creator,
        b"",
        sender=creator,
    )
    proxy_contract = project.TACoChildApplication.at(proxy.address)
    root_application.setChildApplication(proxy_contract.address, sender=creator)

    return proxy_contract


@pytest.fixture()
def coordinator(project, child_application, creator):
    contract = project.CoordinatorForTACoChildApplicationMock.deploy(
        child_application, sender=creator
    )
    child_application.initialize(contract.address, sender=creator)
    return contract


def test_update_operator(accounts, root_application, child_application):
    (
        creator,
        staking_provider_1,
        staking_provider_2,
        operator_1,
        operator_2,
        *everyone_else,
    ) = accounts[0:]

    # Call to update operator can be done only from root app
    with ape.reverts("Caller must be the root application"):
        child_application.updateOperator(staking_provider_1, operator_1, sender=creator)

    # First bonding of operator
    tx = root_application.updateOperator(staking_provider_1, operator_1, sender=creator)
    assert child_application.stakingProviderFromOperator(operator_1) == staking_provider_1
    assert child_application.stakingProviderInfo(staking_provider_1)[OPERATOR_SLOT] == operator_1
    assert not child_application.stakingProviderInfo(staking_provider_1)[CONFIRMATION_SLOT]
    assert child_application.getStakingProvidersLength() == 1

    assert tx.events == [
        child_application.OperatorUpdated(stakingProvider=staking_provider_1, operator=operator_1)
    ]

    # No active stakingProviders before confirmation
    all_locked, staking_providers = child_application.getActiveStakingProviders(0, 0)
    assert all_locked == 0
    assert len(staking_providers) == 0

    # Rebond operator
    tx = root_application.updateOperator(staking_provider_1, operator_2, sender=creator)
    assert child_application.stakingProviderFromOperator(operator_2) == staking_provider_1
    assert child_application.stakingProviderFromOperator(operator_1) == ZERO_ADDRESS
    assert child_application.stakingProviderInfo(staking_provider_1)[OPERATOR_SLOT] == operator_2
    assert not child_application.stakingProviderInfo(operator_2)[CONFIRMATION_SLOT]
    assert not child_application.stakingProviderInfo(operator_1)[CONFIRMATION_SLOT]
    assert child_application.getStakingProvidersLength() == 1

    assert tx.events == [
        child_application.OperatorUpdated(stakingProvider=staking_provider_1, operator=operator_2)
    ]

    # Unbond operator
    tx = root_application.updateOperator(staking_provider_1, ZERO_ADDRESS, sender=creator)
    assert child_application.stakingProviderFromOperator(operator_2) == ZERO_ADDRESS
    assert child_application.stakingProviderInfo(staking_provider_1)[OPERATOR_SLOT] == ZERO_ADDRESS
    assert not child_application.stakingProviderInfo(operator_2)[CONFIRMATION_SLOT]
    assert child_application.stakingProviderFromOperator(ZERO_ADDRESS) == ZERO_ADDRESS
    assert child_application.getStakingProvidersLength() == 1

    assert tx.events == [
        child_application.OperatorUpdated(stakingProvider=staking_provider_1, operator=ZERO_ADDRESS)
    ]

    # Bonding from another address
    tx = root_application.updateOperator(staking_provider_2, operator_1, sender=creator)
    assert child_application.stakingProviderFromOperator(operator_1) == staking_provider_2
    assert child_application.stakingProviderInfo(staking_provider_2)[OPERATOR_SLOT] == operator_1
    assert not child_application.stakingProviderInfo(operator_1)[CONFIRMATION_SLOT]
    assert child_application.getStakingProvidersLength() == 2

    assert tx.events == [
        child_application.OperatorUpdated(stakingProvider=staking_provider_2, operator=operator_1)
    ]


def test_update_authorization(accounts, root_application, child_application):
    creator, staking_provider, *everyone_else = accounts[0:]
    value = Web3.to_wei(40_000, "ether")

    # Call to update auhtorization can be done only from root app
    with ape.reverts("Caller must be the root application"):
        child_application.updateAuthorization(staking_provider, value, sender=creator)

    # First increazing of authorization
    tx = root_application.updateAuthorization(staking_provider, value, sender=creator)
    assert child_application.authorizedStake(staking_provider) == value
    assert tx.events == [
        child_application.AuthorizationUpdated(stakingProvider=staking_provider, amount=value)
    ]

    # Deauthorization imitation
    tx = root_application.updateAuthorization(staking_provider, value // 2, sender=creator)
    assert child_application.authorizedStake(staking_provider) == value // 2
    assert tx.events == [
        child_application.AuthorizationUpdated(stakingProvider=staking_provider, amount=value // 2)
    ]

    # Increazing of authorization again
    tx = root_application.updateAuthorization(staking_provider, value, sender=creator)
    assert child_application.authorizedStake(staking_provider) == value
    assert tx.events == [
        child_application.AuthorizationUpdated(stakingProvider=staking_provider, amount=value)
    ]

    # Full deauthorization
    tx = root_application.updateAuthorization(staking_provider, 0, sender=creator)
    assert child_application.authorizedStake(staking_provider) == 0
    assert tx.events == [
        child_application.AuthorizationUpdated(stakingProvider=staking_provider, amount=0)
    ]


def test_confirm_address(accounts, root_application, child_application, coordinator):
    (
        creator,
        staking_provider,
        operator,
        other_staking_provier,
        other_operator,
        *everyone_else,
    ) = accounts[0:]
    value = Web3.to_wei(40_000, "ether")

    # Call to confirm operator address can be done only from coordinator
    with ape.reverts("Only Coordinator allowed to confirm operator"):
        child_application.confirmOperatorAddress(operator, sender=creator)

    # Can't confirm operator address without bonding with staking provider
    with ape.reverts("Authorization must be greater than minimum"):
        coordinator.confirmOperatorAddress(operator, sender=creator)

    # First bonding of operator
    root_application.updateOperator(staking_provider, operator, sender=creator)
    assert child_application.stakingProviderFromOperator(operator) == staking_provider
    assert child_application.stakingProviderInfo(staking_provider)[OPERATOR_SLOT] == operator
    assert not child_application.stakingProviderInfo(staking_provider)[CONFIRMATION_SLOT]
    assert child_application.getStakingProvidersLength() == 1

    # Can't confirm operator address without authorized amount
    with ape.reverts("Authorization must be greater than minimum"):
        coordinator.confirmOperatorAddress(operator, sender=creator)

    # Can't confirm operator address with too low amount
    root_application.updateAuthorization(staking_provider, MIN_AUTHORIZATION - 1, sender=creator)
    with ape.reverts("Authorization must be greater than minimum"):
        coordinator.confirmOperatorAddress(operator, sender=creator)

    # Confirm operator address
    root_application.updateAuthorization(staking_provider, value, sender=creator)
    tx = coordinator.confirmOperatorAddress(operator, sender=creator)
    assert child_application.stakingProviderInfo(staking_provider)[CONFIRMATION_SLOT]
    assert root_application.confirmations(operator)
    assert tx.events == [
        child_application.OperatorConfirmed(stakingProvider=staking_provider, operator=operator)
    ]

    # After confirmation operator is becoming active
    all_locked, staking_providers = child_application.getActiveStakingProviders(0, 0)
    assert all_locked == value
    assert len(staking_providers) == 1
    assert to_checksum_address(staking_providers[0][0]) == staking_provider
    assert staking_providers[0][1] == value

    # Can't confirm twice
    with ape.reverts("Can't confirm same operator twice"):
        coordinator.confirmOperatorAddress(operator, sender=creator)

    # Confirm another operator
    root_application.updateAuthorization(other_staking_provier, value, sender=creator)
    root_application.updateOperator(other_staking_provier, other_staking_provier, sender=creator)
    coordinator.confirmOperatorAddress(other_staking_provier, sender=creator)
    assert child_application.stakingProviderInfo(other_staking_provier)[CONFIRMATION_SLOT]
    assert root_application.confirmations(other_staking_provier)
    assert child_application.getStakingProvidersLength() == 2

    # After confirmation operator is becoming active
    all_locked, staking_providers = child_application.getActiveStakingProviders(0, 0)
    assert all_locked == 2 * value
    assert len(staking_providers) == 2
    assert to_checksum_address(staking_providers[0][0]) == staking_provider
    assert to_checksum_address(staking_providers[1][0]) == other_staking_provier
    assert staking_providers[0][1] == value
    assert staking_providers[1][1] == value
    all_locked, staking_providers = child_application.getActiveStakingProviders(1, 1)
    assert all_locked == value
    assert len(staking_providers) == 1
    assert to_checksum_address(staking_providers[0][0]) == other_staking_provier
    assert staking_providers[0][1] == value

    # Changing operator resets confirmation
    root_application.updateOperator(other_staking_provier, other_operator, sender=creator)
    assert child_application.stakingProviderFromOperator(other_operator) == other_staking_provier
    assert (
        child_application.stakingProviderInfo(other_staking_provier)[OPERATOR_SLOT]
        == other_operator
    )
    assert not child_application.stakingProviderInfo(other_staking_provier)[CONFIRMATION_SLOT]
    assert child_application.getStakingProvidersLength() == 2

    # Resetting operator removes from active list before next confirmation
    all_locked, staking_providers = child_application.getActiveStakingProviders(1, 0)
    assert all_locked == 0
    assert len(staking_providers) == 0

    root_application.updateAuthorization(staking_provider, value - 1, sender=creator)
    all_locked, staking_providers = child_application.getActiveStakingProviders(0, 0)
    assert all_locked == 0
    assert len(staking_providers) == 0
