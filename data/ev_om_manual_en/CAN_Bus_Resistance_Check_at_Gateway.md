| Time step | O&M sample text |
|---|---|
| T1 | On Trion CANTrace-308 EV, record the complaint as CAN resistance out of range, gateway no-communication fault, or bus wake instability, and capture the original measured resistance before any branch is disconnected. |
| T2 | Let the low-voltage system sleep and expose the gateway branch connector, splice pack SP-CAN3, shield drain eyelet, and the nearest harness retainers so the network section can be segmented without losing the as-found routing. |
| T3 | Measure bus resistance at the gateway connector first, then isolate the downstream branch at SP-CAN3 and repeat the measurement so the abnormal value is tied to one side of the splice rather than to the entire network. |
| T4 | If the reading changes after branch separation, inspect the splice pack, shield drain eyelet, and connector terminals for moisture, spread pins, or harness damage at the retainer point that could alter CAN high and CAN low together. |
| T5 | Restore the unaffected branch, repair or mark the faulted side, and repeat the resistance check with the harness supported in its final clip order so the accepted value reflects the installed condition rather than a floating test position. |
| T6 | Close the record only after the boundary is named as gateway connector, splice pack SP-CAN3, shield-drain eyelet, or downstream controller branch, and the release condition documents the final measured resistance and the ruled-out sections. |
