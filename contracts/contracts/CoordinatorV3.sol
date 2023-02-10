// SPDX-License-Identifier: AGPL-3.0-or-later

pragma solidity ^0.8.0;

import "./proxy/Upgradeable.sol";

/**
* @title CoordinatorV3
* @notice Coordination layer for DKG-TDec
*/
contract CoordinatorV3 is Upgradeable {

    // DKG state signals
    event StartRitual(uint32 indexed ritualId, address[] nodes);
    event StartTranscriptRound(uint32 indexed ritualId);
    event StartAggregationRound(uint32 indexed ritualId);
    event EndRitual(uint32 indexed ritualId, RitualStatus status);

    // Node events
    event TranscriptPosted(uint32 indexed ritualId, address indexed node, bytes32 transcriptDigest);
    event AggregationPosted(uint32 indexed ritualId, address indexed node);

    // Admin events
    event TimeoutChanged(uint32 oldTimeout, uint32 newTimeout);
    event MaxDkgSizeChanged(uint32 oldSize, uint32 newSize);

    enum RitualStatus {
        WAITING_FOR_TRANSCRIPTS,
        WAITING_FOR_CONFIRMATIONS,
        CONFIRMED,
        FAILED_TIMEOUT,
        FAILED_INVALID_TRANSCRIPTS,
        FINALIZED
    }

    struct Rite {
        address node;
        bool aggregated;
        bytes transcript;
    }

    struct Ritual {
        uint32 id;
        uint32 dkgSize;
        uint32 initTimestamp;
        uint32 totalTranscripts;
        uint32 totalConfirmations;
        RitualStatus status;
        Rite[] rite;
    }

    Ritual[] public rituals;

    uint32 public timeout;
    uint32 public maxDkgSize;

    constructor(uint32 _timeout) {
        timeout = _timeout;
        maxDkgSize = 64;  // TODO Who knows? https://www.youtube.com/watch?v=hzqFmXZ8tOE&ab_channel=Protoje
    }

    function _checkActiveRitual(Ritual storage _ritual) internal {
        uint32 delta = uint32(block.timestamp) - _ritual.initTimestamp;
        if (delta > timeout) {
            _ritual.status = RitualStatus.FAILED_TIMEOUT;
            emit EndRitual(_ritual.id, _ritual.status); // penalty hook, missing nodes can be known at this stage
            revert("Ritual timed out");
        }
    }

    function setTimeout(uint32 newTimeout) external onlyOwner {
        uint32 oldTimeout = timeout;
        timeout = newTimeout;
        emit TimeoutChanged(oldTimeout, newTimeout);
    }

    function setMaxDkgSize(uint32 newSize) external onlyOwner {
        uint32 oldSize = maxDkgSize;
        maxDkgSize = newSize;
        emit MaxDkgSizeChanged(oldSize, newSize);
    }

    function numberOfRituals() external view returns(uint256) {
        return rituals.length;
    }

    function getRites(uint32 ritualId) external view returns(Rite[] memory) {
        Rite[] memory rites = new Rite[](rituals[ritualId].rite.length);
        for(uint32 i=0; i < rituals[ritualId].rite.length; i++){
            rites[i] = rituals[ritualId].rite[i];
        }
        return rites;
    }

    function initiateRitual(address[] calldata nodes) external returns (uint32) {
        // TODO: Check for payment
        // TODO: Check for expiration time
        // TODO: Improve DKG size choices
        require(nodes.length <= maxDkgSize, "Invalid number of nodes");

        uint32 id = uint32(rituals.length);
        Ritual storage ritual = rituals.push();
        ritual.id = id;
        ritual.dkgSize = uint32(nodes.length);
        ritual.initTimestamp = uint32(block.timestamp);
        ritual.status = RitualStatus.WAITING_FOR_TRANSCRIPTS;

        address previousNode = nodes[0];
        ritual.rite[0].node = previousNode;
        address currentNode;
        for(uint256 i=1; i < nodes.length; i++){
            currentNode = nodes[i];
            require(currentNode > previousNode, "Nodes must be sorted");
            ritual.rite[i].node = currentNode;
            previousNode = currentNode;
            // TODO: Check nodes are eligible (staking, etc)
        }

        emit StartRitual(id, nodes);
        return ritual.id;
    }

    function postTranscript(uint32 ritualId, uint256 nodeIndex, bytes calldata transcript) external {
        Ritual storage ritual = rituals[ritualId];
        require(ritual.rite[nodeIndex].node == msg.sender, "Node not part of ritual");

        require(ritual.status == RitualStatus.WAITING_FOR_TRANSCRIPTS, "Not waiting for transcripts");
        require(ritual.rite[nodeIndex].transcript.length == 0, "Node already posted transcript");
        require(ritual.rite[nodeIndex].aggregated == false, "Node already posted aggregation");

        _checkActiveRitual(ritual);

        // Nodes commit to their transcript
        bytes32 transcriptDigest = keccak256(transcript);
        ritual.rite[nodeIndex].transcript = transcript;
        emit TranscriptPosted(ritualId, msg.sender, transcriptDigest);
        ritual.totalTranscripts++;

        if (ritual.totalTranscripts == ritual.dkgSize){
            ritual.status = RitualStatus.WAITING_FOR_CONFIRMATIONS;
            emit StartAggregationRound(ritualId);
        }
    }

    function postConfirmation(uint32 ritualId, uint256 nodeIndex, bytes calldata aggregatedTranscripts) external {
        Ritual storage ritual = rituals[ritualId];
        require(ritual.status == RitualStatus.WAITING_FOR_CONFIRMATIONS, "Not waiting for confirmations");
        require(ritual.rite[nodeIndex].node == msg.sender, "Node not part of ritual");
        _checkActiveRitual(ritual);

        ritual.rite[nodeIndex].transcript = aggregatedTranscripts;
        ritual.rite[nodeIndex].aggregated = true;
        ritual.totalConfirmations++;

        if (ritual.totalConfirmations == ritual.dkgSize){
            ritual.status = RitualStatus.CONFIRMED;
            // TODO is this considered a final stage (EndRitual) or an Intermediate stage without finalization?
            //  I guess all the relevant information is present (confirmations) although aggregated transcripts
            //  not yet compared to each other
            emit EndRitual(ritualId, ritual.status);
        }
        emit AggregationPosted(ritualId, msg.sender);
    }

    function finalizeRitual(uint32 ritualId) public {
        Ritual storage ritual = rituals[ritualId];
        require(ritual.status == RitualStatus.CONFIRMED, 'ritual not confirmed');

        bytes32 firstRiteDigest = keccak256(ritual.rite[0].transcript);
        for(uint32 i=1; i < ritual.rite.length; i++){
            bytes32 currentRiteDigest = keccak256(ritual.rite[i].transcript);
            if (firstRiteDigest != currentRiteDigest) {
                ritual.status = RitualStatus.FAILED_INVALID_TRANSCRIPTS;
                emit EndRitual(ritualId, ritual.status);
                revert('aggregated transcripts do not match');
            }
        }

        // mark as finalized
        ritual.status = RitualStatus.FINALIZED;
        emit EndRitual(ritualId, ritual.status);
    }


}