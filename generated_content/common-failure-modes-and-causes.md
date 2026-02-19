# Common Failure Modes and Causes: The Blueprint for Standardized Maintenance Reporting

**Keyword:** common failure modes and causes

**Meta Title:** Common Failure Modes vs. Causes: A Guide to Maintenance Taxonomy

**Meta Description:** Stop guessing. Learn the critical difference between failure modes and causes, and how to build a standardized failure taxonomy that drives asset reliability.

**Word Count:** 2267

**Link Count:** 6

---

If you walk into a maintenance shop and ask a technician why a conveyor stopped, they might say, "The motor burned out." If you ask the operator, they might say, "It just quit running." If you ask the reliability engineer, they might say, "Insulation breakdown due to thermal overload caused by restricted airflow."

All three are describing the same event, but they are speaking different languages. This disconnect is the primary reason why Computerized Maintenance Management Systems (CMMS) often become graveyards for bad data. When you cannot distinguish between what happened (the failure mode) and why it happened (the failure cause), you cannot prevent it from happening again.

In 2026, where AI-driven predictive maintenance is becoming the standard, garbage data is more dangerous than ever. You cannot train an algorithm on "It broke."

This guide answers the core question: **How do we distinguish between failure modes and causes to build a maintenance taxonomy that actually reduces downtime?** We will move beyond dictionary definitions into the physics of failure, the structure of ISO 14224, and how to configure your software to capture data that matters.

---

## The Core Distinction: Mode vs. Cause vs. Effect

The most common mistake in maintenance reporting is conflating the symptom with the disease. To build a robust reliability strategy, you must separate the event into three distinct chronological buckets.

### What is a Failure Mode?
A **Failure Mode** is the manner in which a failure is observed. It is the physical description of *how* the asset or component failed to perform its intended function. It is the "what happened" at the component level.

*   **Key Characteristic:** It is observable.
*   **Examples:** Seized bearing, fractured shaft, shorted circuit, leaking seal.

### What is a Failure Cause?
A **Failure Cause** is the physical, human, or systemic condition that led to the failure mode. It is the "why" behind the event. Without identifying the cause, any repair is merely a temporary patch.

*   **Key Characteristic:** It usually requires investigation (Root Cause Analysis) to confirm.
*   **Examples:** Lubricant contamination, misalignment, voltage spike, operator error, fatigue.

### What is a Failure Effect?
The **Failure Effect** is the consequence of the failure mode on the operation, the system, or the environment. This is what the operator usually notices first.

*   **Key Characteristic:** It describes impact (Safety, Environmental, Production).
*   **Examples:** Line stoppage, fire, hazardous leak, loud noise, loss of pressure.

### The Chain of Events: A Practical Example
Let’s look at a centrifugal pump to see how these link together.

1.  **Failure Cause:** The alignment shims were installed incorrectly (Human/Physical Cause), leading to severe misalignment.
2.  **Failure Mode:** The inboard bearing seized (Component Failure Mode).
3.  **Failure Effect:** The pump stopped pumping fluid, causing the downstream mixer to starve and the production line to halt (System Effect).

If your [asset management](/features/asset-management) strategy only records "Pump Stopped," you have recorded the effect, but you have zero insight into how to prevent it. If you record "Bearing Seized," you know what to replace, but not how to stop it from seizing again next month. Only by linking Cause, Mode, and Effect do you get a complete picture.

---

## The "Big Six" Mechanical Failure Modes: The Physics of Breakdown

Once you understand the taxonomy, the next logical question is: **What are the specific failure modes I should be looking for?**

While there are hundreds of specific failures, roughly 80% of mechanical failures in industrial environments fall into six categories of physical degradation. Understanding the physics behind these modes allows your technicians to identify them correctly rather than using generic terms like "broken."

### 1. Fatigue (Cyclic Stress)
Fatigue is the most common cause of structural failure in rotating equipment. It occurs when a material is subjected to repeated loading and unloading. Even if the stress loads are well below the material's yield strength, the repetition creates microscopic cracks that propagate over time.

*   **Visual Identification:** Look for "beach marks" or "clam shell marks" on the fracture surface. These lines show the progression of the crack before the final catastrophic snap.
*   **Common Contexts:** Shafts, gear teeth, and bolts subjected to vibration.

### 2. Surface Degradation (Wear)
This category covers the removal of material from a surface. It is the domain of tribology.
*   **Abrasive Wear:** Hard particles (contaminants) get between two moving surfaces and cut into them. It looks like scratching or grooving.
*   **Adhesive Wear:** Two surfaces weld together microscopically and tear apart. This is often called "galling" or "scuffing" and usually indicates lubrication failure.
*   **Erosive Wear:** Caused by fluid or gas carrying particles striking a surface. Common in pipe elbows and pump impellers.

### 3. Corrosion (Chemical Attack)
Corrosion is the degradation of material due to a reaction with its environment.
*   **Uniform Corrosion:** Rust across the whole surface.
*   **Pitting:** Localized, deep holes. This is dangerous because it can penetrate pipe walls rapidly while the surrounding metal looks fine.
*   **Galvanic Corrosion:** Occurs when two dissimilar metals are in electrical contact in a conductive fluid (electrolyte). The anode corrodes to protect the cathode.

### 4. Overload (Yielding/Brittle Fracture)
This happens when the stress applied to a component exceeds its strength.
*   **Ductile Fracture:** The part stretches or deforms before breaking. You will see "necking" at the break point.
*   **Brittle Fracture:** The part snaps suddenly with no warning or deformation. This often happens in cold temperatures or with hardened materials.

### 5. Thermal Degradation
Heat changes the properties of materials.
*   **Metals:** Can undergo creep (slow deformation under stress at high temps) or changes in hardness.
*   **Polymers/Seals:** Hardening, cracking, or melting. O-rings that come out square-shaped and brittle have suffered thermal set.

### 6. Cavitation
Specific to pumps and valves, cavitation occurs when pressure drops below the vapor pressure of the liquid, forming bubbles. When these bubbles move to a higher-pressure zone, they collapse (implode) with massive force, blasting material off the impeller or housing.
*   **Audible Symptom:** Sounds like gravel passing through the pump.
*   **Visual Symptom:** The metal looks like a sponge or Swiss cheese.

For detailed strategies on detecting these issues in fluid handling systems, refer to our guide on [predictive maintenance for pumps](/solutions/predictive-maintenance-pumps).

---

## Electrical Failure Modes: The Invisible Threat

Mechanical failures often give visual warnings. Electrical failures are often binary: they work until they don't, or they fail catastrophically. However, the *modes* of failure are distinct.

### Dielectric Breakdown (Insulation Failure)
This is the number one enemy of electric motors. Insulation degrades due to heat, contamination, or voltage spikes.
*   **Short to Ground:** Current jumps from the winding to the motor frame.
*   **Turn-to-Turn Short:** Insulation fails between two windings in the same coil. This creates a localized hot spot that rapidly destroys the motor.

### Contact Resistance (High Resistance Connection)
Loose connections, corrosion, or oxidation increase resistance. According to Ohm's Law ($P=I^2R$), increased resistance with constant current leads to heat generation.
*   **Detection:** Infrared thermography is the primary tool here. A "hot connection" is a failure mode in progress.

### Voltage Imbalance
While technically a power quality issue (cause), it leads to the failure mode of **overheating**. A 3.5% voltage imbalance can cause a 25% increase in temperature in the motor windings.

For more on monitoring these electrical signatures, explore [predictive maintenance for motors](/solutions/predictive-maintenance-motors).

---

## Root Causes: Digging Deeper (The "Why")

You have identified the mode (e.g., Bearing Seized). Now, the natural follow-up question is: **How do we find the true cause so we aren't just swapping parts?**

Reliability engineers often use the "Swiss Cheese Model" or "Latent Cause Analysis." Causes generally fall into three layers:

### 1. Physical Roots (The Direct Cause)
This is the physics that triggered the mode.
*   *Example:* The lubricant film broke down.
*   *Example:* The voltage spiked to 600V.

### 2. Human Roots (The Intervention)
This is the action (or inaction) taken by a person.
*   *Example:* The technician applied the wrong grease type.
*   *Example:* The operator ignored the high-vibration alarm.

### 3. Latent/System Roots (The Management System)
This is the deficiency in the management system that allowed the human error to occur. **This is where you solve the problem permanently.**
*   *Example:* There was no standard operating procedure (SOP) defining which grease to use.
*   *Example:* The training program for new operators does not cover alarm protocols.

If you stop at the Physical Root, you fix the machine. If you stop at the Human Root, you blame the mechanic. If you solve the Latent Root, you fix the organization.

Implementing robust [PM procedures](/features/pm-procedures) is often the solution to Latent Roots. If the procedure doesn't exist or is outdated, the failure is guaranteed to recur.

---

## Building a Failure Taxonomy in Your CMMS

Now we move to the practical application. **How do you configure your software to capture this data without overwhelming your team?**

Many organizations fail here by allowing "free text" entry for failure reporting. This results in data like "busted," "fried," "broken," and "fixed." You cannot analyze free text. You need a structured hierarchy.

### The ISO 14224 Standard
The oil and gas industry developed ISO 14224 to standardize reliability data, but its principles apply to manufacturing, food and bev, and facilities. It suggests a hierarchy:

1.  **Equipment Class** (e.g., Pump, Centrifugal)
2.  **Maintainable Item** (e.g., Bearing Assembly)
3.  **Failure Mode** (e.g., Seized, Leaking, Vibration High)
4.  **Failure Cause** (e.g., Wear, Misalignment, Operator Error)

### Best Practices for CMMS Configuration
When setting up your [CMMS software](/products/cmms-software), follow these rules:

1.  **Limit the Choices:** Do not give technicians a list of 500 failure modes. Use "Smart Filtering." If they select "Pump," show them pump-related modes (Leak, Cavitation, Seize). If they select "Conveyor," show them conveyor modes (Belt tracking, Motor trip).
2.  **Mandatory Fields:** Make "Failure Mode" a mandatory field for closing a Corrective Maintenance (CM) work order.
3.  **The "Other" Trap:** Do not include an "Other" option if you can avoid it. "Other" quickly becomes the top failure mode in every poorly managed database.
4.  **Separate Cause from Remedy:** "Replaced Bearing" is a remedy, not a cause. Ensure your CMMS has separate fields for "Action Taken" and "Failure Cause."

---

## The Role of AI and Predictive Maintenance in 2026

The traditional approach to failure modes is reactive: the failure happens, and we code it. The modern approach is proactive. **How does AI change how we detect failure modes?**

### The P-F Curve and Early Detection
The P-F curve illustrates the interval between a **Potential Failure (P)** (when a condition is detectable) and a **Functional Failure (F)** (when the asset stops working).

Different failure modes manifest at different points on the curve:
*   **Ultrasound:** Detects lubrication issues and early bearing fatigue (months before failure).
*   **Vibration:** Detects misalignment, imbalance, and looseness (weeks/months before failure).
*   **Thermography:** Detects electrical resistance and mechanical friction (weeks before failure).
*   **Noise/Heat:** Detects late-stage failure (days/hours before failure).

### AI as the Translator
In 2026, [AI predictive maintenance](/features/ai-predictive-maintenance) tools act as the translator between raw sensor data and failure mode identification.

Instead of a vibration analyst looking at a spectrum and saying, "I see a peak at 2x line frequency," the AI analyzes the pattern and outputs: **"Probability of Misalignment: 95%."**

This shifts the workflow from:
*   *Old Way:* Machine breaks -> Fix -> Record "Misalignment" in CMMS.
*   *New Way:* AI detects Misalignment signature -> Schedule alignment -> Prevent "Bearing Seizure" mode entirely.

---

## ROI: Why Standardization Pays Off

A common objection from management is: "Why do we need to spend time entering all these codes? Just fix it and get back to production."

**What is the business case for granular failure mode tracking?**

### 1. MTBF Accuracy
Mean Time Between Failures (MTBF) is a useless metric if you aggregate all failures. You need MTBF by Failure Mode. Knowing a pump fails every 6 months is okay. Knowing a pump fails due to *seal leakage* every 6 months tells you that you are buying the wrong seals or installing them wrong.

### 2. Spare Parts Optimization
If your data shows that "Electronic Card Failure" is rare but "Bearing Wear" is frequent, you can adjust your inventory. Stock more bearings, stock fewer cards. This frees up working capital.

### 3. Defensibility
When a catastrophic failure occurs, regulators or insurance auditors will ask for maintenance history. A log that says "Fixed" 10 times is a liability. A log that details specific modes, causes, and rectifications proves due diligence.

### 4. Automating Root Cause Analysis
If you have clean data, you can run a Pareto analysis (80/20 rule). "Show me the top 5 failure modes costing us the most downtime this year." You might find that 80% of your downtime comes from just two modes: "Limit Switch Jammed" and "Filter Clogged." You can now direct 100% of your engineering resources to solving just those two problems, guaranteeing a massive ROI.

---

## Conclusion: Start Small, But Start Now

You do not need to map every failure mode for every bolt in your facility today. That is a recipe for paralysis.

**How to get started:**

1.  **Pick your Critical Assets:** Identify the top 10% of assets that cause the most pain.
2.  **Define the Top 10 Modes:** For those assets, list the 10 most common things that go wrong.
3.  **Update the CMMS:** Load those codes and train the team.
4.  **Review Monthly:** Look at the data. Are technicians using the codes? Are patterns emerging?

Standardizing your failure modes and causes is not just a data entry exercise; it is the foundation of a reliability culture. It transforms your maintenance team from "fixers" into "improvers."