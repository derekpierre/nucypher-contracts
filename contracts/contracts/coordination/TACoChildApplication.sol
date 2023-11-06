// SPDX-License-Identifier: AGPL-3.0-or-later

pragma solidity ^0.8.0;

import "@openzeppelin-upgradeable/contracts/access/AccessControlUpgradeable.sol";
import "@openzeppelin-upgradeable/contracts/proxy/utils/Initializable.sol";
import "./ITACoRootToChild.sol";
import "../../threshold/ITACoChildApplication.sol";
import "./ITACoChildToRoot.sol";
import "./Coordinator.sol";

/**
 * @title TACoChildApplication
 * @notice TACoChildApplication
 */
contract TACoChildApplication is ITACoRootToChild, ITACoChildApplication, Initializable {
    struct StakingProviderInfo {
        address operator;
        uint96 authorized;
        bool operatorConfirmed;
        uint248 index; // index in stakingProviders array + 1
    }

    ITACoChildToRoot public immutable rootApplication;
    address public coordinator;

    uint96 public immutable minimumAuthorization;

    mapping(address => StakingProviderInfo) public stakingProviderInfo;
    address[] public stakingProviders;
    mapping(address => address) public stakingProviderFromOperator;

    /**
     * @dev Checks caller is root application
     */
    modifier onlyRootApplication() {
        require(msg.sender == address(rootApplication), "Caller must be the root application");
        _;
    }

    constructor(ITACoChildToRoot _rootApplication, uint96 _minimumAuthorization) {
        require(
            address(_rootApplication) != address(0),
            "Address for root application must be specified"
        );
        require(_minimumAuthorization > 0, "Minimum authorization must be specified");
        rootApplication = _rootApplication;
        minimumAuthorization = _minimumAuthorization;
        _disableInitializers();
    }

    /**
     * @notice Initialize function for using with OpenZeppelin proxy
     */
    function initialize(address _coordinator) external initializer {
        require(coordinator == address(0), "Coordinator already set");
        require(_coordinator != address(0), "Coordinator must be specified");
        require(
            address(Coordinator(_coordinator).application()) == address(this),
            "Invalid coordinator"
        );
        coordinator = _coordinator;
    }

    function authorizedStake(address _stakingProvider) external view returns (uint96) {
        return stakingProviderInfo[_stakingProvider].authorized;
    }

    function updateOperator(
        address stakingProvider,
        address operator
    ) external override onlyRootApplication {
        _updateOperator(stakingProvider, operator);
    }

    function updateAuthorization(
        address stakingProvider,
        uint96 amount
    ) external override onlyRootApplication {
        _updateAuthorization(stakingProvider, amount);
    }

    function _updateOperator(address stakingProvider, address operator) internal {
        StakingProviderInfo storage info = stakingProviderInfo[stakingProvider];
        address oldOperator = info.operator;

        if (stakingProvider == address(0) || operator == oldOperator) {
            return;
        }

        if (info.index == 0) {
            stakingProviders.push(stakingProvider);
            info.index = uint248(stakingProviders.length);
        }

        info.operator = operator;
        // Update operator to provider mapping
        stakingProviderFromOperator[oldOperator] = address(0);
        if (operator != address(0)) {
            stakingProviderFromOperator[operator] = stakingProvider;
        }
        info.operatorConfirmed = false;
        // TODO placeholder to notify Coordinator

        emit OperatorUpdated(stakingProvider, operator);
    }

    function _updateAuthorization(address stakingProvider, uint96 amount) internal {
        StakingProviderInfo storage info = stakingProviderInfo[stakingProvider];
        uint96 fromAmount = info.authorized;

        if (stakingProvider != address(0) && amount != fromAmount) {
            info.authorized = amount;
            emit AuthorizationUpdated(stakingProvider, amount);
        }
    }

    function confirmOperatorAddress(address _operator) external override {
        require(msg.sender == coordinator, "Only Coordinator allowed to confirm operator");
        address stakingProvider = stakingProviderFromOperator[_operator];
        StakingProviderInfo storage info = stakingProviderInfo[stakingProvider];
        require(
            info.authorized >= minimumAuthorization,
            "Authorization must be greater than minimum"
        );
        // TODO maybe allow second confirmation, just do not send root call?
        require(!info.operatorConfirmed, "Can't confirm same operator twice");
        info.operatorConfirmed = true;
        emit OperatorConfirmed(stakingProvider, _operator);
        rootApplication.confirmOperatorAddress(_operator);
    }

    /**
     * @notice Return the length of the array of staking providers
     */
    function getStakingProvidersLength() external view returns (uint256) {
        return stakingProviders.length;
    }

    /**
     * @notice Get the value of authorized tokens for active providers as well as providers and their authorized tokens
     * @param _startIndex Start index for looking in providers array
     * @param _maxStakingProviders Max providers for looking, if set 0 then all will be used
     * @return allAuthorizedTokens Sum of authorized tokens for active providers
     * @return activeStakingProviders Array of providers and their authorized tokens.
     * Providers addresses stored as uint256
     * @dev Note that activeStakingProviders[0] is an array of uint256, but you want addresses.
     * Careful when used directly!
     */
    function getActiveStakingProviders(
        uint256 _startIndex,
        uint256 _maxStakingProviders
    )
        external
        view
        returns (uint256 allAuthorizedTokens, uint256[2][] memory activeStakingProviders)
    {
        uint256 endIndex = stakingProviders.length;
        require(_startIndex < endIndex, "Wrong start index");
        if (_maxStakingProviders != 0 && _startIndex + _maxStakingProviders < endIndex) {
            endIndex = _startIndex + _maxStakingProviders;
        }
        activeStakingProviders = new uint256[2][](endIndex - _startIndex);
        allAuthorizedTokens = 0;

        uint256 resultIndex = 0;
        for (uint256 i = _startIndex; i < endIndex; i++) {
            address stakingProvider = stakingProviders[i];
            StakingProviderInfo storage info = stakingProviderInfo[stakingProvider];
            uint256 eligibleAmount = info.authorized;
            if (eligibleAmount < minimumAuthorization || !info.operatorConfirmed) {
                continue;
            }
            activeStakingProviders[resultIndex][0] = uint256(uint160(stakingProvider));
            activeStakingProviders[resultIndex++][1] = eligibleAmount;
            allAuthorizedTokens += eligibleAmount;
        }
        assembly {
            mstore(activeStakingProviders, resultIndex)
        }
    }
}

contract TestnetTACoChildApplication is AccessControlUpgradeable, TACoChildApplication {
    bytes32 public constant UPDATE_ROLE = keccak256("UPDATE_ROLE");

    constructor(
        ITACoChildToRoot _rootApplication,
        uint96 _minimumAuthorization
    ) TACoChildApplication(_rootApplication, _minimumAuthorization) {}

    function initialize(address _coordinator, address[] memory updaters) external initializer {
        coordinator = _coordinator;
        for (uint256 i = 0; i < updaters.length; i++) {
            _grantRole(UPDATE_ROLE, updaters[i]);
        }
    }

    function forceUpdateOperator(
        address stakingProvider,
        address operator
    ) external onlyRole(UPDATE_ROLE) {
        _updateOperator(stakingProvider, operator);
    }

    function forceUpdateAuthorization(
        address stakingProvider,
        uint96 amount
    ) external onlyRole(UPDATE_ROLE) {
        _updateAuthorization(stakingProvider, amount);
    }
}
