# What is FFI (Failure Finding Interval) and Why Is It the Most Critical Metric for Hidden Failures?

**Keyword:** ffi

**Meta Title:** FFI in Maintenance: Calculating Failure Finding Intervals

**Meta Description:** What is FFI? In maintenance, the Failure Finding Interval is critical for managing hidden failures in protective devices. Learn to calculate and optimize it.

**Word Count:** 2403

**Link Count:** 8

---

If you are a software developer, "FFI" means Foreign Function Interface. If you are in finance, it means Foreign Financial Institution. But if you are a maintenance manager, reliability engineer, or plant operator reading this in 2026, **FFI stands for Failure Finding Interval.**

It is arguably the most misunderstood concept in the reliability world, yet it is the only barrier standing between a minor operational hiccup and a catastrophic safety incident.

So, what exactly is the Failure Finding Interval?

**The Failure Finding Interval (FFI) is the frequency at which a maintenance team must inspect or test a protective device to determine if it has failed.**

Unlike standard assets (like motors or conveyors) that make noise, vibrate, or smoke when they fail, protective devices suffer from **Hidden Failures**. A pressure relief valve, a high-temperature trip switch, or a backup diesel generator does not tell you it is broken until you actually need it. If it has failed silently, and a demand event occurs, the result is a multiple failure scenario that often leads to injury, environmental damage, or massive asset destruction.

The FFI is the mathematical answer to the question: *"How often do I need to check this silent guardian to ensure the risk of it failing when I need it is acceptably low?"*

In this comprehensive guide, we will move beyond the basic definition. We will explore how to calculate FFI using reliability formulas, how it differs from standard Preventive Maintenance (PM), and how to implement a rigorous Failure Finding strategy within your [asset management](/features/asset-management) program.

---

## The Core Problem: What Are Hidden Failures and Why Do They Require FFI?

To understand FFI, you must first understand the nature of the assets it protects. Most maintenance strategies—Predictive Maintenance (PdM) and Preventive Maintenance (PM)—are designed for **evident failures**.

*   **Evident Failure:** A pump bearing seizes. You hear it screeching. The line stops. The failure is obvious to the operator.
*   **Hidden Failure:** A high-level alarm on a chemical tank burns out. The tank looks normal. The process continues. The failure is *not* evident until the tank overfills and the alarm fails to sound.

FFI is exclusively designed for the latter. These are typically **protective devices**.

### The Protective Device Paradox
Protective devices are unique because their sole function is to sit idle and wait for something else to go wrong. Because they are idle, they do not wear out in the traditional sense (friction, heat, fatigue) that a running motor does. Therefore, traditional usage-based maintenance (e.g., "replace every 500 running hours") is often irrelevant because the device has zero running hours.

However, they can still fail due to corrosion, electronic degradation, seizure from inactivity, or insect infestation.

Because the failure is hidden, the only way to know the device is working is to force it to work. You must simulate the alarm, trip the breaker, or pop the valve. This is called a **Failure Finding Task**. The FFI is simply the schedule for that task.

### The Consequence of Ignoring FFI
If you do not have a calculated FFI, you are likely doing one of two things:
1.  **Over-maintaining:** Testing the device so often that you are introducing wear or wasting labor hours.
2.  **Under-maintaining:** Leaving the device unchecked for so long that the probability of it being in a failed state approaches 100%.

If a protective device has failed (Hidden Failure) and the event it guards against happens (Demand Event), you enter the realm of **Multiple Failures**. This is where industrial disasters happen. FFI is the mathematical lever we pull to reduce the probability of that Multiple Failure to a level the business (and the law) can accept.

---

## How Do You Calculate the Correct Failure Finding Interval?

This is the most common follow-up question: *"I know I need to check my safety valves, but is 'once a year' enough? Should it be monthly?"*

In 2026, guessing is no longer an acceptable maintenance strategy. We must use the math provided by Reliability Centered Maintenance (RCM) principles, specifically SAE JA1011 standards.

The calculation of FFI is a trade-off between the **Mean Time Between Failures (MTBF)** of the protective device and the **Required Availability** of that device.

### The Standard FFI Formula
The simplified formula often used in RCM for determining the interval ($T_{FFI}$) is:

$$ T_{FFI} = \frac{2 \times M_{av} \times MTBF}{1} $$

Where:
*   **$T_{FFI}$**: The Failure Finding Interval (how often you check).
*   **$M_{av}$**: The Mean Unavailability you are willing to accept (the risk factor).
*   **MTBF**: The Mean Time Between Failures of the protective device itself.

*Note: There are more complex variations of this formula that account for the demand rate of the protected function, but this linear approximation is the industry standard for setting baselines.*

### A Practical Calculation Example
Let’s say you have a **High-Pressure Trip Switch** on a compressor.

1.  **Determine MTBF:** Based on manufacturer data or your own historical data, you know these switches tend to fail once every 50 years (438,000 hours).
2.  **Determine Acceptable Risk (Unavailability):** Your safety team determines that this switch must be available 99.5% of the time. Therefore, the acceptable **Unavailability** ($U$) is 0.5% (or 0.005).

Using a derived formula for Unavailability where $U = \frac{T_{FFI}}{2 \times MTBF}$:

$$ 0.005 = \frac{T_{FFI}}{2 \times 50 \text{ years}} $$

$$ T_{FFI} = 0.005 \times 100 \text{ years} $$

$$ T_{FFI} = 0.5 \text{ years} $$

**Result:** You must test this switch every **6 months**.

If you decided to test it only once a year, your unavailability doubles to 1%, meaning the risk of the safety system failing when needed has doubled. If you test it every month, you are achieving 99.9% availability, but you are spending 6x the labor.

### The Variable of "Demand Rate"
The formula above assumes the protective device is the only line of defense. However, you must also consider the **Demand Rate**—how often the compressor actually over-pressurizes.

If the compressor is brand new and highly reliable, the demand on the safety switch is low. If the compressor is old and unstable, the demand is high.
*   **High Demand Rate:** Requires a shorter FFI (more frequent testing).
*   **Low Demand Rate:** Allows for a longer FFI.

For complex calculations involving demand rates, reliability engineers often turn to Reliabilityweb or similar technical resources to model the probability of coincident failures.

---

## FFI vs. PM vs. PdM: What is the Difference?

Confusion between Failure Finding and Preventive Maintenance is the primary reason for poor data in a CMMS. Maintenance managers often lump FFI tasks under "PMs," but they are fundamentally different in intent and execution.

### 1. Preventive Maintenance (PM)
*   **Goal:** Prevent failure by restoring the asset.
*   **Action:** Lubrication, filter changes, belt replacements.
*   **Trigger:** Time or Usage (e.g., every 500 hours).
*   **Target:** Assets that wear out.
*   **Outcome:** The asset is in "like new" condition.

### 2. Predictive Maintenance (PdM)
*   **Goal:** Detect the onset of failure.
*   **Action:** Vibration analysis, thermography, oil analysis.
*   **Trigger:** Condition data.
*   **Target:** Assets that give warnings (P-F Curve).
*   **Outcome:** A scheduled repair before catastrophic failure.

### 3. Failure Finding (FFI)
*   **Goal:** Discover a failure that has *already happened* but is hidden.
*   **Action:** Functional testing (trip the breaker, switch the valve).
*   **Trigger:** The calculated FFI (Risk-based).
*   **Target:** Protective devices (Hidden failures).
*   **Outcome:** Confirmation that the device works, OR a repair order if it doesn't.

**Key Distinction:** When you finish a PM, you have prevented a failure. When you finish an FFI task, you haven't prevented anything—you have simply *checked* if it was already broken. This distinction is vital for how you structure your [preventive maintenance procedures](/features/pm-procedures).

If you classify FFI tasks as PMs, you skew your reliability data. A "passed" FFI task is not a maintenance action; it is an inspection. A "failed" FFI task means the plant was operating at risk for an unknown period of time.

---

## The "Testing Paradox": Can You Test Too Often?

Once maintenance teams understand FFI, the knee-jerk reaction is often: *"Let's test everything every week to be safe."*

This approach, while well-intentioned, introduces new risks. This is known as the **Testing Paradox** or **Maintenance Induced Failures**.

### 1. Wear from Testing
Imagine a standby diesel fire pump. It is designed to run in emergencies. If you start it cold, run it for 5 minutes, and shut it down every single week, you are introducing massive thermal stress and engine wear. You might actually *cause* the failure you are trying to detect.
*   **Solution:** The FFI calculation must account for the "cost" (in asset life) of the test itself.

### 2. The "Left in Failed State" Risk
Failure finding tasks are intrusive. You often have to bypass a safety system, physically manipulate a valve, or disconnect a wire to test it.
*   **The Risk:** The technician tests the system, finds it works perfectly, but **forgets to reset it** to automatic mode or forgets to reopen the valve.
*   **The Result:** You have now created a hidden failure *because* you did the inspection.
*   **Mitigation:** FFI procedures must always include a "Return to Service" checklist step that is verified by a second person or a digital handshake in your [work order software](/features/work-order-software).

### 3. Production Interruption
Some FFI tasks require shutting down the main line. If the FFI is too short (frequent), production losses skyrocket. If the FFI is too long, safety risks skyrocket.
*   **Optimization:** This is where "Online Testing" capabilities become valuable. Modern equipment often includes "partial stroke testing" for valves, allowing FFI tasks to occur without stopping production.

---

## Implementing FFI in Your CMMS: A Step-by-Step Guide

Knowing the math is one thing; executing it in a busy facility is another. Here is how to operationalize FFI using modern maintenance software.

### Step 1: Identify Your Hidden Failures
You cannot set an FFI for assets you haven't identified. Conduct a Criticality Analysis or RCM study. Look specifically for:
*   Alarms and Annunciators.
*   Relief Valves (PRVs/PSVs).
*   Limit Switches and Trip devices.
*   Standby pumps and fans.
*   Ground Fault Circuit Interrupters (GFCIs).

### Step 2: Separate FFI Work Orders
Do not bury a failure finding task inside a generic PM checklist.
*   **Bad:** A 50-step PM for a conveyor that includes "Check emergency stop" as line item 42.
*   **Good:** A separate Work Order specifically for "Functional Test: Conveyor Emergency Stop."
Why? Because if line item 42 fails, the conveyor might still run, and the technician might just tick the box. By isolating it, you track the reliability of the safety device specifically.

### Step 3: Define the "Standard of Failure"
Technicians need to know exactly what constitutes a pass or fail.
*   *Vague:* "Check valve."
*   *Specific:* "Raise pressure to 150 PSI. Valve must lift between 148 and 152 PSI. If it lifts outside this range, mark as FAILED."

### Step 4: Automate the Schedule
Use your CMMS to lock in the intervals. Unlike PMs, which can sometimes be floated a few days, FFI tasks are regulatory or safety-critical. Use [mobile CMMS](/features/mobile-cmms) features to ensure technicians have the specific testing procedure right at the device, ensuring they don't skip the "Return to Service" steps.

### Step 5: Analyze the Findings
This is the loop-back. If you test a set of breakers every year and they *never* fail, your MTBF is likely higher than you thought. You can safely extend the FFI to 18 months or 2 years (saving money). Conversely, if you test them every year and 20% of them fail, you need to shorten the FFI immediately.

---

## Advanced FFI Strategies for 2026: AI and Real-Time Data

The formula $T_{FFI} = \frac{2 \times M_{av} \times MTBF}{1}$ relies on MTBF. Historically, MTBF was a static number grabbed from a manufacturer's manual. In 2026, we have better data.

### Dynamic MTBF with AI
With [AI predictive maintenance](/features/ai-predictive-maintenance), we can move from a static MTBF to a dynamic reliability score.
*   **Scenario:** You have 50 identical pressure switches. 25 are in a clean, climate-controlled room. 25 are in a corrosive, outdoor environment.
*   **Old Way:** All 50 get the same FFI based on the manual.
*   **New Way:** AI analyzes the failure history. It recognizes that the outdoor switches fail 3x faster. It automatically recommends shortening the FFI for the outdoor units and extending it for the indoor units. This is **Prescriptive Maintenance**.

### Self-Diagnostic Systems
The ultimate goal is to eliminate the manual FFI task entirely. Modern smart valves and digital switchgear perform continuous self-diagnostics.
*   Instead of sending a human to test the device (FFI), the device sends a signal to the CMMS if its internal circuitry detects a fault.
*   This shifts the asset from "Hidden Failure" to "Evident Failure," effectively removing the need for an FFI calculation and replacing it with real-time condition monitoring.

However, even smart devices have mechanical components (the physical spring in the valve) that electronics cannot test. Therefore, manual FFI tasks will remain a requirement for the mechanical aspects of protective devices for the foreseeable future.

---

## Summary: The FFI Decision Framework

To wrap up, use this framework when evaluating your facility's safety systems:

1.  **Is the failure evident to the operator?**
    *   **Yes:** Use Condition Monitoring or PM.
    *   **No:** It is a Hidden Failure. Proceed to step 2.
2.  **Is there a sensor that can monitor the condition continuously?**
    *   **Yes:** Use [Predictive Maintenance](/products/predict).
    *   **No:** You must use Failure Finding. Proceed to step 3.
3.  **What is the consequence of a multiple failure?**
    *   **Safety/Environmental:** Set a high availability target (e.g., 99.9%). Calculate FFI strictly.
    *   **Economic only:** Compare the cost of the inspection vs. the cost of the risk.
4.  **Execute and Verify.**
    *   Schedule the task.
    *   Ensure the device is returned to service.
    *   Record the result (Pass/Fail) to update your MTBF data.

FFI is not just an acronym; it is the discipline of finding risks before they find you. By moving from "guessing" to "calculating," you transition your maintenance department from a cost center to a true risk-management organization.

For more on establishing reliability standards, organizations like the [International Society of Automation (ISA)](https://www.isa.org) provide deep dives into safety instrumented systems (SIS) which rely heavily on FFI logic.

If you are ready to start tracking your Failure Finding Intervals with precision, explore how our [preventive maintenance software](/products/prevent) can help you isolate, schedule, and analyze these critical tasks.