# CRIP Agent Specifications

## Agent 1: Data Governance Agent

### Purpose

Validate and clean uploaded portfolio data.

### Inputs

Entire dataset

### Key Functions

* Missing value checks
* Duplicate checks
* Data type validation
* Category validation
* Risk score validation
* Outlier detection
* Data quality scoring

### Outputs

* Clean Dataset
* Data Quality Score
* Validation Report
* Anomaly Summary
* Fraud Summary

---

## Agent 2: Pricing & Profitability Agent

### Inputs

* Written_Premium
* Claim_Amount
* Total_Expense
* Claim_Count
* Product_Type
* Customer_Segment
* Distribution_Channel
* Region
* Policy_Status
* Sum_Insured

### Calculations

* Loss Ratio
* Expense Ratio
* Combined Ratio
* Underwriting Profit
* Claim Severity
* Premium Adequacy

### Outputs

* Product Profitability Ranking
* Loss Ratio Analysis
* Combined Ratio Analysis
* Underwriting Profit Analysis
* Pricing Insights

---

## Agent 3: Risk Intelligence Agent

### Inputs

* Insurance_Risk
* Market_Risk
* Credit_Risk
* Operational_Risk
* Catastrophe_Risk
* Claim_Count
* Claim_Amount
* Fraud_Flag
* Product_Type
* Policy_Status
* Region
* Customer_Segment
* Sum_Insured
* Policy_Tenure_Months
* Renewal_Count

### Calculations

* Composite Risk Score
* Risk Category
* Exposure At Risk
* Risk Concentration
* Fraud Rate
* High-Risk Policy Count

### Outputs

* Composite Risk Score
* Risk Heatmap
* Risk Ranking
* Exposure Analysis
* Fraud Analysis
* Risk Category Distribution

---

## Agent 4: Time Series Intelligence Agent

### Inputs

* Date
* Written_Premium
* Claim_Amount
* Claim_Count
* Product_Type
* Season_Flag
* Anomaly_Flag

### Calculations

* Monthly Aggregation
* Claim Frequency
* Claim Severity
* Claims Forecast
* Premium Forecast
* Year-over-Year Growth
* Seasonal Trend Analysis

### Outputs

* Claims Forecast Chart
* Premium Forecast Chart
* Trend Analysis
* Seasonal Analysis
* Forecast Summary

---

## Agent 5: Stress Testing Agent

### Inputs

* Claim_Amount
* Written_Premium
* Total_Expense
* Capital_Reserve
* Insurance_Risk
* Market_Risk
* Credit_Risk
* Operational_Risk
* Catastrophe_Risk
* Product_Type
* Region

### Scenarios

#### Scenario 1

Claims +20%

#### Scenario 2

Claims +40%

#### Scenario 3

Market Risk +25%

#### Scenario 4

Combined Shock

Claims +40%
+
Market Risk +25%

#### Scenario 5

Catastrophic Event

Flood / Cyclone / Earthquake Scenario

### Outputs

* Scenario Results
* Capital Impact
* Solvency Analysis
* Capital Shortfall
* Product Vulnerability Analysis

---

## Agent 6: Executive Reporting Agent

### Inputs

* Data Governance Results
* Pricing Results
* Risk Results
* Forecasting Results
* Stress Testing Results

### Functions

* KPI Consolidation
* Portfolio Summary
* Growth Analysis
* Renewal Analysis
* Risk Commentary
* Recommendation Generation

### Gemini Tasks

* Executive Summary
* Risk Narrative
* Strategic Recommendations

### Outputs

* Executive Summary
* KPI Dashboard
* Risk Report
* Management Recommendations
* Downloadable PDF Report

---

# Workflow

Upload Dataset

↓

Data Governance Agent (Mandatory)

↓

Select Analysis Mode

↓

Pricing Agent

↓

Risk Agent

↓

Time Series Agent

↓

Stress Testing Agent

↓

Executive Reporting Agent

↓

Dashboard & PDF Report
