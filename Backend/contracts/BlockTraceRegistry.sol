// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title BlockTraceRegistry
 * @notice Stores investigation records on-chain: a SHA-256 investigation hash
 *         paired with the IPFS CID of the corresponding forensic PDF report.
 *         Each hash can only be stored once (immutable evidence trail).
 *
 * @dev Deploy via Remix IDE → "Injected Provider - MetaMask" on Sepolia.
 *      No external imports — compiles stand-alone in Remix.
 */
contract BlockTraceRegistry {

    struct Record {
        bytes32  investigationHash;
        string   ipfsCid;
        address  submitter;
        uint256  timestamp;
    }

    /// @notice Emitted every time a new record is stored.
    event RecordStored(
        bytes32 indexed investigationHash,
        string  ipfsCid,
        address indexed submitter,
        uint256 timestamp
    );

    /// investigationHash → Record
    mapping(bytes32 => Record) private _records;

    /// Quick existence check so we can reject duplicates without comparing strings.
    mapping(bytes32 => bool) private _exists;

    /**
     * @notice Store a new investigation record. Reverts if the hash has already been recorded.
     * @param investigationHash SHA-256 digest of the investigation findings (bytes32).
     * @param ipfsCid           IPFS content identifier of the uploaded PDF report.
     */
    function storeRecord(bytes32 investigationHash, string calldata ipfsCid) external {
        require(!_exists[investigationHash], "BlockTraceRegistry: hash already recorded");
        require(bytes(ipfsCid).length > 0,    "BlockTraceRegistry: empty IPFS CID");

        _records[investigationHash] = Record({
            investigationHash: investigationHash,
            ipfsCid:           ipfsCid,
            submitter:         msg.sender,
            timestamp:         block.timestamp
        });

        _exists[investigationHash] = true;

        emit RecordStored(investigationHash, ipfsCid, msg.sender, block.timestamp);
    }

    /**
     * @notice Retrieve a previously stored record by its investigation hash.
     * @param investigationHash The hash to look up.
     * @return investigationHash_ The stored hash (same as the input).
     * @return ipfsCid           The IPFS CID of the PDF report.
     * @return submitter         The address that submitted the record.
     * @return timestamp         The block timestamp when the record was stored.
     */
    function getRecord(bytes32 investigationHash)
        external
        view
        returns (
            bytes32 investigationHash_,
            string  memory ipfsCid,
            address submitter,
            uint256 timestamp
        )
    {
        require(_exists[investigationHash], "BlockTraceRegistry: record not found");
        Record storage r = _records[investigationHash];
        return (r.investigationHash, r.ipfsCid, r.submitter, r.timestamp);
    }
}
