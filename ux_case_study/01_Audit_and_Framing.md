# Phase 1: Audit & Framing

## 1. Problem Statement
GrowthLens is a working Streamlit analytics dashboard (Olist dataset, ~99K orders) with seven modules. While it proves analytical skill, it says nothing about design judgment. Product design hiring managers in enterprise data companies look for evidence of how a candidate turns dense, multi-dimensional data into clear hierarchy, handles statistical uncertainty honestly, and builds reusable systems. 

This project converts GrowthLens into a Figma-based redesign case study plus a mini design system, demonstrating process, decisions, and validation, not just output.

**Cost of not doing it:** The portfolio stays "data projects with default Streamlit UI," which reads as analyst work, not product design.

## 2. Personas (Hypotheses)

| Persona | Context | Core Question |
| --- | --- | --- |
| **Growth Analyst** | Works in the dashboard daily | "Which cohort or funnel stage is underperforming, and why?" |
| **Category/Product Manager** | Reviews weekly | "Did the test work, and can I trust the result?" |
| **Executive Viewer** | Glances occasionally | "Are we healthy? What needs my attention?" |

*Note: These are assumptions to be validated or changed during Phase 4 Usability Testing.*

## 3. Task List (For Usability Testing & Audit)

These tasks are designed to evaluate the current UI and the future prototype:
1. **Find the weakest cohort:** "Using the Cohort module, identify which acquisition month had the lowest retention at month 3."
2. **Diagnose funnel drop-off:** "Using the Funnel module, identify the stage with the highest drop-off rate. Can you drill down to see what segment caused it?"
3. **Evaluate A/B test results:** "Using the A/B Testing module, determine if the latest test was a 'win'. Is there enough sample size, and what is the confidence interval?"

## 4. Current-State Audit
*Audit conducted on the live Streamlit dashboard across the three primary analytical workflows: Cohort Retention, Funnel Analysis, and A/B Testing Engine.*

### Module 1: Cohort Analysis
![Cohort Retention Module](./screenshots/cohort_analysis.png)

- **Usability & Hierarchy Issues:**
  - *Data Trust & Formatting Anomalies:* Week 0 retention displays erroneous values above 100% (e.g., 101%, 102%) due to unrounded floating-point calculations, and cell text glyphs visually clash with heatmap cell boundaries. In enterprise analytics, displaying >100% retention immediately destroys executive trust in the platform.
  - *Disconnected Sample Sizes:* The retention heatmap displays percentages in isolation without adjacent cohort sizes (N). Analysts cannot evaluate whether a 30% retention rate represents 30 users or 3,000 users without scrolling down past the retention curve to inspect a disconnected secondary table.
  - *Sparse Y-Axis Grid & Label Skipping:* The heatmap y-axis skips alternate cohort months (only labeling Jan, Mar, May, Jul, Sep), forcing users to mentally interpolate intermediate rows (Feb, Apr, Jun, Aug).
  - *Lack of Multidimensional Drilldown:* The module provides zero segmentation filters (acquisition channel, customer tier, product category, or geo-location), preventing growth analysts from discovering *why* a particular cohort retained poorly.

---

### Module 3: Funnel Analysis
![Funnel Analysis Module](./screenshots/funnel_analysis.png)

- **Usability & Hierarchy Issues:**
  - *Disjointed Filtering Architecture:* The "Device" filter sits isolated in an awkward position above the KPI metric cards rather than integrated into a unified filter bar, and lacks date range selectors, UTM source segmentation, or user-type filters.
  - *Information Disconnect in Funnel Graphic:* The funnel visualization displays absolute volume and relative percentage from previous stage inside bars, but completely omits drop-off numbers and drop percentages directly on the transition bridges. Users are forced to cross-reference the graphic with the "Step-by-step breakdown" table below to find where customers were lost.
  - *No Stage-Level Diagnostic Drilldown:* Clicking on high-leakage steps (such as the 48% drop from Visit to PDP View, or the 38% drop from Cart to Checkout) does not reveal root causes, friction indicators, or demographic skews.
  - *Vertical Real Estate Inefficiency:* The funnel graphic dominates vertical screen height, pushing critical conversion breakdown channels ("Purchase CVR by channel") entirely below the initial fold.

---

### Module 4: A/B Testing Engine
#### Tab 1: Sample Size Calculator
![A/B Testing - Sample Size Calculator](./screenshots/ab_testing_calculator.png)

#### Tab 2: Results Analyser
![A/B Testing - Results Analyser](./screenshots/ab_testing_results.png)

- **Usability & Hierarchy Issues:**
  - *Siloed Pre-Test and Post-Test Workflows:* Sample size calculation (planning) and results evaluation (analysis) are split into disconnected tabs with zero state persistence. An analyst who plans a test must manually re-enter numbers rather than linking planned experiment parameters with incoming test results.
  - *Confirmation Bias Trap (Missing Visual Confidence Intervals):* The results dashboard highlights headline metrics like **+19.0% Uplift** in prominent bold type, despite a non-significant p-value of 0.0911 at α=0.05. Without visual confidence interval error bars illustrating overlap with zero, non-statistical stakeholders are likely to declare victory prematurely.
  - *Low-Utility Statistical Visualization:* The z-distribution bell curve is mathematically theoretical but practically unhelpful for product managers. It fails to convey decision risk, runtime progression, or how many additional days of testing are required to reach statistical clarity.
  - *Binary, Un-actionable Verdicts:* The alert box offers a rigid binary statement ("Inconclusive... run the test longer") without calculating the remaining sample deficit or estimating time-to-conclusion based on current daily velocity.
