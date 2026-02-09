# How to Review Preventive Maintenance Plans: The "Kill Your Darlings" Approach to Reliability

**Keyword:** how to review preventive maintenance plans

**Meta Title:** How to Review Preventive Maintenance Plans: A PMO Guide (2026)

**Meta Description:** Stop pencil-whipping. Learn how to review preventive maintenance plans using reliability engineering principles to cut backlog, reduce costs, and improve

**Word Count:** 2435

**Link Count:** 6

---

You are likely reading this because you have a problem. It’s probably one of two scenarios: either your maintenance backlog has become an insurmountable mountain of overdue work orders, or your team is hitting 95% PM compliance, yet your assets are still failing unexpectedly.

In 2026, the era of "more maintenance is better maintenance" is dead. The modern Maintenance Manager doesn't ask, "Did we do the maintenance?" They ask, "Did the maintenance actually reduce risk?"

When you search for "how to review preventive maintenance plans," you aren't looking for a tutorial on how to edit a calendar entry in your CMMS. You are looking for a framework to audit the *value* of the work your team performs. You are looking for **PM Optimization (PMO)**.

This guide takes a Reliability Engineering approach, simplified for operational leadership. We are going to explore how to audit your current strategy, identify the "waste" tasks that are consuming your budget, and transition from a time-based culture to a condition-based reality.

---

## The Core Question: Why Do Most PM Plans Fail Despite High Compliance?

Before we open a spreadsheet or log into the CMMS, we must answer the fundamental question: **Why isn't the current plan working?**

The answer usually lies in the "PM Creep." Over the last decade, whenever a machine failed, the immediate corrective action was often: *"Add a PM to check that next time."*

Fast forward five years, and you have a weekly PM checklist with 45 line items. Your technicians, pressed for time, begin "pencil-whipping" the list—checking boxes without actually inspecting the asset—because physically performing 45 checks in the allotted 30 minutes is impossible.

### The "Kill Your Darlings" Philosophy
To review a preventive maintenance plan effectively, you must adopt a subtractive mindset. Your goal is not to add more checks; it is to remove everything that does not directly link to a specific failure mode.

A successful PM review validates every single task against three criteria:
1.  **Is the failure mode credible?** (Is this actually likely to break?)
2.  **Is the task actionable?** (Does "Check Motor" tell the tech what to do? No. "Measure drive-end bearing temperature" does.)
3.  **Is the frequency correct?** (Are we checking a belt for wear every week when the P-F interval is three months?)

If a task doesn't pass these filters, it must be modified or deleted. This is the "Kill Your Darlings" phase of reliability. You must be willing to delete legacy tasks that make you feel safe but provide no technical value.

---

## Phase 1: Prioritization – Which Assets Do I Review First?

**Follow-up Question:** "I have 2,000 assets in my facility. I can't review every single PM plan this month. How do I prioritize?"

You cannot—and should not—apply the same level of scrutiny to a bathroom exhaust fan as you do to your primary CNC machining center or the facility's main air compressor. The first step in your review process is **Asset Criticality Analysis (ACA)**.

### The Criticality Matrix
If you haven't ranked your assets, pause the PM review and do this first. You need to categorize assets based on two axes:
1.  **Severity of Failure:** If this goes down, does production stop? is safety compromised? Is there an environmental impact?
2.  **Probability of Failure:** How old is the asset? What is its history?

Group your assets into three tiers:
*   **Critical (Top 10-15%):** Immediate production loss, safety risk, or high capital cost.
*   **Essential (Middle 30-40%):** Production slows down or can be buffered; redundancy exists.
*   **Non-Essential (Bottom 40-50%):** Run-to-failure is an acceptable strategy.

### The Review Strategy by Tier
*   **For Critical Assets:** You will perform a full Reliability Centered Maintenance (RCM) style review. Every bolt, belt, and sensor gets scrutinized. You will likely integrate [predictive maintenance solutions](/products/predict) here.
*   **For Essential Assets:** You will perform a "PM Optimization" (PMO) blitz. This is a faster review focused on cleaning up task lists and adjusting frequencies based on OEM guidelines and experience.
*   **For Non-Essential Assets:** The review is simple—**delete the PMs.** If a $50 exhaust fan takes $200 of labor a year to inspect, and a replacement costs $100, you are losing money by maintaining it. Switch to "Run-to-Failure."

---

## Phase 2: The Task Audit – Moving from "Inspect" to "Measure"

**Follow-up Question:** "Okay, I've picked my critical conveyor system. I'm looking at the PM list. How do I know if a specific task is good or bad?"

This is where the rubber meets the road. Most legacy PM plans are plagued by vague, qualitative language.

### The Problem with "Check" and "Inspect"
Look at your current PM procedures. If you see tasks like:
*   *Check chain tension.*
*   *Inspect hydraulic oil.*
*   *Listen for noise.*

These are bad PMs. Why? Because they rely entirely on the subjective opinion of the technician. One tech’s "loose" is another tech’s "fine."

### The Quantitative Transformation
To review and fix these, you must translate them into quantitative specifications with clear pass/fail criteria.

**Bad Task:** "Check conveyor belt tension."
**Optimized Task:** "Measure belt tension using sonic tension meter. Value must be between 45Hz and 50Hz. If <45Hz, re-tension. If >50Hz, loosen."

**Bad Task:** "Inspect hydraulic oil."
**Optimized Task:** "Pull oil sample for particle count analysis. Verify ISO code is below 18/16/13. Check sight glass level is between min/max lines."

### The Failure Mode Connection
For every task, ask: **"What Failure Mode is this preventing?"**
If the task is "Grease Bearings," the failure mode is "Bearing seizure due to lack of lubrication."
However, if you grease a sealed bearing, you are *causing* a failure mode (over-greasing/seal rupture).

During your review, map every task to a failure mode. If you find a task that says "Wipe down cabinet," and you cannot identify a mechanical failure mode that dirt causes (e.g., overheating due to blocked vents), move that task to a cleaning schedule or operator checklist. It does not belong in a skilled trade PM.

For more on structuring these lists, look into dedicated [PM procedures](/features/pm-procedures) tools that force this level of detail.

---

## Phase 3: The Frequency Trap – OEM vs. Real-World Usage

**Follow-up Question:** "The manufacturer says I need to change the oil every 500 hours. Should I just stick to that?"

This is one of the most controversial parts of a PM review. The Original Equipment Manufacturer (OEM) guidelines are the starting point, not the bible.

### The OEM Conflict of Interest
OEMs write maintenance manuals to:
1.  Protect their warranty liability.
2.  Sell spare parts.
3.  Cover the "worst-case scenario" operating environment.

If the manual says "Replace bearings every 2,000 hours," they assume you might be running the machine at max load in a dusty, hot environment. If you are running it at 50% load in a climate-controlled clean room, replacing that bearing at 2,000 hours is a waste of money and downtime.

### Adjusting Frequency with Data
To review frequency, you need to look at your Work Order History and MTBF (Mean Time Between Failures).

*   **Scenario A:** You have a PM to replace a filter every month. You look at the history, and the filter is always clean when removed.
    *   *Action:* Extend the frequency to 2 months. Monitor.
*   **Scenario B:** You have a PM to tension a chain every 6 months. History shows three corrective work orders for "chain fell off" in between the PMs.
    *   *Action:* Shorten the frequency to 3 months, or investigate why the chain is stretching (root cause analysis).

### The P-F Curve Logic
The frequency of an inspection should be determined by the **P-F Interval**. This is the time between the point where a **P**otential failure is detectable and the point of **F**unctional failure.

If a bearing starts making noise (Potential failure) 4 weeks before it seizes (Functional failure), checking it every 8 weeks is useless. The failure could start and finish in the gap between your checks. Your inspection interval must be *shorter* than the P-F interval (typically half the P-F interval is the rule of thumb).

---

## Phase 4: Transitioning to Condition-Based Maintenance (CbM)

**Follow-up Question:** "I can't check everything every day. How do I stop doing time-based maintenance altogether?"

The ultimate goal of reviewing your PM plan is to destroy it—or rather, to transform it into a Condition-Based Maintenance (CbM) plan.

Time-based maintenance assumes that machines wear out in a linear fashion (e.g., "it's been 3 months, so it must be broken"). Reliability studies (like the famous Nolan & Heap study) show that **89% of failure modes are random**, not age-related.

### Replacing Tasks with Sensors
In your review, identify tasks that are purely "inspection" and see if technology can do them for you 24/7.

*   **Manual Task:** Technicians walk around with a vibration pen once a month to check [motors](/solutions/predictive-maintenance-motors).
    *   *Review Decision:* Replace with wireless vibration sensors.
    *   *Benefit:* You get data every minute, not every month. You catch the failure the moment it starts.
*   **Manual Task:** Technician checks temperature of electrical panels.
    *   *Review Decision:* Install thermal cameras or continuous thermal monitoring.

By integrating [AI predictive maintenance](/features/ai-predictive-maintenance), you move from "Reviewing the PM schedule" to "Reviewing the Asset Health Dashboard." The PM is no longer a recurring calendar invite; it is a work order triggered automatically when the asset actually needs help.

---

## Phase 5: The Human Element – Who Should Be in the Room?

**Follow-up Question:** "Can I do this review alone in my office, or do I need a team?"

Reviewing PMs in a vacuum is a recipe for disaster. If you (the Manager) rewrite the plan without consulting the people turning the wrenches, you will miss critical on-the-ground reality.

### The PMO Workshop
Host a "PM Optimization Workshop." For a critical asset, this might take 1-2 days. For smaller assets, it might be an hour.

**Attendees:**
1.  **Reliability Engineer/Manager:** Facilitates the process and enforces the methodology.
2.  **Senior Technician:** The person who knows the machine best. They know which PMs are "garbage" and which ones save the day.
3.  **Machine Operator:** Often overlooked, but they know what the machine sounds like before it breaks. They can tell you, "It always jams when we run product X."

### The Feedback Loop
During the review, ask the technician:
*   "When you do this PM, do you ever find anything wrong?"
*   "Is this task dangerous to perform?"
*   "Do you have to remove guards to do this? If so, can we install an inspection window instead?"

This collaborative approach not only improves the plan but also buys "buy-in" from the team. When the new PM plan rolls out, they will follow it because they helped write it.

---

## Phase 6: Handling Intrusive Maintenance

**Follow-up Question:** "What about tasks that require shutting down the machine and taking it apart? Are those worth it?"

Intrusive maintenance (opening a machine to inspect it) carries a risk: **Infant Mortality.** Every time you open a gearbox or pull a pump apart, you risk introducing contaminants, damaging seals, or reassembling it incorrectly.

### The "Do No Harm" Rule
In your review, scrutinize intrusive tasks heavily.
*   *Task:* "Open casing to inspect gears."
*   *Challenge:* Can we use oil analysis instead? Can we use vibration analysis?
*   *Goal:* Eliminate intrusive inspections unless absolutely necessary.

If you must perform intrusive maintenance, ensure the procedure includes strict quality assurance steps (e.g., torque specs, cleanliness standards) to prevent human error during reassembly.

---

## Phase 7: Measuring Success – ROI and KPIs

**Follow-up Question:** "I've spent weeks reviewing these plans. How do I prove to upper management that this was a good use of time?"

You need to track the right KPIs before and after the review.

### 1. PM to CM Ratio
Ideally, your work mix should be roughly 6:1 (6 Preventive/Predictive jobs for every 1 Corrective job). If you are currently at 1:1, your PM review should aim to shift this.
*   *Warning:* Don't just look at the *number* of PMs. If you delete 50% of your useless PMs, your total PM count goes down, which is good! Look at the **Emergency Work Hours**. If PM count drops but Emergency Work stays flat or drops, you have successfully optimized.

### 2. Schedule Compliance vs. PM Yield
*   **Schedule Compliance:** Did we do the PM on time? (Standard metric).
*   **PM Yield:** Did the PM result in a follow-up corrective work order?
    *   If you inspect a belt 50 times and never find an issue, the yield is 0%. The frequency is too high.
    *   If you inspect it and find a defect, the PM did its job.
    *   *Goal:* You actually want a PM yield of roughly 10-15%. If it's 0%, you're over-maintaining. If it's 50%, you're under-maintaining (or the asset is end-of-life).

### 3. Backlog Reduction
A successful review often results in a massive reduction of the "nuisance backlog." By eliminating non-value-added tasks, you free up [work order software](/features/work-order-software) queues, allowing technicians to focus on the high-priority work that actually improves reliability.

---

## Phase 8: Tools and Sustainability

**Follow-up Question:** "How do I keep the plan from getting bloated again in the future?"

Optimization is not a one-time event; it is a continuous loop. However, manual spreadsheets won't cut it in 2026.

### Leveraging the CMMS
Your [CMMS software](/products/cmms-software) should be the guardian of your PM plan. Use it to:
*   **Force Mandatory Fields:** Require techs to enter measurement data (not just "Done").
*   **Track Failure Codes:** When a machine breaks, require a specific failure code (e.g., "Bearing - Wear"). Review these codes quarterly to adjust PMs.

### The Role of AI
Modern platforms use AI to analyze the descriptions in your work orders. They can flag anomalies like, "You have replaced this seal 4 times in 2 months—consider reviewing the PM procedure for installation errors."

### Continuous Improvement Triggers
Set up triggers for a "Mini-Review":
1.  **After any catastrophic failure:** Perform a Root Cause Analysis (RCA) and update the PM plan immediately.
2.  **New Equipment Installation:** Don't just copy the OEM manual. Review it immediately.
3.  **Annually:** Pick the "Top 10 Bad Actors" (assets with the most downtime) and re-audit their plans.

## Conclusion

Reviewing preventive maintenance plans is the single most effective lever a Maintenance Manager can pull to improve reliability. It costs very little in terms of capital but pays massive dividends in labor efficiency and asset uptime.

Start small. Pick one critical asset. Gather your team. Ask the hard questions about every single task. If it doesn't detect a failure or prevent one, kill it.

The goal is not to be busy; the goal is to be reliable.