// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title BlockTraceCaseRegistry
 * @dev Cryptographic registry for BlockTrace forensic investigation cases.
 *
 * PRIVACY NOTICE:
 * All data stored on-chain and referenced on IPFS is publicly readable.
 * To protect ongoing investigations and suspect confidentiality, plaintext case
 * names, case numbers, and client details are NEVER placed directly on-chain.
 * Only cryptographic hashes (keccak256 of the case number, SHA-256 of the canonical snapshot)
 * and IPFS content identifiers are recorded.
 */
contract BlockTraceCaseRegistry {
    struct CaseRecord {
        bytes32 caseNumberHash; // keccak256(bytes(case_number))
        bytes32 caseDataHash;   // SHA-256 digest of canonical case JSON snapshot
        string ipfsCid;         // IPFS CID containing the case snapshot
        address submitter;      // Address that submitted this version
        uint256 timestamp;      // Block timestamp
        uint256 version;        // 1-indexed version number
    }

    // Mapping from caseNumberHash => array of versioned records
    mapping(bytes32 => CaseRecord[]) private _caseHistory;

    event CaseStored(
        bytes32 indexed caseNumberHash,
        bytes32 caseDataHash,
        string ipfsCid,
        address indexed submitter,
        uint256 version,
        uint256 timestamp
    );

    /**
     * @notice Stores or updates an investigation case record.
     * @dev Version 1 is created on initial storage. Subsequent updates for the same
     *      caseNumberHash must be submitted by the original submitter and increment the version.
     * @param caseNumberHash keccak256 hash of the case number string.
     * @param caseDataHash SHA-256 digest of the canonical investigation snapshot.
     * @param ipfsCid IPFS CID pointing to the pinned snapshot.
     * @return version The version number assigned to this record.
     */
    function storeCase(
        bytes32 caseNumberHash,
        bytes32 caseDataHash,
        string calldata ipfsCid
    ) external returns (uint256 version) {
        require(caseNumberHash != bytes32(0), "Invalid case number hash");
        require(caseDataHash != bytes32(0), "Invalid case data hash");
        require(bytes(ipfsCid).length > 0, "Invalid IPFS CID");

        uint256 currentCount = _caseHistory[caseNumberHash].length;

        if (currentCount == 0) {
            version = 1;
        } else {
            // Only the original submitter who created version 1 may publish updates
            address originalSubmitter = _caseHistory[caseNumberHash][0].submitter;
            require(
                msg.sender == originalSubmitter,
                "Unauthorized: only original submitter can update this case"
            );
            version = currentCount + 1;
        }

        CaseRecord memory record = CaseRecord({
            caseNumberHash: caseNumberHash,
            caseDataHash: caseDataHash,
            ipfsCid: ipfsCid,
            submitter: msg.sender,
            timestamp: block.timestamp,
            version: version
        });

        _caseHistory[caseNumberHash].push(record);

        emit CaseStored(
            caseNumberHash,
            caseDataHash,
            ipfsCid,
            msg.sender,
            version,
            block.timestamp
        );
    }

    /**
     * @notice Retrieves the latest record for a case by its caseNumberHash.
     */
    function getCase(bytes32 caseNumberHash)
        external
        view
        returns (
            bytes32 _caseNumberHash,
            bytes32 _caseDataHash,
            string memory _ipfsCid,
            address _submitter,
            uint256 _timestamp,
            uint256 _version
        )
    {
        uint256 count = _caseHistory[caseNumberHash].length;
        require(count > 0, "Case not found");
        CaseRecord memory record = _caseHistory[caseNumberHash][count - 1];
        return (
            record.caseNumberHash,
            record.caseDataHash,
            record.ipfsCid,
            record.submitter,
            record.timestamp,
            record.version
        );
    }

    /**
     * @notice Retrieves a specific historical version of a case.
     */
    function getCaseVersion(bytes32 caseNumberHash, uint256 version)
        external
        view
        returns (
            bytes32 _caseNumberHash,
            bytes32 _caseDataHash,
            string memory _ipfsCid,
            address _submitter,
            uint256 _timestamp,
            uint256 _version
        )
    {
        uint256 count = _caseHistory[caseNumberHash].length;
        require(count > 0, "Case not found");
        require(version >= 1 && version <= count, "Invalid version");
        CaseRecord memory record = _caseHistory[caseNumberHash][version - 1];
        return (
            record.caseNumberHash,
            record.caseDataHash,
            record.ipfsCid,
            record.submitter,
            record.timestamp,
            record.version
        );
    }

    /**
     * @notice Returns the total number of versions stored for a given case.
     */
    function getCaseVersionCount(bytes32 caseNumberHash)
        external
        view
        returns (uint256)
    {
        return _caseHistory[caseNumberHash].length;
    }
}
