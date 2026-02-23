# How to Build an Event-Driven Monitoring Strategy for Intermittent Assets

**Keyword:** how to monitor intermittent equipment

**Meta Title:** How to Monitor Intermittent Equipment: Event-Driven Guide

**Meta Description:** Monitor intermittent equipment using event-triggered data acquisition. Synchronize sensor readings with machine states to prevent startup and standby failures.

**Word Count:** 1015

**Link Count:** 4

---

To monitor intermittent equipment effectively, you must implement an **event-triggered data acquisition strategy** that synchronizes sensor measurements with the machine’s operational state (Run, Idle, or Off). Unlike continuous-duty assets, intermittent machines require high-frequency "burst" sampling during transient states—specifically startup, peak load, and shutdown—to capture the mechanical and thermal stresses that lead to failure. Monitoring these assets on a fixed time interval (e.g., once per hour) often results in "silent failures" because the data is collected while the machine is stationary or in an unloaded state.

Effective monitoring relies on integrating usage-based data (run-time hours or cycle counts) with condition-based inputs (vibration, temperature, or current). By using Edge computing or PLC integration to trigger data capture only when the asset is active, you eliminate "data noise" and ensure that [intermittent machines don't fail without warning](/blog/why-intermittent-machines-fail-without-warning-the-physics-of-startup-stress-and-standby-degradation) due to the unique physics of startup stress and standby degradation.

### The Step-by-Step Process for Intermittent Monitoring

Monitoring non-continuous assets requires a departure from traditional "always-on" or "calendar-based" approaches. Follow this four-step process to establish a reliable event-driven monitoring framework.

#### 1. Define the State Trigger
You cannot analyze intermittent data without knowing the machine's state. You must establish a "Trigger" that tells the monitoring system when to start and stop data collection.
*   **PLC Integration:** The most reliable method. Use a "Run" bit from the PLC to trigger the IoT gateway.
*   **Current Thresholds:** Use a split-core current transformer (CT) on the motor lead. If current exceeds a specific amperage (e.g., >2A), the system flags the asset as "Active."
*   **Vibration Thresholds:** Use a wireless vibration sensor with an internal wake-up threshold (e.g., 0.5 mm/s).

#### 2. Configure "Burst Mode" for Transient Analysis
Intermittent assets experience their highest failure rates during the first 60 seconds of operation. This is due to inrush current, rapid thermal expansion, and the lack of established lubrication films. 
*   **The Strategy:** Set your sensors to capture high-frequency data (1kHz to 20kHz) during the first 30 seconds of the "Run" state.
*   **Decision Point:** If the startup vibration profile deviates from the baseline by more than 15%, flag it as a "Startup Stress" event, even if the steady-state vibration remains within limits. This is often why [the engineering physics of peak production failures](/blog/the-engineering-physics-of-peak-production-failures-why-machines-break-when-you-need-them-most) occur—the damage happens before the machine even reaches full speed.

#### 3. Establish State-Dependent Baselines
A machine will have different "normal" signatures depending on its load and speed. For intermittent equipment, a single alarm threshold is useless.
*   **If Idle:** Monitor for "Standby Degradation" (e.g., rising bearing temperature due to nearby heat sources or external vibration causing false brinelling).
*   **If Running (Unloaded):** Establish a baseline for the mechanical health of the drivetrain.
*   **If Running (Full Load):** Establish a baseline for the process health and structural integrity.

#### 4. Monitor Standby Health
Intermittent equipment often fails because it sits idle. Lubricants settle, seals dry out, and moisture ingress occurs. 
*   **Action:** Program the monitoring system to "wake up" every 24 hours during idle periods to check for environmental factors. If humidity exceeds 60% or ambient temperature drops below the dew point, the system should trigger a "Warm-up Cycle" or a lubrication alert. This prevents the common issue where [calendar-based lubrication schedules fail](/blog/why-calendar-based-lubrication-schedules-fail-to-prevent-bearing-failures) because they don't account for the lack of grease distribution during long idle periods.

### What to Do About Intermittent Asset Failures

If your facility struggles with "unpredictable" failures on machines that run sporadically—such as sump pumps, backup compressors, or seasonal packaging lines—you must shift from reactive maintenance to a usage-based and condition-triggered model.

**Transition to Usage-Based Maintenance (UBM):**
Stop performing maintenance based on the months elapsed. Instead, use the data from your event-driven monitoring to trigger service based on actual run-time hours or cycles. For example, a gearbox should be serviced every 2,000 operating hours, whether that takes three months or three years.

**Implement Edge-to-Cloud Monitoring:**
To avoid overwhelming your network with useless "idle" data, use Edge computing devices. These devices process the data locally at the machine, only sending "exceptions" or "state-change summaries" to the cloud. This reduces data costs and ensures that when an alert is generated, it is based on a real mechanical deviation.

**Leverage Factory AI for Brownfield Integration:**
For older "brownfield" equipment that lacks modern PLC connectivity, **Factory AI** provides a sensor-agnostic, no-code solution. It can be deployed in under 14 days by attaching wireless sensors to intermittent assets. The AI automatically learns the "Run" vs. "Idle" states without manual programming, providing a health score that accounts for the stresses of frequent starts and stops. This bridges the gap where [vibration checks often fail to prevent failures](/blog/why-vibration-checks-dont-prevent-failures-the-gap-between-data-and-reliability) because the data wasn't captured during the critical startup window.

### Related Questions

**Why does calendar-based maintenance fail for intermittent assets?**
Calendar-based maintenance assumes a linear rate of wear, but intermittent assets suffer from "non-linear" degradation caused by startup cycles and standby corrosion. This leads to over-maintaining assets that haven't run, or under-maintaining assets that have been run at high intensity during peak production.

**What is the best way to track run-time hours on old machinery?**
The most cost-effective way is to install a wireless current-clamp sensor on the main power feed. By monitoring the amperage, the system can automatically log every second the motor is under load, providing accurate usage-based data without needing to tap into an old or proprietary PLC.

**How do you prevent "False Alarms" on intermittent equipment?**
False alarms are prevented by using "State-Masking." This involves programming the monitoring software to ignore data during the first 5-10 seconds of startup (where vibration is naturally high) and only comparing steady-state data against a baseline established for that specific load profile.

**Can AI predict failures on machines that only run once a week?**
Yes, provided the AI uses an event-driven model. By comparing the "Startup Signature" of the current run to the signatures of the previous 50 runs, AI can detect subtle changes in inrush current or vibration harmonics that indicate a looming failure, even with very limited data sets. Factory AI specializes in this type of "sparse data" analysis for intermittent industrial assets.