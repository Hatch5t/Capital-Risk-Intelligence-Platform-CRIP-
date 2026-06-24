# CRIP: Capital Risk Intelligence Pipeline

CRIP is a modular, AI-driven pipeline for evaluating, validating, and analyzing insurance datasets. It employs multiple specialized agents to automate the end-to-end process from data cleaning to advanced risk modeling and regulatory reporting.

## Overview

The pipeline consists of the following key components:

### 1. Data Validation Agent
- Identifies and cleans noisy or redundant data.
- Standardizes missing values.
- Detects outliers and anomalies.

### 2. Pricing & Profitability Agent
- Calculates fundamental insurance metrics: Loss Ratio, Expense Ratio, Combined Ratio, and Underwriting Profit.
- Segments profitability across different dimensions (Product Types, Customer Segments).
- Provides automated pricing insights.

### 3. Risk Intelligence & ML Agent
- Evaluates multi-dimensional risk profiles (Insurance, Credit, Market, Operational, and CAT risk).
- Trains an XGBoost Regressor to predict expected claim amounts.
- Runs Monte Carlo Simulations for portfolio stress testing and Value at Risk (VaR) calculations.

### 4. Data Governance Agent
- Generates comprehensive automated reports for regulatory compliance.
- Assures data integrity and validation reporting.

### 5. Chief Risk Officer Assistant (Chatbot)
- Integrated Executive Assistant chatbot to interactively query and analyze all generated reports.
- Answers questions dynamically based on the exact results from the other models (VaR, forecasting, anomalies).

### 6. Orchestrator
- A unified Streamlit dashboard (`orchestrator.py`) that integrates all the agents into a cohesive user interface.
- Provides interactive data exploration, fraud risk scoring, and report generation.

## Setup & Installation

1. Clone the repository or navigate to the project directory.
2. Create a `.env` file in the root directory and add your API keys (required for the Chatbot):
   ```bash
   OPENAI_API_KEY=your_key_here
   ```
3. Ensure you have the required dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the orchestrator dashboard:
   ```bash
   streamlit run orchestrator.py
   ```

## Repository Structure

- `orchestrator.py`: Main Streamlit application.
- `agents/`: Directory containing individual agent scripts (`data_governance.py`, `pricing.py`, `risk_intelligence.py`, etc.).
- `*.ipynb`: Jupyter notebooks (`data_validation_agent.ipynb`, `pricing_agent.ipynb`, `risk_intelligence_agent.ipynb`) for interactive analysis.
- `Dataset/`: Directory for input datasets.
- `reports/`: Directory containing generated validation and governance reports.

## Tech Stack

- Streamlit
- OpenAI API (GPT-4o)
- Pandas & Numpy
- Prophet (Time Series Forecasting)
- XGBoost & Scikit-learn (Machine Learning)
- Plotly (Interactive Data Visualizations)

## Contributers:
- Aarush Rajan Ranjan
- Deekshikha
- Saumya Bajaj
- Varad Srivastava

## Note: The project is made under the guidance of Sri Sai Sathya Institute of Actuaries (SSSIA) as a part of project in AI AIP Multi Industry Internship.


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

