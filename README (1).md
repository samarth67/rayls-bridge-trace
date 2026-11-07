# Rayls bridge trace

Read-only check of how USDC gets from Ethereum onto Rayls (LayerZero / Stargate) and what can be verified on Rayls mainnet (chain ID 72957).

- No wallet, no transactions sent. Python standard library only.
- Run: `python rayls_bridge_trace.py` (about 1-2 minutes). Output: `bridge_trace_evidence.json`.
- Negative test: `python rayls_bridge_trace.py --negative` changes the last hex digit of the USDC.e address and must stop at "NO contract code". Output: `bridge_trace_negative.json`.
- Dated snapshots: `bridge_trace_evidence_YYYY-MM-DD.json`.
- This is a snapshot per run, not an audit.

## Labels
- **Documented**: stated in Rayls docs
- **Verified**: checked by my run on-chain or on the Rayls explorer
- **My analysis**: my calculation or reading of the numbers
- **Unconfirmed**: not checked, or cannot be checked from public data

## Addresses (Rayls mainnet)
| Name | Address |
|---|---|
| USDC.e | 0x9001dbe4D68d36ab87923A2a9Dfb0c745fd25001 |
| USDT0.s | 0x1343994e136B6b15CBB2eB4075e0E73b8c4Ebce0 |
| WETH | 0xd8cF92E9B6Fae6B32f795AcB11Edd50E8dD6Ff4d |
| Shared owner() | 0x44143b3de2f977b92c054c6f32fdbd3b3cb74120 |
| USDrEscrow (proxy) | 0xD19A5e28FEd41FA289E92Ae61B9Bc5BD883DB0D2 |
| USDrSwapComposer | 0x5d1c636ab61782beb04cc685922f0197758a81aa |
| Escrow minterBurner | 0x07e17e17e17e17e17e17e17e17e17e17e17e17e6 |
| Ethereum pool | 0xc026395860Db2d07ee33e05fE50ed7bD583189C7 |
| Circle USDC (Ethereum) | 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 |

## Claims
| # | Claim | Label |
|---|---|---|
| 1 | USDC is locked on Ethereum, USDC.e is minted on Rayls and locked in USDrEscrow, which mints USDr 1:1 | Documented |
| 2 | USDr cannot be bridged out | Documented |
| 3 | Way in: a tx to Executor (execute302) mints USDC.e from the zero address to USDrSwapComposer, then USDrEscrow. Example tx 0xe15840c22c19e5341f1c7255f0efcd5209fb0314c764b5b83dbf3af666ed2ddf, block 13,650,210 | Verified |
| 4 | Way out: swapAndBridge moves USDC.e from USDrEscrow to USDrBridgeOut to StargateOFTUSDC, which burns it to the zero address. Example tx [FULL HASH] | Verified |
| 5 | USDC.e is a proxy with verified source on the explorer | Verified |
| 6 | USDC.e, USDT0.s and WETH share one owner(); it is a 7,197-byte contract, not a Safe or timelock by interface | Verified |
| 7 | Escrow holds 26,842.631500 of 27,012.613155 USDC.e (99.37%); USDr supply 25,851.670129; gap 990.961371 equals withdrawableSurplus() | Verified |
| 8 | Another researcher's 22-24 Oct numbers (escrow 26,027.421634, USDr 25,036.460263) have both grown by exactly 815.209866; the surplus did not move | Verified |
| 9 | Mints minus burns equals total supply across all N explorer transfers: [fill from run] | Verified |
| 10 | Ethereum pool went 30.69M to 33.15M USDC between 2 and 4 Nov; Rayls USDC.e is about 0.08% of it, so pool balance cannot show Rayls backing | My analysis |
| 11 | Escrow and USDr move together to the sixth decimal | My analysis |
| 12 | Who holds the owner and minter roles on USDC.e | Unconfirmed |
| 13 | What happens on Ethereum after a burn on Rayls; redemption not tested | Unconfirmed |
| 14 | Where the 990.96 surplus comes from | Unconfirmed |

Sources: https://docs.rayls.com/docs/bridging-to-the-public-chain , https://docs.rayls.com/docs/public-chain-tokenomics , https://github.com/anazoro001/rayls-usdr-backing-research
