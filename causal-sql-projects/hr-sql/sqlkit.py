"""Helpers for the HR SQL workbook: load the data into DuckDB, run queries, check answers.

    from sqlkit import connect, run, check, question, hint, solution
"""
import os
import textwrap

import duckdb
import pandas as pd

here = os.path.dirname(os.path.abspath(__file__))
dataDir = os.path.join(here, "data")
tables = ["employees", "job_history", "compensation", "salary_bands", "performance_reviews",
          "engagement_survey", "mentoring_enrollments", "terminations"]
_con = None


def connect():
    """create an in-memory duckdb database with one table per csv"""
    global _con
    if not os.path.exists(os.path.join(dataDir, "employees.csv")):
        raise FileNotFoundError("no data yet: run `python generate_hr_data.py` in the hr-sql folder first")
    _con = duckdb.connect()
    for t in tables:
        path = os.path.join(dataDir, f"{t}.csv").replace("\\", "/")
        _con.execute(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM read_csv_auto('{path}', header=true)")
    return _con


def run(query):
    """run a query and return a pandas dataframe"""
    if _con is None:
        connect()
    return _con.execute(query).df()


# ---------------------------------------------------------------------------
# exercises: id -> (title, question, hints, solution)
# all "as of" questions use the data pull date 2026-06-30
# ---------------------------------------------------------------------------
EX = {}


def ex(id_, title, question_, hints, sol):
    EX[id_] = dict(title=title, question=textwrap.dedent(question_).strip(), hints=hints,
                   solution=textwrap.dedent(sol).strip())


# ---------- level 1: warm-up ----------
ex("1.1", "Hires per year",
   """Count hires by calendar year.
   Columns: hire_year, hires""",
   ["year(hire_date) pulls the year out of a date.", "GROUP BY the year."],
   """
   SELECT year(hire_date) AS hire_year, count(*) AS hires
   FROM employees
   GROUP BY 1
   ORDER BY 1;
   """)

ex("1.2", "Exits by year and type",
   """Count terminations by year of termination and termination_type (Voluntary / Involuntary).
   Columns: term_year, termination_type, exits""",
   ["Group by two columns."],
   """
   SELECT year(termination_date) AS term_year, termination_type, count(*) AS exits
   FROM terminations
   GROUP BY 1, 2
   ORDER BY 1, 2;
   """)

ex("1.3", "Experience by hire source",
   """Average prior_experience_years for each hire_source, rounded to 1 decimal.
   Columns: hire_source, avg_prior_experience""",
   ["round(avg(x), 1)"],
   """
   SELECT hire_source, round(avg(prior_experience_years), 1) AS avg_prior_experience
   FROM employees
   GROUP BY 1
   ORDER BY 2 DESC;
   """)

# ---------- level 2: joins ----------
ex("2.1", "Active headcount by location",
   """How many employees are active as of 2026-06-30, by location?
   Active = no row in terminations (every termination in the data is on or before 2026-06-30).
   Columns: location, active_headcount""",
   ["LEFT JOIN terminations, then keep rows where the termination side is NULL.",
    "This is the 'anti-join' pattern. NOT EXISTS works too."],
   """
   SELECT e.location, count(*) AS active_headcount
   FROM employees e
   LEFT JOIN terminations t ON t.employee_id = e.employee_id
   WHERE t.employee_id IS NULL
   GROUP BY 1
   ORDER BY 2 DESC;
   """)

ex("2.2", "Early voluntary exits by hire source",
   """For people hired 2020-01-01 through 2025-06-30, what share left VOLUNTARILY within 365 days of hire?
   Early voluntary exit = termination_type 'Voluntary' and termination_date < hire_date + 365 days.
   Columns: hire_source, hires, early_vol_exits, rate_pct (percent, 1 decimal)""",
   ["Keep every hire (LEFT JOIN) so people who stayed count in the denominator.",
    "Conditional count: sum(CASE WHEN ... THEN 1 ELSE 0 END) works in every SQL dialect.",
    "date_diff('day', hire_date, termination_date) < 365"],
   """
   SELECT e.hire_source,
          count(*) AS hires,
          sum(CASE WHEN t.termination_type = 'Voluntary'
                    AND date_diff('day', e.hire_date, t.termination_date) < 365 THEN 1 ELSE 0 END)
              AS early_vol_exits,
          round(100.0 * sum(CASE WHEN t.termination_type = 'Voluntary'
                                  AND date_diff('day', e.hire_date, t.termination_date) < 365 THEN 1 ELSE 0 END)
                / count(*), 1) AS rate_pct
   FROM employees e
   LEFT JOIN terminations t ON t.employee_id = e.employee_id
   WHERE e.hire_date BETWEEN DATE '2020-01-01' AND DATE '2025-06-30'
   GROUP BY 1
   ORDER BY rate_pct DESC;
   """)

ex("2.3", "Survey response rate",
   """Response rate for the 2025-12-15 engagement pulse.
   Eligible = hired on or before 2025-11-15 AND not terminated on or before 2025-12-15.
   Responded = eligible and has a row in engagement_survey with survey_date = 2025-12-15.
   Columns: eligible, responded, response_rate_pct (1 decimal)""",
   ["Build the eligible list first (a CTE helps), then LEFT JOIN the survey rows for that date.",
    "Put the survey_date condition in the ON clause, not the WHERE clause. Why does that matter?"],
   """
   WITH eligible AS (
       SELECT e.employee_id
       FROM employees e
       LEFT JOIN terminations t ON t.employee_id = e.employee_id
       WHERE e.hire_date <= DATE '2025-11-15'
         AND (t.termination_date IS NULL OR t.termination_date > DATE '2025-12-15')
   )
   SELECT count(*) AS eligible,
          count(s.employee_id) AS responded,
          round(100.0 * count(s.employee_id) / count(*), 1) AS response_rate_pct
   FROM eligible el
   LEFT JOIN engagement_survey s
          ON s.employee_id = el.employee_id AND s.survey_date = DATE '2025-12-15';
   """)

# ---------- level 3: dates and headcount ----------
ex("3.1", "Month-end headcount, 2025",
   """Headcount on the last day of each month in 2025.
   On payroll on day X = hire_date <= X AND (no termination OR termination_date > X).
   Columns: month_end, headcount""",
   ["Make a list of the 12 month-end dates first: generate_series(DATE '2025-01-01', DATE '2025-12-01', "
    "INTERVAL 1 MONTH) gives month starts; last_day(d) gives the month end.",
    "Join employees to that list with the 'on payroll' condition, then count per month_end."],
   """
   WITH months AS (
       SELECT last_day(CAST(m AS DATE)) AS month_end
       FROM generate_series(DATE '2025-01-01', DATE '2025-12-01', INTERVAL 1 MONTH) g(m)
   )
   SELECT mo.month_end, count(e.employee_id) AS headcount
   FROM months mo
   JOIN employees e ON e.hire_date <= mo.month_end
   LEFT JOIN terminations t ON t.employee_id = e.employee_id
   WHERE t.termination_date IS NULL OR t.termination_date > mo.month_end
   GROUP BY 1
   ORDER BY 1;
   """)

ex("3.2", "2025 voluntary turnover rate",
   """Annual voluntary turnover for 2025 = voluntary exits in 2025 / average of the 12 month-end headcounts.
   Columns: vol_exits, avg_headcount (1 decimal), turnover_pct (1 decimal)""",
   ["Reuse your 3.1 query as a CTE.", "Two CTEs, one row each, then CROSS JOIN them."],
   """
   WITH months AS (
       SELECT last_day(CAST(m AS DATE)) AS month_end
       FROM generate_series(DATE '2025-01-01', DATE '2025-12-01', INTERVAL 1 MONTH) g(m)
   ),
   hc AS (
       SELECT mo.month_end, count(e.employee_id) AS headcount
       FROM months mo
       JOIN employees e ON e.hire_date <= mo.month_end
       LEFT JOIN terminations t ON t.employee_id = e.employee_id
       WHERE t.termination_date IS NULL OR t.termination_date > mo.month_end
       GROUP BY 1
   ),
   ex AS (
       SELECT count(*) AS vol_exits
       FROM terminations
       WHERE termination_type = 'Voluntary' AND year(termination_date) = 2025
   )
   SELECT ex.vol_exits,
          round(avg(hc.headcount), 1) AS avg_headcount,
          round(100.0 * ex.vol_exits / avg(hc.headcount), 1) AS turnover_pct
   FROM hc CROSS JOIN ex
   GROUP BY ex.vol_exits;
   """)

ex("3.3", "Tenure bands",
   """Active employees (as of 2026-06-30) by tenure band.
   Tenure in years = date_diff('day', hire_date, DATE '2026-06-30') / 365.25
   Bands: '<1 yr' (under 1), '1-2 yrs' (1 to under 2), '2-5 yrs' (2 to under 5), '5+ yrs'.
   Columns: tenure_band, headcount""",
   ["CASE WHEN ... THEN '<1 yr' WHEN ... END"],
   """
   WITH active AS (
       SELECT e.*, date_diff('day', e.hire_date, DATE '2026-06-30') / 365.25 AS tenure_yrs
       FROM employees e
       LEFT JOIN terminations t ON t.employee_id = e.employee_id
       WHERE t.employee_id IS NULL
   )
   SELECT CASE WHEN tenure_yrs < 1 THEN '<1 yr'
               WHEN tenure_yrs < 2 THEN '1-2 yrs'
               WHEN tenure_yrs < 5 THEN '2-5 yrs'
               ELSE '5+ yrs' END AS tenure_band,
          count(*) AS headcount
   FROM active
   GROUP BY 1
   ORDER BY 1;
   """)

# ---------- level 4: window functions ----------
ex("4.1", "Current department and level",
   """job_history has one row per job change. An employee's CURRENT job is their latest row (by effective_date).
   For active employees, count headcount by current department and current job_level.
   Columns: department, job_level, headcount""",
   ["row_number() OVER (PARTITION BY employee_id ORDER BY effective_date DESC) = 1 picks the latest row.",
    "DuckDB (and Snowflake, BigQuery) let you filter on a window function with QUALIFY. "
    "Elsewhere, wrap it in a subquery."],
   """
   WITH current_job AS (
       SELECT *
       FROM job_history
       QUALIFY row_number() OVER (PARTITION BY employee_id ORDER BY effective_date DESC) = 1
   )
   SELECT cj.department, cj.job_level, count(*) AS headcount
   FROM current_job cj
   LEFT JOIN terminations t ON t.employee_id = cj.employee_id
   WHERE t.employee_id IS NULL
   GROUP BY 1, 2
   ORDER BY 1, 2;
   """)

ex("4.2", "Promotions per year (using LAG)",
   """A promotion = a job_history row whose job_level is higher than that employee's previous row.
   Don't use change_type; the point is to practice LAG. Count promotions by year of effective_date.
   Columns: promo_year, promotions""",
   ["lag(job_level) OVER (PARTITION BY employee_id ORDER BY effective_date) gives the previous level.",
    "Compute the lag in a CTE, then filter where job_level > prev_level."],
   """
   WITH jh AS (
       SELECT *, lag(job_level) OVER (PARTITION BY employee_id ORDER BY effective_date) AS prev_level
       FROM job_history
   )
   SELECT year(effective_date) AS promo_year, count(*) AS promotions
   FROM jh
   WHERE job_level > prev_level
   GROUP BY 1
   ORDER BY 1;
   """)

ex("4.3", "Time to first promotion",
   """For employees who were ever promoted, months from hire to FIRST promotion.
   Report the median by department at hire (the department on their 'Hire' row).
   Months = date_diff('month', hire_date, first_promotion_date).
   Columns: department, promoted_employees, median_months""",
   ["One CTE for each employee's first promotion date (min effective_date where change_type = 'Promotion').",
    "Another for department at hire. Join them with employees."],
   """
   WITH first_promo AS (
       SELECT employee_id, min(effective_date) AS first_promo_date
       FROM job_history
       WHERE change_type = 'Promotion'
       GROUP BY 1
   ),
   at_hire AS (
       SELECT employee_id, department
       FROM job_history
       WHERE change_type = 'Hire'
   )
   SELECT h.department,
          count(*) AS promoted_employees,
          median(date_diff('month', e.hire_date, fp.first_promo_date)) AS median_months
   FROM first_promo fp
   JOIN employees e USING (employee_id)
   JOIN at_hire h USING (employee_id)
   GROUP BY 1
   ORDER BY 3;
   """)

ex("4.4", "Rolling 3-month voluntary exits, 2025",
   """Voluntary exits per month in 2025, plus a rolling average of the current and previous two months
   (for January use January alone; for February, Jan-Feb). Months with zero exits must still appear.
   Columns: month_start, vol_exits, rolling_3mo_avg (2 decimals)""",
   ["Generate the 12 months first so empty months exist, then LEFT JOIN exits.",
    "avg(x) OVER (ORDER BY month_start ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)"],
   """
   WITH months AS (
       SELECT CAST(m AS DATE) AS month_start
       FROM generate_series(DATE '2025-01-01', DATE '2025-12-01', INTERVAL 1 MONTH) g(m)
   ),
   monthly AS (
       SELECT mo.month_start, count(t.employee_id) AS vol_exits
       FROM months mo
       LEFT JOIN terminations t
              ON date_trunc('month', t.termination_date) = mo.month_start
             AND t.termination_type = 'Voluntary'
       GROUP BY 1
   )
   SELECT month_start, vol_exits,
          round(avg(vol_exits) OVER (ORDER BY month_start ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2)
              AS rolling_3mo_avg
   FROM monthly
   ORDER BY 1;
   """)

ex("4.5", "Latest rating for active employees",
   """For active employees with at least one review, take their most recent review (highest review_year).
   Count them by that review's rating (NULL rating = review not completed; keep those as their own group).
   Columns: latest_rating, employees""",
   ["QUALIFY row_number() ... = 1 again.", "GROUP BY keeps NULL as its own group."],
   """
   WITH latest AS (
       SELECT r.*
       FROM performance_reviews r
       LEFT JOIN terminations t ON t.employee_id = r.employee_id
       WHERE t.employee_id IS NULL
       QUALIFY row_number() OVER (PARTITION BY r.employee_id ORDER BY r.review_year DESC) = 1
   )
   SELECT rating AS latest_rating, count(*) AS employees
   FROM latest
   GROUP BY 1
   ORDER BY 1 NULLS LAST;
   """)

# ---------- level 5: cohorts and retention ----------
ex("5.1", "12-month retention by hire cohort",
   """For hire years 2020 through 2024, the share of hires still employed 365 days after hire.
   Left within a year = termination_date < hire_date + 365 days (any termination type).
   Columns: hire_year, hires, retained_12m, retention_pct (1 decimal)""",
   ["A hire is retained unless they have a termination within 365 days."],
   """
   SELECT year(e.hire_date) AS hire_year,
          count(*) AS hires,
          sum(CASE WHEN t.termination_date IS NULL
                     OR date_diff('day', e.hire_date, t.termination_date) >= 365 THEN 1 ELSE 0 END) AS retained_12m,
          round(100.0 * sum(CASE WHEN t.termination_date IS NULL
                                   OR date_diff('day', e.hire_date, t.termination_date) >= 365 THEN 1 ELSE 0 END)
                / count(*), 1) AS retention_pct
   FROM employees e
   LEFT JOIN terminations t USING (employee_id)
   WHERE year(e.hire_date) BETWEEN 2020 AND 2024
   GROUP BY 1
   ORDER BY 1;
   """)

ex("5.2", "Retention curve for the 2023 cohort",
   """For people hired in 2023: the percent still employed at 3, 6, 12, 18, and 24 months.
   Still employed at m months = no termination_date before hire_date + INTERVAL m MONTH.
   Columns: months, pct_retained (1 decimal)""",
   ["unnest([3, 6, 12, 18, 24]) AS months gives you the checkpoints; CROSS JOIN them to the cohort.",
    "hire_date + months * INTERVAL 1 MONTH adds a variable number of months."],
   """
   WITH cohort AS (
       SELECT e.employee_id, e.hire_date, t.termination_date
       FROM employees e
       LEFT JOIN terminations t USING (employee_id)
       WHERE year(e.hire_date) = 2023
   ),
   checkpoints AS (SELECT unnest([3, 6, 12, 18, 24]) AS months)
   SELECT c.months,
          round(100.0 * avg(CASE WHEN co.termination_date IS NULL
                                   OR co.termination_date >= co.hire_date + c.months * INTERVAL 1 MONTH
                                 THEN 1 ELSE 0 END), 1) AS pct_retained
   FROM checkpoints c CROSS JOIN cohort co
   GROUP BY 1
   ORDER BY 1;
   """)

ex("5.3", "First-year voluntary attrition by gender and location, with suppression",
   """Hires 2022-01-01 through 2025-06-30. For each gender x location group:
   hires, early voluntary exits (Voluntary, within 365 days), and rate_pct (1 decimal).
   Small-group rule: if a group has fewer than 30 hires, rate_pct must be NULL (suppressed).
   Columns: gender, location, hires, early_vol_exits, rate_pct""",
   ["CASE WHEN count(*) < 30 THEN NULL ELSE round(...) END",
    "Why suppress? Small groups give unstable rates and can point at individuals."],
   """
   SELECT e.gender, e.location,
          count(*) AS hires,
          sum(CASE WHEN t.termination_type = 'Voluntary'
                    AND date_diff('day', e.hire_date, t.termination_date) < 365 THEN 1 ELSE 0 END)
              AS early_vol_exits,
          CASE WHEN count(*) < 30 THEN NULL
               ELSE round(100.0 * sum(CASE WHEN t.termination_type = 'Voluntary'
                                            AND date_diff('day', e.hire_date, t.termination_date) < 365
                                           THEN 1 ELSE 0 END) / count(*), 1) END AS rate_pct
   FROM employees e
   LEFT JOIN terminations t USING (employee_id)
   WHERE e.hire_date BETWEEN DATE '2022-01-01' AND DATE '2025-06-30'
   GROUP BY 1, 2
   ORDER BY 1, 2;
   """)

# ---------- level 6: capstone ----------
ex("6.1", "Capstone: build the mentoring analysis table",
   """One row per employee hired 2023-01-01 through 2025-06-30 (everyone in this window has a full year of data).
   Columns, in this order:
     employee_id
     mentored                 1 if in mentoring_enrollments, else 0
     hire_source, location, gender, prior_experience_years
     department_at_hire       from their 'Hire' row in job_history
     level_at_hire            from their 'Hire' row in job_history
     comp_ratio_at_hire       hire salary ('Hire' row in compensation) / band_mid for that department and level,
                              rounded to 3 decimals
     left_within_12m          1 if any termination_date < hire_date + 365 days, else 0
     first_pulse_engagement   average of the four survey items on their FIRST survey response after hire
                              (NULL if they never responded), rounded to 2 decimals
   This is the table you'll use to estimate the mentoring program's effect.""",
   ["Build one CTE per source (hire job row, hire salary, first survey), then LEFT JOIN them all to the cohort.",
    "First survey: QUALIFY row_number() OVER (PARTITION BY employee_id ORDER BY survey_date) = 1.",
    "Check your row count: it should equal the number of hires in the window. A wrong join type changes it."],
   """
   WITH cohort AS (
       SELECT *
       FROM employees
       WHERE hire_date BETWEEN DATE '2023-01-01' AND DATE '2025-06-30'
   ),
   hire_job AS (
       SELECT employee_id, department AS department_at_hire, job_level AS level_at_hire
       FROM job_history
       WHERE change_type = 'Hire'
   ),
   hire_pay AS (
       SELECT employee_id, base_salary AS hire_salary
       FROM compensation
       WHERE change_reason = 'Hire'
   ),
   first_pulse AS (
       SELECT s.employee_id,
              (s.belonging + s.manager_support + s.growth + s.intent_to_stay) / 4.0 AS engagement
       FROM engagement_survey s
       JOIN cohort c ON c.employee_id = s.employee_id AND s.survey_date > c.hire_date
       QUALIFY row_number() OVER (PARTITION BY s.employee_id ORDER BY s.survey_date) = 1
   )
   SELECT c.employee_id,
          CASE WHEN m.employee_id IS NOT NULL THEN 1 ELSE 0 END AS mentored,
          c.hire_source, c.location, c.gender, c.prior_experience_years,
          hj.department_at_hire, hj.level_at_hire,
          round(hp.hire_salary / b.band_mid, 3) AS comp_ratio_at_hire,
          CASE WHEN t.termination_date < c.hire_date + INTERVAL 365 DAY THEN 1 ELSE 0 END AS left_within_12m,
          round(fp.engagement, 2) AS first_pulse_engagement
   FROM cohort c
   LEFT JOIN mentoring_enrollments m ON m.employee_id = c.employee_id
   LEFT JOIN hire_job hj ON hj.employee_id = c.employee_id
   LEFT JOIN hire_pay hp ON hp.employee_id = c.employee_id
   LEFT JOIN salary_bands b ON b.department = hj.department_at_hire AND b.job_level = hj.level_at_hire
   LEFT JOIN terminations t ON t.employee_id = c.employee_id
   LEFT JOIN first_pulse fp ON fp.employee_id = c.employee_id
   ORDER BY c.employee_id;
   """)


# ---------------------------------------------------------------------------
def question(id_):
    e = EX[id_]
    print(f"[{id_}] {e['title']}\n\n{e['question']}")


def hint(id_, k=None):
    hs = EX[id_]["hints"]
    for i, h in enumerate(hs if k is None else [hs[k - 1]], start=1 if k is None else k):
        print(f"hint {i}: {h}")


def solution(id_):
    print(EX[id_]["solution"])


def _cell(v):
    # one comparable text form per value: NULL for missing, whole numbers without .0, floats to 2 decimals
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return "NULL"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        v = round(float(v), 2)
        return str(int(v)) if v.is_integer() else f"{v:.2f}"
    if hasattr(v, "is_integer") or type(v).__name__ == "Decimal":
        return _cell(float(v))
    return str(v)[:10] if hasattr(v, "strftime") else str(v)


def _normalize(df):
    out = pd.DataFrame({f"c{i}": [_cell(v) for v in df.iloc[:, i].tolist()] for i in range(df.shape[1])})
    return out.sort_values(list(out.columns)).reset_index(drop=True)


def check(id_, query):
    """compare your query's result to the solution's (column order matters, names and row order don't)"""
    if not query or not query.strip() or query.strip().startswith("-- your query"):
        print(f"[{id_}] not attempted yet")
        return None
    try:
        mine = run(query)
    except Exception as err:  # show the database error instead of a traceback
        print(f"[{id_}] your query raised an error:\n{err}")
        return False
    target = run(EX[id_]["solution"])
    if mine.shape[1] != target.shape[1]:
        print(f"[{id_}] ✗ you returned {mine.shape[1]} columns; expected {target.shape[1]}: "
              f"{list(target.columns)}")
        return False
    if len(mine) != len(target):
        print(f"[{id_}] ✗ you returned {len(mine)} rows; expected {len(target)}")
        return False
    a, b = _normalize(mine), _normalize(target)
    if a.equals(b):
        print(f"[{id_}] ✓ correct")
        return True
    diff = (a != b).any(axis=1)
    print(f"[{id_}] ✗ same shape, but {int(diff.sum())} of {len(a)} rows differ "
          f"(after sorting). First mismatch:\n  yours:    {a[diff].iloc[0].tolist()}\n"
          f"  expected: {b[diff].iloc[0].tolist()}")
    return False
