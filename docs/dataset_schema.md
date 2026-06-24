# CRIP Dataset Schema

## Dataset Overview

General Insurance Portfolio Dataset

Products Covered:

* Motor Insurance
* Health Insurance
* Property Insurance
* Travel Insurance
* Fire Insurance
* Marine Insurance

Historical Period:

* January 2022 to December 2024
* Monthly Records

---

## Identity

| Field     | Type   | Description              |
| --------- | ------ | ------------------------ |
| Policy_ID | String | Unique policy identifier |
| Date      | Date   | Monthly observation date |

---

## Portfolio Information

| Field                | Type     | Description                                   |
| -------------------- | -------- | --------------------------------------------- |
| Product_Type         | Category | Motor, Health, Property, Travel, Fire, Marine |
| Region               | Category | North, South, East, West, Central             |
| Policy_Status        | Category | Active, Lapsed, Renewed, Cancelled            |
| Customer_Segment     | Category | Individual, SME, Corporate                    |
| Distribution_Channel | Category | Agent, Bancassurance, Direct, Online          |

---

## Premium & Exposure

| Field                | Type    | Description                 |
| -------------------- | ------- | --------------------------- |
| Written_Premium      | Float   | Premium collected (₹)       |
| Sum_Insured          | Float   | Maximum coverage amount (₹) |
| Policy_Tenure_Months | Integer | Policy duration in months   |
| Renewal_Count        | Integer | Number of renewals          |

---

## Claims

| Field         | Type    | Description                                 |
| ------------- | ------- | ------------------------------------------- |
| Claim_Count   | Integer | Number of claims                            |
| Claim_Amount  | Float   | Total claims paid (₹)                       |
| Total_Expense | Float   | Acquisition and administration expenses (₹) |

---

## Risk Indicators

| Field            | Type    | Description                           |
| ---------------- | ------- | ------------------------------------- |
| Insurance_Risk   | Integer | Underwriting and claims risk (1-10)   |
| Market_Risk      | Integer | Investment and economic risk (1-10)   |
| Credit_Risk      | Integer | Counterparty default risk (1-10)      |
| Operational_Risk | Integer | Process and operational risk (1-10)   |
| Catastrophe_Risk | Integer | Natural disaster exposure risk (1-10) |

---

## Flags

| Field           | Type     | Description                    |
| --------------- | -------- | ------------------------------ |
| Fraud_Flag      | Integer  | 1 = Fraud Suspected, 0 = Clean |
| Anomaly_Flag    | Integer  | 1 = Unusual Record, 0 = Normal |
| Season_Flag     | Category | Summer, Monsoon, Winter        |
| Capital_Reserve | Float    | Available capital reserve (₹)  |

---

## Derived Metrics (Not Stored)

These values are calculated by agents during execution.

* Loss Ratio
* Expense Ratio
* Combined Ratio
* Underwriting Profit
* Claim Frequency
* Claim Severity
* Composite Risk Score
* Risk Category
* Exposure At Risk
* Renewal Rate
* Solvency Ratio
* Capital Impact
* Capital Shortfall
