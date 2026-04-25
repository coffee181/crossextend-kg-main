| Time step | O&M sample text |
|---|---|
| T1 | On Kestrel CANLink-341 EV, record the complaint as intermittent gateway communication loss, no response from the thermal controller after wake, or CAN-off faults after battery replacement, and save the as-received node status before the communication branch is opened. |
| T2 | Let the low-voltage system sleep and expose gateway connector C214, CAN splice S112, the local ground eyelet, and the first two harness clips beneath the battery tray without changing the harness twist between the splice and connector. |
| T3 | Inspect C214, splice S112, and the routed harness for moisture, terminal recession, rub at the tray edge, clip loss, or ground-eyelet looseness that could distort CAN high and CAN low together during wake. |
| T4 | Measure CAN high, CAN low, and bus resistance at C214 and then compare the values at splice S112 so the fault is placed on the gateway connector, the splice branch, or the downstream controller leg rather than on the network generally. |
| T5 | If the values change while the harness is touched, inspect terminal drag, seal compression, and the clip-to-connector path so an intermittent pin fit or harness pull is separated from a controller-side fault. |
| T6 | After any connector or splice repair, restore the harness twist and clip order and repeat the same sleep-to-wake sequence that originally dropped communication, verifying that the gateway and thermal controller remain online together. |
| T7 | Close the record only after the boundary is named as C214 terminal fit, splice S112 branch, ground-eyelet resistance, tray-edge rub, or normal gateway branch behavior, and the release state documents stable CAN communication through repeat wake cycles. |
