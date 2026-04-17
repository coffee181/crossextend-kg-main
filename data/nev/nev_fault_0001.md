# NEV Fault Diagnosis Case Document

**Case ID:** nev_fault_0001
**Related Product ID:** nev_product_001
**Fault Type:** Battery Range Drop
**Fault Code:** BMS_ALM_2107 (Battery Capacity Degradation Alarm)
**Date Logged:** 2023-10-26
**Diagnostician:** Sr. Engineer Zhang Wei

## Case Overview
The customer reported a significant and sudden reduction in the vehicle's driving range. The advertised range is 420 km (NEDC), but the current real-world range has dropped to approximately 280 km, accompanied by a 15% discrepancy between the displayed State of Charge (SOC) and the actual usable energy. The vehicle has been in service for 22 months and has accumulated 45,000 km.

### Environment & Vehicle Conditions
| Item | Detail |
| :--- | :--- |
| **Vehicle Model** | NEV_Product_001 (Long-Range Edition) |
| **VIN** | LVHRE1A3XK5001234 |
| **Mileage** | 45,320 km |
| **Production Date** | 2022-01 |
| **Ambient Temperature** | 15-25 °C (During complaint period) |
| **Primary Usage** | Daily urban commute, frequent DC fast charging (>90% of charging cycles) |
| **Average Speed** | 32 km/h |
| **Tire Pressure** | Within specification (2.5 Bar) |

## Diagnosis Process Timeline

**Step 1 – Data Verification & Preliminary Interview (Day 1)**
*   Connected diagnostic tool and extracted fault logs from Vehicle Control Unit (VCU) and Battery Management System (BMS).
*   Confirmed active alarm `BMS_ALM_2107` and multiple historical logs for `BMS_WRN_105` (Cell Voltage Imbalance).
*   Interviewed customer to confirm driving habits, charging patterns (predominantly fast charging to 100%), and the timeline of range reduction (noticed sharp drop over the last 2 months).

**Step 2 – On-board Data Analysis & Health Check (Day 1)**
*   Performed a full BMS data scan. Key findings:
    *   Total pack capacity calculated by BMS: 68.2 kWh (vs. original 78.9 kWh).
    *   Maximum cell voltage deviation: 412 mV (Severely out of spec >50mV).
    *   Internal Resistance (IR) of Module #3 was 35% higher than the pack average.
*   Conducted a slow, full calibration charge in a controlled environment. Observed that the charging current tapered prematurely when cells in Module #3 reached their upper voltage limit.

**Step 3 – In-depth Battery Pack Analysis (Day 2)**
*   Isolated and removed the battery pack for a workshop-level inspection.
*   Used a dedicated battery cell analyzer to perform a static and dynamic capacity test on individual modules.
*   **Critical Finding:** The capacity of Module #3 was measured at 52.1 Ah, while all other modules measured between 59.8 - 60.5 Ah. This represented a ~14% capacity loss isolated to one module.

**Step 4 – Cell-Level Diagnosis (Day 2)**
*   Disassembled Module #3 and performed capacity and internal resistance tests on each of its 12 cells.
*   Identified two specific cells (Cell 3B and 3F) with severe capacity fade (>18%) and significantly elevated internal resistance. These cells were identified as the "weak links" causing the entire module, and consequently the pack, to de-rate.

**Step 5 – Root Cause Correlation & Validation (Day 3)**
*   Correlated the location of the failed cells with the vehicle's thermal management system layout.
*   Reviewed the fast-charging history data from the BMS, confirming that the high current and heat generation during frequent fast charging, combined with a localized cooling inefficiency in that module area, accelerated the degradation of the two cells.

## Root Cause Analysis
The root cause of the sudden range drop is **accelerated and uneven degradation of specific lithium-ion cells within Battery Module #3, leading to severe capacity imbalance within the pack.** The primary accelerator was the customer's habitual use of high-power DC fast charging to 100% State of Charge (SOC), which generates significant heat and stress on battery cells. Compounding this, a minor, localized inefficiency in the thermal interface material for Module #3 resulted in slightly higher operating temperatures for cells 3B and 3F during these charging events. This chronic, localized thermal stress caused these cells to degrade at a much faster rate than their peers. The BMS, detecting the growing voltage and capacity imbalance, proactively limited the usable capacity of the entire battery pack to protect the weakest cells, manifesting as a sudden and severe range reduction for the driver.

## Solution Description
The faulty **Battery Module #3** was replaced with a new, factory-calibrated module. The replacement module underwent a capacity and internal resistance matching process to ensure compatibility with the existing modules in the pack. Following installation, a full pack integration procedure was performed, including:
1.  A low-current balance charge to equalize all cell voltages.
2.  A complete BMS software reset and capacity re-learning cycle.
3.  A full discharge and slow charge calibration cycle to allow the BMS to accurately map the new pack capacity.

Post-repair, the vehicle's calculated pack capacity returned to 77.8 kWh, and the cell voltage deviation was measured at 18 mV (within specification). A road test confirmed the restoration of the expected driving range. The customer was advised on optimal charging practices.

## Lessons Learned
1.  A sudden range drop is often a symptom of a *system-level protective action* (BMS limiting usage) rather than just uniform wear.
2.  Fault codes related to cell imbalance (`BMS_WRN_105`) are critical early indicators that warrant immediate investigation to prevent accelerated failure.
3.  Customer usage data, especially charging history, is indispensable for accurate root cause diagnosis of battery issues.

## Prevention Measures
*   **For Users:** Update the owner's manual and in-vehicle infotainment prompts to educate users on battery care: encourage using AC slow charging for daily needs, setting charge limit to 80-90% for daily use, and reserving 100% DC fast charging for long trips only.
*   **For Design:** Review and enhance the thermal conductive design for Module #3's location in the next product iteration. Improve BMS software logic to provide earlier, more user-friendly warnings about developing cell imbalances.
*   **For Service:** Implement a routine battery health check during regular maintenance, including a report on cell voltage deviation and SOH (State of Health) estimation, to allow for proactive intervention.