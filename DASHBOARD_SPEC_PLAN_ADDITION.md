# Plan addition: Explainability and in-context help

**Merge this into the dashboard documentation overhaul plan when executing.**

---

## Requirement: Users can always get information on what any element means

The spec must state that the dashboard (and any rebuild) should let users understand **every** important element in place — without leaving the page or opening external docs. The documentation should both **require** this behavior and **provide** the content (or a clear list of what needs to be explained) so the colleague can implement it and an AI can generate copy.

### What must be explainable

1. **Dimensions**
   - Each of the **5 super-dimensions** and **15 sub-dimensions** should have a short, accessible description (what the dimension measures, what high/low means). Users should be able to see this from the chart (e.g. hover on a bar or axis label, or click a dimension name to open a tooltip/panel). The spec should list the dimension names and either include suggested description text or point to a single source (e.g. “Dimension descriptions” subsection) so the rebuild can ship the same meanings.

2. **Charts**
   - Every chart type should have an “Explain this chart” (or equivalent) affordance: a short sentence or two on what the chart shows, what the axes/slices/rows represent, and how to read it (e.g. “Each row is a division; the dot is the mean, the bar is the 95% credibility interval; the vertical line is the organization average”). The spec should include a **one-paragraph “Explain this chart”** (or bullet list) for each chart type so the rebuild can use it as tooltip, expander, or help panel.

3. **Terms and metrics**
   - **Credibility interval (CrI):** Explain in plain language (e.g. “We are 95% confident the true value lies in this range; the range is computed from the data and our model.”). Where CrI appears (bars, forest plots, spiders), a hover or “?” next to “95% CrI” should offer this explanation.
   - **Prior / posterior** (in Statistical detail): Short explanation of “prior = belief before data; posterior = updated belief after data”; optional one line on “every data point improves the prediction.” These can live in the Statistical tab intro or in a tooltip next to the section title.
   - Other terms used in the UI (e.g. “super-dimension,” “drill-down,” “profile”) should be defined in the **Glossary** in the spec; the rebuild can expose the same definitions in a sidebar panel, “?” icons, or tooltips.

### Where the spec documents this

- **In the spec document itself:** Add a section **“Explainability and in-context help”** (or “Helping users understand every element”) that:
  - States the principle: “Users should always be able to get an explanation of what any element means — dimensions, charts, and key terms.”
  - Lists what must be explainable (dimensions, each chart type, CrI, prior/posterior, and any other terms).
  - For each, provides **canonical explanation text** (or a pointer to the Glossary / dimension list) so the rebuild has copy-ready content. For example:
    - **Credibility interval:** “The 95% credibility interval (CrI) is the range in which we are 95% confident the true score lies, given the data and our model. A narrower interval means more precise estimates.”
    - **Horizontal bar chart (scores):** “This chart shows the culture profile: one bar per dimension (5 super-dimensions on top, 15 sub-dimensions below). The length is the score (0–100). Optional error bars show the 95% CrI.”
    - (Similarly for spider, forest plot, sunburst, prior/posterior.)
  - Suggests **UI patterns** without prescribing tech: e.g. tooltips on hover, “?” icons that open a short explanation, an expandable “Dimension guide” in the sidebar, and “Explain this chart” link or icon near each chart. The current app’s “Dimension guide” expander and hover descriptions on bars are examples.

- **In the Chart types reference:** For each chart type, add a **“How to explain it”** or **“Suggested explanation (for UI)”** line: one or two sentences the app can show when the user asks “what is this chart?” or hovers on a help icon.

- **In the Glossary:** Ensure every term that appears in the UI (Credibility interval, prior, posterior, super-dimension, sub-dimension, drill-down, profile, etc.) has a one- or two-sentence definition so the rebuild can reuse them in tooltips or a help panel.

### Outcome

After implementation, the spec will:
1. Require that the dashboard offers in-context help for dimensions, charts, and key terms.
2. Provide the actual explanation text (or a single source for it) so the colleague and AI can implement “explain this element” without inventing copy.
3. List UI patterns (tooltips, “?” icons, expanders, sidebar guide) as suggestions so the rebuild can choose how to surface the explanations.
