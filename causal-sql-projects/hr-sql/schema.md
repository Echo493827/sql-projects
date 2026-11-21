# Kestrel Media Co. · HR data dictionary

Fictional company, simulated data. Data pulled **2026-06-30**. Every termination in the data is on or before that date.

The first question to ask about any table is its **grain**: what does one row mean?

| table | grain (one row = …) | rows (approx.) |
|---|---|---|
| `employees` | one employee (static facts at hire) | 6,200 |
| `job_history` | one job change: hire, promotion, or transfer (effective-dated) | 8,000 |
| `compensation` | one pay change: hire, merit, or promotion (effective-dated) | 17,000 |
| `salary_bands` | one department × job level | 42 |
| `performance_reviews` | one employee × review year | 12,500 |
| `engagement_survey` | one survey response (quarterly pulse) | 30,000 |
| `mentoring_enrollments` | one enrolled employee | 1,150 |
| `terminations` | one terminated employee (no rehires) | 2,900 |

## employees
| column | type | notes |
|---|---|---|
| employee_id | int | primary key |
| hire_date | date | 2014-01 to 2026-06 |
| gender | text | Woman, Man, Nonbinary |
| location | text | Los Angeles, New York, Austin, Remote |
| hire_source | text | Referral, Recruiter, Job Board, University |
| prior_experience_years | int | years of experience before joining |

## job_history
| column | type | notes |
|---|---|---|
| employee_id | int | |
| effective_date | date | when the change took effect |
| department | text | Engineering, Content, Marketing, Product, Finance, Talent |
| job_level | int | 1 (entry) to 7 |
| manager_id | int | an employee_id; NULL if no manager on record |
| change_type | text | Hire, Promotion, Transfer |

Current job = the row with the latest `effective_date`. Department/level at hire = the `Hire` row.

## compensation
| column | type | notes |
|---|---|---|
| employee_id | int | |
| effective_date | date | |
| base_salary | int | annual, USD |
| change_reason | text | Hire, Merit (March), Promotion |

## salary_bands
| column | type | notes |
|---|---|---|
| department, job_level | | composite key |
| band_min, band_mid, band_max | int | comp ratio = salary / band_mid |

## performance_reviews
| column | type | notes |
|---|---|---|
| employee_id | int | |
| review_year | int | reviews happen in December |
| rating | int | 1 to 5; **NULL when the review wasn't completed** |
| review_status | text | Completed, Not completed |

## engagement_survey
| column | type | notes |
|---|---|---|
| employee_id | int | |
| survey_date | date | 15th of Mar, Jun, Sep, Dec, from 2022 |
| belonging, manager_support, growth, intent_to_stay | int | 1 to 5 Likert items |

Response is voluntary (around 70%). Only employees on payroll can respond.

## mentoring_enrollments
| column | type | notes |
|---|---|---|
| employee_id | int | |
| enroll_date | date | within 30 days of hire; program open to hires from 2023-01-01 |

Enrollment was **opt-in**, not random.

## terminations
| column | type | notes |
|---|---|---|
| employee_id | int | at most one row per employee |
| termination_date | date | last day |
| termination_type | text | Voluntary, Involuntary |
| reason | text | voluntary: Better Pay, Career Growth, Manager, Relocation, Personal, Workload/Schedule; involuntary: Performance, Conduct, Restructuring |

## Things that trip people up
- Joining `job_history`, `compensation`, `performance_reviews`, or `engagement_survey` straight to `employees` multiplies rows. Pick the row you need first (window functions).
- "Active" means no row in `terminations`.
- Point-in-time questions (headcount on a date) need `hire_date <= d AND (no termination OR termination_date > d)`.
- Missing ratings are NULL, not zero. Decide on purpose whether to keep them.
