# CNC Fault Diagnosis Case Document

**Case ID:** cnc_fault_0001
**Product ID:** cnc_product_001
**Fault Type:** Spindle Bearing Failure
**Fault Code:** S-1207 (Spindle Vibration Excessive)
**Date Logged:** 2023-10-26
**Machine:** VMC-850 5-Axis Vertical Machining Center
**Controller:** FANUC 31i-B5

---

## 1. Case Overview
The operator reported abnormal noise and visible vibration during high-speed (12,000 RPM) finishing operations on aluminum aerospace components. The vibration led to poor surface finish (chatter marks) and triggered the machine's vibration monitoring system, generating alarm S-1207. The fault occurred intermittently at first but became consistent over a 48-hour period.

## 2. Environment & Operating Conditions

| Condition | Detail |
| :--- | :--- |
| **Machine Runtime** | 22,450 hours |
| **Spindle Runtime** | 18,920 hours |
| **Operating Shift** | 24/5 (Two 12-hour shifts) |
| **Primary Material** | Aluminum 7075, Titanium 6Al-4V |
| **Coolant Type** | Semi-synthetic, 8% concentration |
| **Shop Ambient Temp** | 24°C ± 3°C |
| **Recent Maintenance** | Coolant system service 30 days prior. No recent spindle service. |

## 3. Diagnosis Process Timeline

| Step | Time Elapsed | Action & Procedure | Observations & Data |
| :--- | :--- | :--- | :--- |
| **1. Initial Response** | 0 - 15 min | Acknowledge alarm. Interview operator. Perform visual/auditory inspection at idle (500 RPM) and low speed (3,000 RPM). | High-frequency metallic whining noise audible above 2,500 RPM. Minor visible runout at spindle nose. |
| **2. Data Collection** | 15 - 60 min | Connect portable vibration analyzer (accelerometer) to spindle housing. Run spindle through predefined speed steps (1k, 3k, 6k, 9k, 12k RPM) under no load. | Vibration velocity (RMS) exceeded ISO 10816-3 G2.5 limits at all speeds. Dominant frequency peak at 587 Hz, correlating to the **Ball Pass Frequency Outer (BPFO)** of the front angular contact bearing set. |
| **3. Thermal Analysis** | 60 - 90 min | Measure spindle housing temperature with IR thermometer after 30-minute run at 8,000 RPM. Compare with baseline. | Front bearing housing temp: 72°C (Baseline: 52°C). Excessive temperature rise indicates friction. |
| **4. Contamination Check** | 90 - 120 min | Drain spindle coolant-oil mist lubrication unit. Inspect for metal particles using magnetic plug and filter examination. | Fine bronze/gray metallic flakes found in the filter, indicative of bearing cage and race wear. |
| **5. Confirmation Test** | 120 - 150 min | Perform coast-down test. Monitor vibration spectrum as spindle decelerates from 10,000 RPM. | Vibration peak at BPFO remained dominant during deceleration, confirming bearing defect is mechanical, not resonance or imbalance-related. |

## 4. Root Cause Analysis
The root cause was **fatigue spalling of the front angular contact bearing races** due to a combination of factors. The primary catalyst was **lubrication starvation** in the front bearing set. Investigation revealed a partially restricted metering jet in the oil-mist lubrication line feeding the front bearings, likely caused by a small debris ingress during the last coolant system service. This led to inadequate oil film formation at high speeds and temperatures. The resultant metal-to-metal contact accelerated bearing fatigue. Secondary contributing factors were the high axial and radial loads from continuous 5-axis contouring of titanium, which placed exceptional stress on the already compromised lubrication. The failure mode was classic bearing pitting and spalling, generating vibration at characteristic bearing frequencies.

## 5. Solution Description
The corrective action involved a complete spindle bearing replacement and lubrication system overhaul. The spindle was disassembled, and the matched pair of front angular contact bearings (and the rear cylindrical roller bearing) were replaced with precision-grade equivalents (P4 tolerance). The lubrication system was fully flushed, and all metering jets, lines, and the mist generator were cleaned or replaced. Following reassembly, the spindle was pre-loaded and thermally stabilized in a controlled run-in procedure over 8 hours. Final verification included a vibration analysis, which showed levels within ISO G1.0 (excellent), and a test cut that confirmed surface finish specifications were met. Total downtime was 32 hours.

## 6. Lessons Learned
1. Proactive maintenance of the auxiliary systems (like lubrication) is as critical as the spindle itself.
2. Intermittent symptoms are early failure indicators and should trigger immediate investigation, not run-to-failure.
3. Vibration analysis is a powerful predictive tool when baseline data and characteristic bearing frequencies are known.

## 7. Prevention Measures
- **Revised PM Schedule:** Implement monthly checks of oil-mist flow to each bearing junction via sight glasses.
- **Filter Upgrade:** Install a 10-micron secondary filter in the lubrication feed line.
- **Training:** Brief maintenance staff on strict cleanliness protocols when servicing systems connected to the spindle lube.
- **Monitoring:** Log spindle vibration data quarterly to establish a trend and enable predictive maintenance.
- **Spare Parts:** Stock a critical bearing kit (front set) to reduce future downtime.