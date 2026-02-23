# How to Combine Maintenance and Production Data for Integrated Reliability

**Keyword:** how to combine maintenance and production data

**Meta Title:** How to Combine Maintenance and Production Data (UNS Guide)

**Meta Description:** Combine maintenance and production data by mapping PLC/SCADA tags to CMMS records using a Unified Namespace (UNS) and MQTT Sparkplug B for real-time OEE.

**Word Count:** 1043

**Link Count:** 6

---

To combine maintenance and production data, you must establish a **Unified Namespace (UNS)** that serves as a centralized software layer where both Operational Technology (OT) data—such as PLC tags, SCADA outputs, and MES states—and Information Technology (IT) data—such as CMMS work orders and ERP schedules—are mapped to a common hierarchy. This is achieved by using a lightweight communication protocol like **MQTT with Sparkplug B** to "publish" data from machines and "subscribe" to it from maintenance management systems. Instead of rigid, point-to-point API integrations that break during software updates, a UNS allows production metrics (cycle counts, temperatures, vibration) to be automatically correlated with maintenance events (MTTR, spare parts consumption, and technician logs) in real-time.

This integration changes the fundamental nature of industrial data from "siloed records" to "contextualized events." For example, when a motor's amperage spikes (production data), the system immediately checks the last lubrication date and the current spare parts inventory for that specific asset (maintenance data). Without this combination, maintenance remains reactive, and production remains blind to the [engineering physics of peak production failures](/blog/the-engineering-physics-of-peak-production-failures-why-machines-break-when-you-need-them-most), where machines are pushed to breakdown during high-demand cycles.

### The Technical Architecture: Implementing a Unified Namespace (UNS)

Combining these data streams requires moving away from the "Purdue Model" of isolated layers and toward a hub-and-spoke architecture. Follow these four steps to execute the integration:

#### 1. Define the ISA-95 Hierarchy
Before connecting any cables, you must define a naming convention that both production and maintenance teams understand. The industry standard is the ISA-95 model: `Enterprise > Site > Area > Line > Cell`. 
*   **Production Data:** Might be tagged as `Site_A/Bottling_Line_1/Filler_3/Motor_Temp`.
*   **Maintenance Data:** Might be tagged as `Site_A/Bottling_Line_1/Filler_3/Work_Order_Status`.
By using the same path for both data types, the system automatically "knows" that a temperature spike and a work order belong to the same physical asset.

#### 2. Deploy an MQTT Broker with Sparkplug B
Traditional SCADA systems use "poll-response" protocols (like Modbus) which are inefficient for combining large datasets. MQTT (Message Queuing Telemetry Transport) is a "publish-subscribe" protocol that allows machines to report data only when it changes (Report by Exception). **Sparkplug B** is a specification that adds a standard data payload format, ensuring that when a PLC sends data, the CMMS or Analytics engine knows exactly what the units (e.g., Celsius vs. Fahrenheit) and data types are without manual mapping.

#### 3. Bridge the IT/OT Gap (CMMS to UNS)
Most modern CMMS platforms (like MaintainX or Upkeep) offer REST APIs. To combine this with production data, you need a middleware or "Industrial IoT Gateway" (such as [Inductive Automation’s Ignition](https://inductiveautomation.com/ignition/) or HiveMQ) that pulls work order data from the CMMS API and publishes it into the UNS. 
*   **If the machine stops (OT data):** The UNS sees a "State = Down" message.
*   **If a technician starts a repair (IT data):** The UNS sees a "Work Order = In Progress" message.
The combination of these two data points allows for the calculation of true **OEE (Overall Equipment Effectiveness)**, specifically the "Availability" loss due to unplanned maintenance.

#### 4. Contextualization and Visualization
Once the data is flowing into the UNS, use a Business Intelligence (BI) tool or a specialized reliability platform to create dashboards. The goal is to move beyond simple charts. You want to see "Maintenance Cost per Unit Produced" or "Mean Time Between Failures (MTBF) vs. Production Speed." This prevents the common issue where [technicians don’t trust maintenance data](/blog/why-technicians-dont-trust-maintenance-data-diagnosing-the-systemic-trust-failure) because they can see the data reflects the actual reality of the shop floor.

### What to Do About It: Moving Toward Predictive Reliability

Combining data is not the end goal; the goal is to eliminate the "reactive death spiral." Once your production and maintenance data are unified, you can transition from calendar-based schedules to **Condition-Based Maintenance (CBM)**.

1.  **Identify High-Impact Assets:** Start with "brownfield" equipment—older machines that cause the most downtime. These often lack modern sensors but are critical to throughput.
2.  **Automate Triggered Work Orders:** Set thresholds in your UNS. If a conveyor's vibration exceeds 0.5 in/s (production/sensor data), the system should automatically generate a "Check Bearings" work order in the CMMS (maintenance data). This closes the loop between seeing a problem and fixing it.
3.  **Deploy Factory AI for Rapid Scaling:** Building a full UNS from scratch can take 12-18 months. **Factory AI** provides a shortcut. It is sensor-agnostic and no-code, meaning it can ingest raw PLC data and CMMS logs simultaneously. It is specifically designed for brownfield environments and can be deployed in as little as 14 days, providing the "Unified Namespace" benefits without the heavy infrastructure lift. This is particularly useful when [vibration checks don’t prevent failures](/blog/why-vibration-checks-dont-prevent-failures-the-gap-between-data-and-reliability) because the data isn't being analyzed in the context of production loads.

### Related Questions

**What is the difference between IT and OT data in manufacturing?**
OT (Operational Technology) data comes from the physical equipment, such as sensors, PLCs, and motors, focusing on real-time performance and control. IT (Information Technology) data comes from business systems like CMMS, ERP, and HR, focusing on work orders, costs, and scheduling. Combining them allows you to see how physical machine behavior impacts business profitability.

**How does combining maintenance and production data improve OEE?**
OEE is calculated using Availability, Performance, and Quality. Without maintenance data, you know a machine is "down" (Availability loss), but you don't know *why*. By integrating CMMS data, you can categorize downtime by root cause (e.g., waiting for parts vs. actual repair time), allowing for targeted improvements that [eliminate chronic machine failures](/blog/how-to-eliminate-chronic-machine-failures-and-repeated-downtime).

**Can I integrate data from "brownfield" (legacy) equipment?**
Yes. You can use IIoT gateways or edge devices to "wrap" legacy protocols (like Modbus or serial) into MQTT. This allows 30-year-old machines to communicate with modern cloud-based CMMS platforms. Tools like Factory AI are specifically built to bridge this gap, allowing legacy data to be contextualized alongside modern production metrics without replacing the entire control system.

**What are the risks of not combining these data streams?**
The primary risk is "data blindness," where the maintenance team performs preventive tasks on machines that don't need them, while ignoring machines that are under high production stress. This leads to the "Maintenance Paradox," where [motors run hot after service](/blog/the-maintenance-paradox-why-motors-run-hot-after-service) or machines fail immediately following a cleaning shift because the maintenance schedule was disconnected from the production reality.