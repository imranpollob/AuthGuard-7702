"""Versioned protocol actors that have authorization meaning in delegate bytecode.

Addresses are lowercase and sourced from the official eth-infinitism account-abstraction
release registry. Keeping this registry separate from learned parameters makes every special
semantic classification inspectable and updateable without silently changing a checkpoint.
"""
from __future__ import annotations


ERC4337_ENTRYPOINTS = {
    "0x5ff137d4b0fdcd49dca30c7cf57e578a026d2789": {
        "version": "0.6",
        "source": "https://github.com/eth-infinitism/account-abstraction/releases/tag/v0.6.0",
    },
    "0x0000000071727de22e5e9d8baf0edac6f37da032": {
        "version": "0.7",
        "source": "https://github.com/eth-infinitism/account-abstraction/releases/tag/v0.7.0",
    },
    "0x4337084d9e255ff0702461cf8895ce9e3b5ff108": {
        "version": "0.8",
        "source": "https://github.com/eth-infinitism/account-abstraction/releases/tag/v0.8.0",
    },
    "0x433709009b8330fda32311df1c2afa402ed8d009": {
        "version": "0.9",
        "source": "https://github.com/eth-infinitism/account-abstraction/releases/tag/v0.9.0",
    },
}

ERC4337_ENTRYPOINT_ADDRESSES = frozenset(ERC4337_ENTRYPOINTS)
