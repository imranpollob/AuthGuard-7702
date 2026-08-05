# Opus 5 vs. Previous Provisional Labels — Comparison Report

**LABEL_SOURCE=LLM_PROVISIONAL_OPUS5 · STATIC_ANALYZER_EVIDENCE=VISIBLE · STATUS=PROVISIONAL_PENDING_HUMAN_REVIEW**

PROVISIONAL — OPUS 5 LABELS WITH STATIC-ANALYZER EVIDENCE. Not human labels, not expert labels, not ground truth.


Both label sets cover the same 230 items. The previous pass (`results/llm_provisional/`) was produced **without** static-analyzer evidence and from a linear byte-window guard tracer. This pass was produced **with** the static-analyzer verdict and its per-address rule facts visible, and from a CFG guard-dominance analysis. Neither pass saw any AuthGuard score or prediction.

## 1. Label distribution, old vs. new

| sample set | n | previous SAFE/UNSAFE/UNCERTAIN | Opus 5 SAFE/UNSAFE/UNCERTAIN |
|---|---|---|---|
| pilot | 20 | 9 / 6 / 5 | 2 / 11 / 7 |
| gold_dev | 60 | 5 / 42 / 13 | 9 / 31 / 20 |
| gold_test | 150 | 7 / 131 / 12 | 20 / 88 / 42 |
| **all** | 230 | 21 / 179 / 30 | 31 / 130 / 69 |

## 2. Exact agreement and confusion matrix

Exact 3-class agreement: **126/230 (54.8%)**. Changed: **104**.

| previous \\ Opus 5 | SAFE | UNSAFE | UNCERTAIN |
|---|---|---|---|
| SAFE | 7 | 12 | 2 |
| UNSAFE | 21 | 105 | 53 |
| UNCERTAIN | 3 | 13 | 14 |

### Directional changes

| change | count |
|---|---|
| SAFE → UNSAFE | 12 |
| UNSAFE → SAFE | 21 |
| SAFE → UNCERTAIN | 2 |
| UNCERTAIN → SAFE | 3 |
| UNSAFE → UNCERTAIN | 53 |
| UNCERTAIN → UNSAFE | 13 |

## 3. What caused each change

| cause | items |
|---|---|
| guard newly visible to CFG analysis (missed by the linear-window tracer) | 24 |
| storage-condition path separated from truly unguarded path | 21 |
| linear-window tracer's OPEN reinterpreted as incomplete evidence | 20 |
| opcode-census reachability shortcut removed (now unresolved evidence) | 18 |
| EIP-7702 reinterpretation of a hardcoded-caller guard | 10 |
| re-derived control-flow evidence | 4 |
| memory-provenance limitation acknowledged (capability, not exploit) | 4 |
| manual review override | 3 |

## 4. Every changed item

| item_id | set | src rule | previous | Opus 5 | reason category | cause |
|---|---|---|---|---|---|---|
| `polygon:0x32ab10ebca6121659e41d7caa364147d87ebd74e` | pilot | positive | SAFE | UNSAFE | UNSAFE_INITIALIZATION | manual review override |
| `base:0x54b20dbe278a201289d808448b798106dc6febdd` | pilot | unflagged | SAFE | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | manual review override |
| `ethereum:0xd24558a256c4aa2d0b6c3a7e12b2f70f810e7b04` | pilot | unflagged | SAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `base:0xbe4cb4f3b926953dc550614b71909f149799f1f9` | pilot | positive | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `bnb:0x7543d5c7417fde1b7e2b1d12f7ec77a8fa0d7e7c` | pilot | positive | SAFE | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | EIP-7702 reinterpretation of a hardcoded-caller guard |
| `ethereum:0x2d33b68f3152a43e10b327dbf47bfed0b4a78d10` | pilot | positive | UNCERTAIN | UNSAFE | ARBITRARY_EXTERNAL_CALL | opcode-census reachability shortcut removed (now unresolved evidence) |
| `gnosis:0x95eb89311ffb27112e657b8a6eaaf7391192c83a` | pilot | positive | SAFE | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | EIP-7702 reinterpretation of a hardcoded-caller guard |
| `base:0x09551d2ab499d73affed001b54d483942e11e0ff` | pilot | positive | SAFE | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | EIP-7702 reinterpretation of a hardcoded-caller guard |
| `optimism:0x068315334224a8433971b72504434e741a034e35` | pilot | positive | SAFE | UNSAFE | UNSAFE_INITIALIZATION | manual review override |
| `bnb:0x8656e0466987509e76e49a7e97dde4c5be341c4c` | pilot | unflagged | UNCERTAIN | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | opcode-census reachability shortcut removed (now unresolved evidence) |
| `base:0x2e8bf58e618447d90f4e19ff6491e85fda84472d` | pilot | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | re-derived control-flow evidence |
| `arbitrum:0xc9a6f7ff9db9408eba9bef142ea8aa53d7bbe303` | pilot | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | re-derived control-flow evidence |
| `arbitrum:0xe93bc144cf11af93c705e28a9602550242edea8f` | gold_dev | positive | SAFE | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | EIP-7702 reinterpretation of a hardcoded-caller guard |
| `ethereum:0x28d0c57d3f0ae14d6307fea3972d704166e26785` | gold_dev | positive | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `base:0xd1d4b213d67bf213563629da22769fe335950da2` | gold_dev | positive | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `base:0x833589fcd6edb6e08f4c7c32d4f71b54bda02913` | gold_dev | positive | UNSAFE | SAFE | ACCESS_CONTROL_APPEARS_APPROPRIATE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `base:0x1511cfd463da477220a34ee95561a5253ba036c0` | gold_dev | positive | SAFE | UNSAFE | TX_ORIGIN_AUTHORIZATION_RISK | EIP-7702 reinterpretation of a hardcoded-caller guard |
| `ethereum:0x2db3224808f473c92fdffc327095400c4c9b0588` | gold_dev | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | opcode-census reachability shortcut removed (now unresolved evidence) |
| `base:0x904ac6ff97d28e1b4f6d37fc0051f810694f014b` | gold_dev | unflagged | UNCERTAIN | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | re-derived control-flow evidence |
| `ethereum:0xa575625e73b750d399ce7a8dc4457c2f31b86a80` | gold_dev | unflagged | UNCERTAIN | SAFE | NO_CONCRETE_DANGEROUS_PATH_FOUND | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `ethereum:0x34ffa7e96eb590d1e5813717e237414995f18632` | gold_dev | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `polygon:0x5af42746a8af42d8a4708df238c53f1f71abf0e0` | gold_dev | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `base:0x07926b8fbfddf09cd66a7fcdc2b224b8482e6690` | gold_dev | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `ethereum:0xe92907ab742c61943a21fe6d5175e0e0487d73cc` | gold_dev | unflagged | UNCERTAIN | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | opcode-census reachability shortcut removed (now unresolved evidence) |
| `base:0x3531b08ac3f030b69c49aa577765188f5ba0e662` | gold_dev | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `ethereum:0x962931c0ef665aa769d50ed96b03fc9d0cffa10f` | gold_dev | unflagged | UNSAFE | SAFE | NO_CONCRETE_DANGEROUS_PATH_FOUND | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `ethereum:0x39733857b6fa8ded364ad04a1eb29b8d2c9d5819` | gold_dev | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `base:0x4926888a69ba4042d3cb491ee27dbd0c9e89fce9` | gold_dev | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `ethereum:0x998d014ff55ed8db43e2c72919f0868b1cb352b9` | gold_dev | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `ethereum:0x5a904049c58d01cb06ba217a7006edca9304ae0e` | gold_dev | unflagged | UNCERTAIN | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | re-derived control-flow evidence |
| `ethereum:0xbcf8c26540ced6c5fc68c385281cfdddafe36ca5` | gold_dev | unflagged | UNCERTAIN | SAFE | OWNER_OR_SELF_CALL_RESTRICTED | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `ethereum:0xf368c74f8b9c322d45d076868aeacbb2849026b2` | gold_dev | unflagged | UNSAFE | SAFE | OWNER_OR_SELF_CALL_RESTRICTED | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `arbitrum:0xc708570dc9c4ceb5ad04e1a01347acf9bc235fb9` | gold_dev | unflagged | UNSAFE | SAFE | SIGNATURE_AUTHORIZATION_CONFIRMED | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `ethereum:0xace41ac58d5622ee2b1d57d68dec5ba949277cae` | gold_dev | unflagged | UNCERTAIN | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | EIP-7702 reinterpretation of a hardcoded-caller guard |
| `optimism:0x3acd6c0028784d800e3830d2f6dcec232e540444` | gold_dev | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `ethereum:0x82ef85e78d97f4ef3e4be1b7dcc744fa880425d7` | gold_dev | unflagged | UNCERTAIN | UNSAFE | DANGEROUS_DELEGATECALL_OR_UPGRADE | opcode-census reachability shortcut removed (now unresolved evidence) |
| `bnb:0x6b26cff1469f172af788258c4e9cdbb70a1abc00` | gold_dev | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `ethereum:0x65be99c2d02749d40471546e1b406d9b6fae9381` | gold_dev | unflagged | UNCERTAIN | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | memory-provenance limitation acknowledged (capability, not exploit) |
| `bnb:0x66cee5007121800c8429ee77ab5d7dbfd82982a3` | gold_dev | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | opcode-census reachability shortcut removed (now unresolved evidence) |
| `ethereum:0xf6ae00d4c8605133d756858d8f2d8fc51214c1f3` | gold_dev | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | opcode-census reachability shortcut removed (now unresolved evidence) |
| `bnb:0xc130d35a2ef67843b085ba42171ac1126800b7da` | gold_dev | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | opcode-census reachability shortcut removed (now unresolved evidence) |
| `optimism:0x470a618326df6e320680642dd31794b0d2d12d0a` | gold_test | positive | UNCERTAIN | UNSAFE | UNSAFE_INITIALIZATION | opcode-census reachability shortcut removed (now unresolved evidence) |
| `base:0x768db2a29a1f4cf2fe2f42a01ce6cb2bbf8cd341` | gold_test | positive | UNCERTAIN | SAFE | NO_CONCRETE_DANGEROUS_PATH_FOUND | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `ethereum:0xae7ab96520de3a18e5e111b5eaab095312d7fe84` | gold_test | positive | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `base:0x5fe78697ca70156a458ec9e9cd561aa136fad4c8` | gold_test | positive | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `optimism:0x9307637c1708c1cec79a5e96f4beea7d363f6ca0` | gold_test | positive | UNCERTAIN | UNSAFE | UNSAFE_INITIALIZATION | opcode-census reachability shortcut removed (now unresolved evidence) |
| `optimism:0x93d473ce2ceb00af7489694511ca778deb83ef88` | gold_test | positive | UNCERTAIN | UNSAFE | UNSAFE_INITIALIZATION | opcode-census reachability shortcut removed (now unresolved evidence) |
| `base:0x5197837eac237092876f1bcaf5943d9ad4b70d41` | gold_test | positive | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `bnb:0x5127b7b8bb69efa1f95185df900588b2572dd0d7` | gold_test | positive | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `arbitrum:0x913ef342a833f58ba924e819b25c345e2ae9e5a7` | gold_test | positive | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `base:0xd34426bef7e56fef2a617ea70fff427d658b740b` | gold_test | positive | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `ethereum:0x047440829317d30e994964ff6fa1f82884910dde` | gold_test | positive | SAFE | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | EIP-7702 reinterpretation of a hardcoded-caller guard |
| `ethereum:0x15e6f094b4f2639dec521cbd6d1313c970811aa7` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `base:0xe61870a21fde3f4ef5676eea69feef75a58505d3` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `bnb:0x55d398326f99059ff775485246999027b3197955` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `ethereum:0x664f4f97329d7a19f99cf01a1b213d5c98ba9a94` | gold_test | unflagged | UNSAFE | SAFE | ACCESS_CONTROL_APPEARS_APPROPRIATE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `ethereum:0xa1b0277a9e51f465e3c0a463addf74a2425c1d60` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `base:0xe2fa4df0634c5836edf602b0c48ed7be4c5c1710` | gold_test | unflagged | SAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `ethereum:0xd8dee877be7876b8e8f098d1453de3d556d86a41` | gold_test | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `ethereum:0x9816c8de04dabd822534be4141886dd31c9a7fff` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `base:0xd968196fa6977c4e58f2af5ac01c655ea8332d22` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `base:0xd28b44af6cb560d3ed42042dab16d70df05ef336` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `base:0x904bf260fca02a0a94c47f279d986632c25357b7` | gold_test | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `gnosis:0xc60ef4800d224aece984aeae36f32d5476b400a0` | gold_test | unflagged | UNSAFE | SAFE | NO_CONCRETE_DANGEROUS_PATH_FOUND | memory-provenance limitation acknowledged (capability, not exploit) |
| `optimism:0x6b90faf6d634ede2e56c024a9b852a9607a5c7bf` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `ethereum:0x1e142b1f5ea1b5b12ddb8db5d96f85aacdafb7cb` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `ethereum:0x2c027e2f044dcc98175b71a9c496aab2dbb0b7b1` | gold_test | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `ethereum:0x30bc49bf1e7c7688ea60e6985e70133a9591b0f9` | gold_test | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | opcode-census reachability shortcut removed (now unresolved evidence) |
| `bnb:0xe74a63325801ea977597e50b589bafb809a36ef4` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `bnb:0x41263cba59eb80dc200f3e2544eda4ed6a90e76c` | gold_test | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | opcode-census reachability shortcut removed (now unresolved evidence) |
| `base:0x880ee977a2e0a4cfc9332631def6d93ccf90941a` | gold_test | unflagged | UNSAFE | SAFE | NO_CONCRETE_DANGEROUS_PATH_FOUND | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `bnb:0x7c908d9586341952c33ca941f916b083e69ab334` | gold_test | unflagged | SAFE | UNSAFE | TX_ORIGIN_AUTHORIZATION_RISK | EIP-7702 reinterpretation of a hardcoded-caller guard |
| `base:0x8fa7e26bd5ea9e8f144ca27b9252d441c61413cc` | gold_test | unflagged | UNSAFE | SAFE | NO_CONCRETE_DANGEROUS_PATH_FOUND | opcode-census reachability shortcut removed (now unresolved evidence) |
| `base:0xc4d8e0a7b6f8189ecde2da2fe1f7af4cdfcc42b6` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `bnb:0xe0fd90b416db8398ce656035917727848afe7425` | gold_test | unflagged | UNSAFE | SAFE | OWNER_OR_SELF_CALL_RESTRICTED | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `base:0x18654e2ef4996dc66a2f3bb974b3621d45a3ba2a` | gold_test | unflagged | UNSAFE | SAFE | SIGNATURE_AUTHORIZATION_CONFIRMED | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `base:0x5bc3ee6df05c244b59abbf4a81c02d625f0fd23f` | gold_test | unflagged | UNSAFE | SAFE | NO_CONCRETE_DANGEROUS_PATH_FOUND | opcode-census reachability shortcut removed (now unresolved evidence) |
| `bnb:0xa42435a676b4b8931dd0ecabf1d37a1f1d066a65` | gold_test | unflagged | UNSAFE | SAFE | NO_CONCRETE_DANGEROUS_PATH_FOUND | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `bnb:0x8b54ffa4b6d5e01f5c3aa6d19175f532b47dfb1b` | gold_test | unflagged | UNSAFE | SAFE | OWNER_OR_SELF_CALL_RESTRICTED | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `base:0x8032605c138383cb8a373b2a0f839ed0b6cf872c` | gold_test | unflagged | UNSAFE | SAFE | ACCESS_CONTROL_APPEARS_APPROPRIATE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `ethereum:0xab3df0c2325233228342e76c93d93fe4b34edb8a` | gold_test | unflagged | UNCERTAIN | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | opcode-census reachability shortcut removed (now unresolved evidence) |
| `ethereum:0x5ce9e7b497262f07004d0d4923d3dda7c069230a` | gold_test | unflagged | SAFE | UNSAFE | TX_ORIGIN_AUTHORIZATION_RISK | EIP-7702 reinterpretation of a hardcoded-caller guard |
| `ethereum:0xafc5877036d4e2e8e5cc604ee196ef583d82e788` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `base:0xe645dfe1629b2a80cbfcfe71c17578843d78ebc2` | gold_test | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `bnb:0x69d13bb734e9c6e42029eb0a670a07319452a996` | gold_test | unflagged | UNSAFE | SAFE | OWNER_OR_SELF_CALL_RESTRICTED | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `ethereum:0x2741482032bcafc9726593e9549b1f9518c5d443` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `optimism:0xa1fdd934a977898b72ddbfbec5525e266b7e9991` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | opcode-census reachability shortcut removed (now unresolved evidence) |
| `base:0x7b52df5e78910bebee88898cfbcaaa5689e46047` | gold_test | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `bnb:0x0845773e131e1a414fe0dff70db3e2dd2c6a7076` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `bnb:0x4359e8462296d76beb4061f0d8e277320c7dcb81` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `bnb:0x77cf893facb6ecb7ad2c3dd40b02c46e67697e59` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `bnb:0x4b03defa3a763c46e80378481a451f5d32758997` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `base:0x09c2379c2b49a1277bf81b7b2fd17e50927249db` | gold_test | unflagged | UNSAFE | SAFE | NO_CONCRETE_DANGEROUS_PATH_FOUND | memory-provenance limitation acknowledged (capability, not exploit) |
| `ethereum:0xbf14231a0aae74cd0a922e399c71af71782ddbca` | gold_test | unflagged | UNCERTAIN | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | opcode-census reachability shortcut removed (now unresolved evidence) |
| `ethereum:0x293b8040f8b641f393d39cdf7904543c295c5015` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `ethereum:0x9b377d79e925dbaa9f66d69e2d1ff06c0b8c7d3c` | gold_test | unflagged | UNSAFE | UNCERTAIN | DECOMPILATION_AMBIGUITY | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `bnb:0x9bcdb32c4d0f0992bfb926a28ee2cb7b9d9750cc` | gold_test | unflagged | UNSAFE | SAFE | OWNER_OR_SELF_CALL_RESTRICTED | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `arbitrum:0xd407fff07edf3591e0a2546861950d4a40c28dde` | gold_test | unflagged | SAFE | UNSAFE | UNAUTHORIZED_ASSET_MOVEMENT | EIP-7702 reinterpretation of a hardcoded-caller guard |
| `polygon:0x4d85ab31f120e4465ae055c0fb97e135691df186` | gold_test | unflagged | UNSAFE | SAFE | NO_CONCRETE_DANGEROUS_PATH_FOUND | linear-window tracer's OPEN reinterpreted as incomplete evidence |
| `ethereum:0xc96c6b7c729ef97296c7e057504e34397dc6ae50` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `bnb:0x8e8e658e22b12ada97b402ff0b044d6a325013c7` | gold_test | unflagged | UNSAFE | UNCERTAIN | INSUFFICIENT_EVIDENCE | storage-condition path separated from truly unguarded path |
| `bnb:0x9aa40217a63f9e941b85ce868c53c61f014faab7` | gold_test | unflagged | UNSAFE | SAFE | NO_CONCRETE_DANGEROUS_PATH_FOUND | memory-provenance limitation acknowledged (capability, not exploit) |
| `gnosis:0x387e4bda692aa4c9b4147c9a3c2ee8c7c846a8af` | gold_test | unflagged | UNSAFE | SAFE | ACCESS_CONTROL_APPEARS_APPROPRIATE | guard newly visible to CFG analysis (missed by the linear-window tracer) |
| `ethereum:0x0000fb7702036ff9f76044a501ac1aa74cbab16b` | gold_test | unflagged | UNSAFE | SAFE | OWNER_OR_SELF_CALL_RESTRICTED | guard newly visible to CFG analysis (missed by the linear-window tracer) |

## 5. Remaining ambiguous cases

69 items remain UNCERTAIN under Opus 5 (30.0% of all items). Reason breakdown:

| uncertain reason | count |
|---|---|
| INSUFFICIENT_EVIDENCE | 39 |
| DECOMPILATION_AMBIGUITY | 30 |

These are excluded from binary metrics everywhere downstream and reported as uncertainty coverage, never forced into a binary label.

