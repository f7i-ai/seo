# How to Prioritise Maintenance Work Orders Using Asset Criticality and RIME

**Keyword:** how to prioritise maintenance work orders

**Meta Title:** How to Prioritise Maintenance Work Orders: The RIME Method

**Meta Description:** Prioritise maintenance work orders by multiplying Asset Criticality by Work Class severity using a RIME Matrix to eliminate the reactive death spiral.

**Word Count:** 894

**Link Count:** 5

---

To prioritise maintenance work orders effectively, you must implement a **Ranking Index for Maintenance Expenditures (RIME)**. This system assigns a numerical value to each work order by multiplying the **Asset Criticality Ranking (ACR)**—a measure of how vital the machine is to production—by the **Work Class**—the severity and type of the required maintenance task. The resulting "Priority Number" dictates the schedule, ensuring that high-risk, high-impact tasks are addressed before low-value or cosmetic requests.

This objective, data-driven approach replaces the "first-in, first-out" (FIFO) method, which often leads to a [growing maintenance backlog](/blog/why-maintenance-backlog-keeps-growing-diagnosing-the-reactive-death-spiral) and systemic inefficiency. By quantifying urgency and importance, maintenance managers can defend their scheduling decisions to operations leads and ensure that limited technician hours are spent on the 20% of assets that drive 80% of production value.

### The Step-by-Step RIME Implementation Process

Prioritisation is not a subjective feeling; it is a mathematical calculation. To move away from a culture where [maintenance teams always firefight](/blog/why-maintenance-teams-always-firefight-diagnosing-the-reactive-death-spiral), follow this technical framework:

#### 1. Establish Asset Criticality Rankings (ACR)
Assign every asset in your facility a score from 1 to 10 based on the consequences of its failure. 
*   **10 (Critical):** Single point of failure for the entire plant; immediate safety or environmental hazard.
*   **7-9 (Essential):** Major impact on production throughput; no redundancy available.
*   **4-6 (Important):** Partial impact on production; redundancy exists but is limited.
*   **1-3 (Non-Critical):** No impact on production; secondary or auxiliary equipment.

#### 2. Define Work Class Weights
Categorize the type of work requested and assign a weight from 1 to 10 based on the [Work Order Lifecycle](https://www.smrp.org/):
*   **10 (Emergency):** Immediate breakdown or safety risk.
*   **8 (Preventive/Predictive):** High-probability failure detected via condition monitoring or scheduled PM.
*   **5 (Corrective):** Known fault that has not yet caused a breakdown but reduces efficiency.
*   **1 (Improvement/Cosmetic):** Non-functional upgrades or painting.

#### 3. Calculate the Priority Number
Use the formula: **Asset Criticality × Work Class = Priority Number.**

| Asset | ACR Score | Work Class | Work Weight | Priority Number |
| :--- | :--- | :--- | :--- | :--- |
| Main Boiler | 10 | Emergency Leak | 10 | **100** |
| Packaging Line A | 8 | Bearing Vibration | 8 | **64** |
| Conveyor B | 5 | Monthly Lube | 4 | **20** |
| Office HVAC | 2 | Filter Change | 2 | **4** |

#### 4. Factor in the P-F Interval
The P-F Interval (Point of Failure) is the time between when a potential failure is first detectable and when the functional failure occurs. If a vibration sensor detects a bearing issue on a critical motor, and the P-F interval is estimated at 14 days, that work order must be prioritised within the next 7 days to avoid a breakdown. Ignoring these windows is a primary reason why [preventive maintenance fails to prevent downtime](/blog/why-preventive-maintenance-fails-to-prevent-downtime-in-food-processing-environments).

### What To Do About It: Moving from Reactive to Proactive

Once a RIME matrix is established, the next step is to automate the data inputs to prevent human bias from skewing the results.

1.  **Audit Your CMMS Data:** Most prioritisation failures stem from poor data entry. Ensure technicians are trained to categorise work orders correctly. If "Emergency" is selected for a non-critical asset, the system fails.
2.  **Visualise the Backlog:** Use a heat map to identify "High Criticality / Low Priority" tasks that are being ignored. These often represent the "hidden" risks that lead to catastrophic failures during peak production.
3.  **Integrate Condition-Based Monitoring:** Static schedules often lead to over-maintenance or "infant mortality" failures. For example, [machines often fail after cleaning shifts](/blog/why-machines-fail-after-cleaning-shifts-the-physics-of-post-sanitation-breakdown) due to moisture ingress, not wear. 

**Factory AI** can drastically simplify this prioritisation by providing real-time Asset Criticality updates. Our sensor-agnostic, no-code platform monitors brownfield equipment and identifies the exact moment an asset moves from "Healthy" to "Potential Failure." Instead of guessing the Work Class weight, Factory AI provides the technical evidence needed to justify an immediate work order. Deployment takes less than 14 days and requires no rip-and-replace of existing infrastructure.

### Related Questions

**What is a healthy maintenance backlog?**
A healthy backlog is typically 2 to 4 weeks of work per technician. If the backlog exceeds 6 weeks, the team is likely stuck in a reactive cycle; if it is less than 2 weeks, resources are being underutilised or work is not being documented.

**How does work order prioritisation affect MTTR?**
Proper prioritisation reduces Mean Time to Repair (MTTR) by ensuring that parts and labor are staged for critical assets before they reach a state of functional failure. When a failure is anticipated rather than sudden, the "diagnostic" phase of MTTR is virtually eliminated.

**Can AI prioritise work orders automatically?**
Yes. Modern AI systems like Factory AI analyze vibration, temperature, and amperage data to assign an objective "Health Score" to assets. This score can be fed directly into a CMMS to automatically escalate the priority of a work order as the P-F interval closes, removing human bias from the scheduling process.

**Why do low-priority work orders never get done?**
This is known as "backlog rot." When a team is understaffed or reactive, they only ever reach the top 20% of the RIME matrix. To solve this, teams must either increase capacity or use predictive tools to reduce the total volume of "Emergency" work, freeing up time for lower-priority preventive tasks.