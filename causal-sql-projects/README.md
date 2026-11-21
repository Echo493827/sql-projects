# Causal inference + HR SQL: two learning projects

Two connected projects for building the skills a people research role tests: **estimating the effect of a program from observational data**, and **SQL on HR data**. They end in one capstone that uses both.

```
causal-sql-projects/
├── lalonde-causal/                          project 1: causal inference on a classic dataset
│   ├── 01_experiment_benchmark.ipynb        potential outcomes, ATE vs ATT, the "right answer"
│   ├── 02_naive_comparison_and_balance.ipynb selection bias, standardized mean differences
│   ├── 03_regression_and_propensity_scores.ipynb  regression, propensity scores, overlap, matching, IPW
│   ├── 04_robustness_and_writeup.ipynb      doubly robust, bootstrap, sensitivity, placebo test, write-up
│   ├── utils.py
│   └── data/                                NSW experiment + CPS comparison group
└── hr-sql/                                  project 2: SQL on a fictional company's HRIS
    ├── 01_sql_workbook.ipynb                18 auto-checked exercises, 6 levels
    ├── 02_mentoring_effect.ipynb            capstone: did mentoring reduce attrition? (known true answer)
    ├── generate_hr_data.py                  simulates the company (rerun anytime; same seed = same data)
    ├── sqlkit.py                            connect / run / check / hint / solution
    ├── schema.md                            data dictionary
    └── data/                                8 CSV tables + _answer_key.json (don't peek)
```

## Suggested order
1. `lalonde-causal/01` → `04`. Read the math cells properly; answer the "predict first" prompts before running cells.
2. `hr-sql/01_sql_workbook.ipynb`. Try each exercise before using a hint.
3. `hr-sql/02_mentoring_effect.ipynb`. Swap in your own capstone query (6.1) at the top.

Every notebook runs top to bottom and is saved with its outputs, so you can read results before running anything.

## Setup

**Windows / local (recommended):**
```
cd causal-sql-projects
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
jupyter lab
```

**Google Colab:** upload the zip, then in a cell:
```
!unzip -q causal-sql-projects.zip
%cd causal-sql-projects/lalonde-causal
%pip install -q duckdb causaldata
```
(`cd` into `hr-sql` for the SQL notebooks.)

## What each project covers, and where it shows up in a job posting

| Skill | Where you practice it |
|---|---|
| Causal inference on observational data | LaLonde 02–04; mentoring capstone |
| Statistical inference and regression | LaLonde 01, 03; bootstrap in 04 |
| SQL to access structured data | SQL workbook levels 1–6 |
| Combining disparate sources (HR, pay, reviews, surveys) | SQL capstone 6.1 joins six tables |
| Explaining methods to leaders | write-up in LaLonde 04 and the capstone |
| Knowing when an analysis is wrong | placebo test, bad-control demo, balance checks |

## Putting it on GitHub
Worth doing **after** you've worked through it and can explain every step without notes. Make it yours:
- Write your own top-level README with your findings and what surprised you.
- Do the "Your turn" extensions; those are where your own work shows.
- Keep the attribution: the NSW/CPS data comes from LaLonde (1986) and Dehejia & Wahba (1999), via the `causaldata` package. The HR data is simulated.

## References
- LaLonde, R. (1986). Evaluating the econometric evaluations of training programs with experimental data. *American Economic Review.*
- Dehejia, R. & Wahba, S. (1999). Causal effects in nonexperimental studies. *JASA.*
- Rosenbaum, P. & Rubin, D. (1983). The central role of the propensity score in observational studies. *Biometrika.*
- Abadie, A. & Imbens, G. (2008). On the failure of the bootstrap for matching estimators. *Econometrica.*
- Austin, P. (2011). Optimal caliper widths for propensity-score matching. *Pharmaceutical Statistics.*
- Free books that go deeper: Cunningham, *Causal Inference: The Mixtape*; Huntington-Klein, *The Effect*.
