| Time step | O&M sample text |
|---|---|
| T1 | On Trion NetBridge-578 EV, record the complaint as intermittent BMS communication loss, random CAN-off DTCs, or wake failures that improve when cabin humidity drops, and save the bus symptom timing before the splice area is opened. |
| T2 | Let the low-voltage system sleep and expose splice pack SP-21, the paired CAN high and CAN low conductors, shield drain eyelet, and the right kick-panel harness retainers without altering the twisted-pair lay between the splice and the module connectors. |
| T3 | Inspect SP-21 and the surrounding retainers for oxidation, moisture trace, conductor nick, untwisted pair length, or shield-drain looseness that could degrade the bus only when the branch is loaded at wake. |
| T4 | Measure bus resistance and continuity at both sides of SP-21, then compare the values while the splice pack is lightly flexed so a weak splice crimp is separated from a connector problem farther down the branch. |
| T5 | If the splice is suspect, open the splice area enough to inspect crimp integrity, conductor insertion depth, and insulation support without disturbing unrelated branches that still provide a clean network baseline. |
| T6 | After any splice repair, restore the twisted-pair length, shield drain, and retainer order so the CAN pair remains supported and shielded in the same path it uses when the kick panel is installed. |
| T7 | Repeat the original wake sequence and verify that BMS communication, bus resistance, and module online status remain stable through the same timing window that originally produced the dropout. |
| T8 | Close the diagnosis only after the boundary is named as splice pack SP-21 oxidation, CAN high or CAN low crimp loss, shield-drain eyelet fault, retainer-induced conductor damage, or normal splice condition with the fault moved elsewhere, and the release state documents a stable bus. |
