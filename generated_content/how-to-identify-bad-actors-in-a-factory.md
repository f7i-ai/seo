# How to Identify Bad Actors in a Factory: A Reliability Engineering Framework

**Keyword:** how to identify bad actors in a factory

**Meta Title:** How to Identify Bad Actors in a Factory: Reliability Guide

**Meta Description:** Identify bad actors by performing a Pareto analysis on CMMS data to find the 20% of assets causing 80% of downtime. Use MTBF and TCO to rank chronic failures.

**Word Count:** 1034

**Link Count:** 8

---

To identify bad actors in a factory, you must perform a **Pareto analysis** on your maintenance data to isolate the 20% of assets responsible for 80% of your downtime, maintenance costs, or production losses. A "bad actor" is defined as any asset or component that experiences repetitive, chronic failures rather than isolated, sporadic breakdowns. Identification requires calculating the **Mean Time Between Failures (MTBF)** and **Total Cost of Ownership (TCO)** for every critical asset over a rolling 12-month period.

The identification process shifts the focus from "what broke today" to "what breaks most often." By ranking assets based on failure frequency and the cumulative cost of repairs, maintenance managers can distinguish between high-impact sporadic events (which require immediate Root Cause Analysis) and the "death by a thousand cuts" caused by chronic bad actors that drain labor and budget.

### The Systematic Process for Identifying Bad Actors

Identifying bad actors is not a subjective exercise based on technician complaints; it is a data-driven audit. Follow these four steps to build an accurate bad actor list:

#### 1. Data Aggregation and Cleaning
Extract 12 to 24 months of work order history from your Computerized Maintenance Management System (CMMS). You must filter for "unplanned corrective maintenance" and exclude preventive maintenance (PM) or capital project work. If your data is "noisy," focus on assets where the [maintenance backlog keeps growing](/blog/why-maintenance-backlog-keeps-growing-diagnosing-the-reactive-death-spiral), as these are often the primary sites of hidden chronic failures.

#### 2. The Pareto Analysis (The 80/20 Rule)
Rank your assets by two distinct variables:
*   **Failure Frequency:** The total number of unplanned work orders per asset.
*   **Total Downtime/Cost:** The sum of labor hours, spare parts costs, and lost production value.

Typically, the top 5% to 10% of your assets will account for more than 50% of your total maintenance spend. These are your primary bad actors. For example, if a specific labeling machine fails 15 times a month for minor adjustments, it is a bad actor, even if each failure only lasts 10 minutes.

#### 3. MTBF and MTTR Calculation
Calculate the Mean Time Between Failures (MTBF) to identify assets with "short cycles." If an asset’s MTBF is shorter than its scheduled PM interval, the PM program is failing to address the physics of failure. Conversely, analyze Mean Time to Repair (MTTR) to find assets that are difficult to service, which often indicates poor design or lack of technician training. You may find that [gearboxes fail every 6 months](/blog/why-gearboxes-fail-every-6-months-diagnosing-chronic-failure-cycles) due to systemic alignment issues rather than component quality.

#### 4. Asset Criticality Ranking (ACR)
Cross-reference your Pareto list with an Asset Criticality Ranking. A bad actor on a non-critical "run-to-fail" asset is a nuisance; a bad actor on a bottleneck machine is a systemic threat. Focus your engineering resources only on bad actors that reside in the "High Criticality" quadrant of your matrix.

### Chronic vs. Sporadic Failures: Why Identification Matters
It is essential to distinguish between these two failure types. **Sporadic failures** are sudden, dramatic, and usually have a single root cause (e.g., a lightning strike or a forklift hitting a panel). **Chronic failures** are the "bad actors"—they are frequent, often perceived as "normal" by operators, and usually have multiple contributing factors like poor lubrication, improper startup procedures, or [post-sanitation breakdown physics](/blog/why-machines-fail-after-cleaning-shifts-the-physics-of-post-sanitation-breakdown).

According to the [Society for Maintenance & Reliability Professionals (SMRP)](https://smrp.org), eliminating chronic failures can reduce overall maintenance costs by up to 60%, as these failures represent the majority of "hidden" factory waste.

### What To Do Once Bad Actors Are Identified

Once you have identified your top 10 bad actors, you must move from identification to elimination.

1.  **Perform a Forensic Root Cause Analysis (RCA):** Do not simply replace the part. Investigate why the failure is repeating. For instance, if motors are the bad actor, investigate if [motors run hot after service](/blog/the-maintenance-paradox-why-motors-run-hot-after-service) due to improper installation or over-greasing.
2.  **Optimize Preventive Maintenance (PM):** Many bad actors are actually caused by "over-maintenance" or intrusive PMs that introduce infant mortality. Use the data to [eliminate chronic machine failures](/blog/how-to-eliminate-chronic-machine-failures-and-repeated-downtime) by switching from calendar-based tasks to condition-based monitoring.
3.  **Deploy Targeted Condition Monitoring:** For assets that remain bad actors despite RCA, deploy continuous monitoring. **Factory AI** offers a sensor-agnostic, brownfield-ready solution that can be deployed in under 14 days. Unlike traditional vibration checks that only provide snapshots, Factory AI uses high-frequency data to detect the specific "signatures" of chronic degradation before they result in a work order. This is particularly effective for complex systems like [servo motors that fail unpredictably](/blog/root-cause-analysis-why-servo-motors-fail-unpredictably).
4.  **Redesign or Replace:** If the TCO of a bad actor exceeds 50% of its replacement value within three years, the asset should be flagged for capital replacement.

### Related Questions

**What is the difference between a bad actor and a critical asset?**
A critical asset is a machine that is essential to production (e.g., a main boiler), while a bad actor is a machine that fails frequently (e.g., a specific conveyor). An asset can be both, but bad actor identification focuses on failure frequency and cost, whereas criticality focuses on the consequences of failure.

**How often should a Bad Actor Audit be performed?**
A formal Bad Actor Audit should be performed quarterly. This frequency allows maintenance managers to see if their RCA and PM optimization efforts are actually moving assets off the Pareto "Top 10" list or if new bad actors are emerging due to changes in production speed or raw materials.

**Can software identify bad actors automatically?**
Yes, modern CMMS and AI platforms like Factory AI can automate bad actor identification. By integrating real-time machine health data with maintenance logs, these systems can flag assets that are deviating from their baseline MTBF in real-time, allowing for intervention before the asset becomes a top-tier Pareto offender. This bridges the gap for teams where [technicians don't trust maintenance data](/blog/why-technicians-dont-trust-maintenance-data-diagnosing-the-systemic-trust-failure) by providing objective, physics-based evidence of failure.

**What is the "Maintenance Paradox" in bad actor identification?**
The maintenance paradox occurs when increasing the frequency of PMs on a bad actor actually increases its failure rate. This is usually due to "maintenance-induced failures," where reassembly errors or lubrication contamination occur during the PM itself. Identifying this requires looking for failures that occur within 48 hours of a PM intervention.