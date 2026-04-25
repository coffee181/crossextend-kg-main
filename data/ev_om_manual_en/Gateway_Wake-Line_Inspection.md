| Time step | O&M sample text |
|---|---|
| T1 | On Trion NetBridge-516 LR, record the complaint as no-ready after sleep, charge-port module not waking, or wake-line DTC at key-on, and capture the original wake-line voltage and gateway state before any connector is opened. |
| T2 | Let the low-voltage system sleep and expose wake-line splice WG-4, gateway connector C118, charge-port control connector XCP-2, the local harness retainer, and the adjacent anti-rub sleeve while preserving the installed harness angle. |
| T3 | Measure wake-line continuity and voltage from C118 to XCP-2, flexing the branch at WG-4 and the retainer point so the fault is placed on the splice, connector, or harness segment rather than on the network generally or on the gateway module. |
| T4 | If the value changes with movement, inspect WG-4, C118, and XCP-2 for terminal recession, splice pullout, seal damage, anti-rub sleeve loss, or conductor break at the retainer edge. |
| T5 | Restore the repaired branch in its final clip order and repeat the same sleep-to-wake event that originally failed, confirming that gateway and charge-port controller now wake together with a stable line voltage and no delay at the charge-port control node. |
| T6 | Close the record only after the boundary is named as wake-line splice WG-4, gateway connector C118, charge-port connector XCP-2, anti-rub sleeve loss at the retainer, or conductor break at the retainer edge, and the release condition documents a stable wake path through repeat cycles. |
