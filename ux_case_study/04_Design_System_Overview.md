# GrowthLens Mini Design System

## Overview
This design system provides the foundational building blocks for the GrowthLens redesign. The focus is on clarity, data density management, and accessible data visualization.

## 1. Typography
* Define Type Scale (e.g., Inter or Roboto).
* **Display:** For headline metrics.
* **Body:** For standard text, axis labels, legends.
* **Monospace:** For data tables and numerical alignments.

## 2. Color Palette
* **Brand/Primary:** ...
* **Background/Surfaces:** ...
* **Text/Iconography:** ...
* **Data Visualization (Categorical):** 5-7 distinct colors (checked for colorblindness).
* **Data Visualization (Sequential/Diverging):** For heatmaps (e.g., Cohort retention).
* **Status:** Success (Green), Warning (Yellow/Orange), Error (Red), Neutral/Insufficient Data (Gray).

## 3. Core Components
* **Filter Bar:** Standardized placement (top or left rail) across all modules.
* **Data Table:** Row heights (Dense/Compact), pagination, sorting indicators.
* **Chart Containers:** Standardized title, subtitle, legend placement, and export/overflow menus.
* **Confidence Interval Bars:** Specifically for A/B testing to show effect size and uncertainty.

## 4. State Patterns
* **Loading:** Skeleton screens for charts and tables.
* **Empty:** Clear illustrations and calls to action (e.g., "Adjust filters").
* **Error:** Non-destructive error messages with retry options.
* **Low Sample Size / Uncertainty:** Specific warnings applied to A/B tests or small cohorts to prevent misinterpretation.

## 5. Accessibility Guidelines
* All text must meet WCAG AA contrast ratios.
* No meaning conveyed by color alone (use patterns, text labels, or icons).
