// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

/**
 * @title MockVerifier
 * @dev A simple verifier that always returns true for testing/hackathon purposes.
 */
contract MockVerifier {
    function verify(
        uint256[] calldata,
        bytes calldata
    ) external pure returns (bool) {
        return true;
    }
}
