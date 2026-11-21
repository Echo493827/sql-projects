"""Generate a fictional company's HR data (Kestrel Media Co.) for SQL practice.

Everything here is simulated. No real people or companies.

The data has one planted causal story you get to uncover later:
  - New hires from 2023 on could opt into a mentoring program in their first 30 days.
  - Enrollment is NOT random. Referral hires, more senior hires, better-paid hires,
    and non-remote hires were more likely to sign up, and those same people were
    already less likely to leave.
  - Mentoring really does lower first-year attrition, but by less than a naive
    comparison suggests.
  - Because this is a simulation, we know the true effect. It's saved to
    data/_answer_key.json. Don't open it until you've estimated it yourself.

Run:  python generate_hr_data.py      (writes CSVs into ./data, takes about 20 seconds)
"""
import json
import os

import numpy as np
import pandas as pd

seed = 2026
rng = np.random.default_rng(seed)
snapshotDate = pd.Timestamp("2026-06-30")
programStart = pd.Timestamp("2023-01-01")
outDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(outDir, exist_ok=True)

departments = ["Engineering", "Content", "Marketing", "Product", "Finance", "Talent"]
deptProbs = [0.30, 0.22, 0.16, 0.14, 0.09, 0.09]
deptMult = {"Engineering": 1.25, "Content": 1.00, "Marketing": 0.95, "Product": 1.20,
            "Finance": 1.05, "Talent": 0.90}
deptHazard = {"Engineering": 0.00, "Content": 0.15, "Marketing": 0.20, "Product": -0.05,
              "Finance": -0.10, "Talent": 0.10}
locations = ["Los Angeles", "New York", "Austin", "Remote"]
locProbs = [0.35, 0.20, 0.15, 0.30]
sources = ["Referral", "Recruiter", "Job Board", "University"]
srcProbs = [0.25, 0.35, 0.28, 0.12]
genders = ["Woman", "Man", "Nonbinary"]
genderProbs = [0.46, 0.51, 0.03]
levelBase = {1: 72000, 2: 90000, 3: 115000, 4: 145000, 5: 185000, 6: 235000, 7: 300000}

# hires per calendar year; the company existed before 2020, so seed some long-tenured staff
hiresPerYear = {2014: 90, 2015: 110, 2016: 130, 2017: 160, 2018: 200, 2019: 260,
                2020: 500, 2021: 650, 2022: 800, 2023: 900, 2024: 950, 2025: 1000, 2026: 450}


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def addMonths(ts, k):
    return ts + pd.DateOffset(months=int(k))


# ---------- step 1: draw hires ----------
rows = []
for year, n in hiresPerYear.items():
    endDay = 181 if year == 2026 else 365
    days = rng.integers(0, endDay, size=n)
    for d in days:
        rows.append(pd.Timestamp(f"{year}-01-01") + pd.Timedelta(days=int(d)))
hireDates = sorted(rows)
n = len(hireDates)

emp = pd.DataFrame({"hire_date": hireDates})
emp["employee_id"] = np.arange(100001, 100001 + n)
emp["gender"] = rng.choice(genders, size=n, p=genderProbs)
emp["location"] = rng.choice(locations, size=n, p=locProbs)
emp["hire_source"] = rng.choice(sources, size=n, p=srcProbs)
emp["department"] = rng.choice(departments, size=n, p=deptProbs)
isUni = emp["hire_source"].eq("University").to_numpy()
priorExp = np.where(isUni, rng.integers(0, 2, size=n), np.round(rng.gamma(2.2, 2.6, size=n)))
emp["prior_experience_years"] = priorExp.astype(int)
level = 1 + np.floor(priorExp / 3.5) + rng.choice([-1, 0, 0, 0, 1], size=n)
emp["job_level"] = np.clip(level, 1, 6).astype(int)
emp.loc[isUni, "job_level"] = 1
compRatio = np.clip(rng.normal(1.0, 0.08, size=n), 0.80, 1.20)
emp["comp_ratio"] = compRatio
emp["band_mid"] = [levelBase[l] * deptMult[d] for l, d in zip(emp.job_level, emp.department)]
emp["salary"] = np.round(emp["band_mid"] * compRatio / 100) * 100

# latent traits (never written to the CSVs)
ability = rng.normal(0, 1, size=n)
engBase = rng.normal(0, 1, size=n)
mgrQuality = rng.normal(0, 1, size=n)  # quality of each employee as a manager

# ---------- step 2: mentoring enrollment (non-random) ----------
eligible = (emp["hire_date"] >= programStart).to_numpy()
enrollLogit = (-1.55
               + 1.30 * emp["hire_source"].eq("Referral").to_numpy()
               + 0.55 * (emp["job_level"].to_numpy() >= 3)
               + 6.00 * (compRatio - 1.0)
               + 0.08 * np.minimum(priorExp, 10)
               - 1.00 * emp["location"].eq("Remote").to_numpy()
               + 0.40 * emp["department"].isin(["Engineering", "Product"]).to_numpy())
enrollProb = sigmoid(enrollLogit)
mentored = eligible & (rng.random(n) < enrollProb)
emp["mentored"] = mentored
emp["enroll_date"] = [h + pd.Timedelta(days=int(rng.integers(3, 30))) if m else pd.NaT
                      for h, m in zip(emp.hire_date, mentored)]

# ---------- step 3: simulate each career month by month ----------
# common random numbers: every employee gets one fixed stream of draws, so we can
# replay their first year with and without mentoring and get both potential outcomes
import datetime as dt

maxMonths = int((snapshotDate.year - 2014) * 12 + 12)
uExit = rng.random((n, maxMonths))
uInvol = rng.random((n, maxMonths))
uPromo = rng.random((n, maxMonths))
uTransfer = rng.random((n, maxMonths))
uTransferDept = rng.integers(0, 5, size=(n, maxMonths))
uDay = rng.integers(0, 28, size=n)
ratingNoise = rng.normal(0, 0.7, size=(n, 15))
ratingMissing = rng.random((n, 15)) < 0.06
surveyU = rng.random((n, 60))
surveyNoise = rng.normal(0, 0.6, size=(n, 60, 4))
reasonGumbel = rng.gumbel(size=(n, 6))

snap = snapshotDate.date()
hireArr = [d.date() for d in emp["hire_date"]]
eidArr = emp["employee_id"].to_numpy()
deptArr = emp["department"].to_numpy()
levelArr = emp["job_level"].to_numpy()
salArr = emp["salary"].to_numpy()
isReferral = emp["hire_source"].eq("Referral").to_numpy()
isRemote = emp["location"].eq("Remote").to_numpy()
deptCodes = {d: k for k, d in enumerate(departments)}
deptCodeArr = np.array([deptCodes[d] for d in deptArr])
termOrdinal = np.full(n, 10**9)  # ordinal of termination date; huge = still employed

managerOf = np.full(n, -1)
termDate = [pd.NaT] * n
termType = [None] * n
termReason = [None] * n
jobRows, compRows, reviewRows, surveyRows = [], [], [], []
firstYearLeft = {}  # i -> (left within a year if mentored, if not)
reasons = ["Better Pay", "Career Growth", "Manager", "Relocation", "Personal", "Workload/Schedule"]


def pickManager(i):
    # managers: level 4+ at hire, same department, hired earlier, still employed on this hire date
    lo = max(0, i - 2500)
    hOrd = hireArr[i].toordinal()
    mask = ((deptCodeArr[lo:i] == deptCodeArr[i]) & (levelArr[lo:i] >= 4) & (termOrdinal[lo:i] > hOrd))
    cands = np.nonzero(mask)[0] + lo
    return int(rng.choice(cands)) if len(cands) else -1


def runCareer(i, isMentored, record):
    """simulate employee i from hire to exit or snapshot; returns (termDate, termType, reason)"""
    h = hireArr[i]
    lvl = int(levelArr[i])
    dept = deptArr[i]
    sal = float(salArr[i])
    cr = float(compRatio[i])
    mgr = managerOf[i]
    mq = mgrQuality[mgr] if mgr >= 0 else 0.0
    mgrId = int(eidArr[mgr]) if mgr >= 0 else None
    lastRating = None
    lastPromoMonth = -99
    reviewIdx = 0
    surveyIdx = 0
    k = 0
    while k < maxMonths:
        total = h.month - 1 + k
        year, month = h.year + total // 12, total % 12 + 1
        monthStart = dt.date(year, month, 1)
        if monthStart > snap:
            return pd.NaT, None, None
        inFirstYear = k < 12
        engNow = engBase[i] + 0.3 * mq + (0.90 if (isMentored and inFirstYear) else 0.0)

        # march: merit and promotion based on last december's rating, plus rare transfers
        if month == 3 and k >= 3 and lastRating is not None:
            effDate = dt.date(year, 3, 1)
            if not np.isnan(lastRating):
                promoP = sigmoid(-2.6 + 0.9 * (lastRating - 3) + 0.15 * min(k / 12, 5))
                if uPromo[i, k] < promoP and lvl < 7:
                    lvl += 1
                    sal = round(sal * 1.10 / 100) * 100
                    lastPromoMonth = k
                    if record:
                        jobRows.append((eidArr[i], effDate, dept, lvl, mgrId, "Promotion"))
                        compRows.append((eidArr[i], effDate, sal, "Promotion"))
                else:
                    pct = max(0.0, 0.025 + 0.012 * (lastRating - 3))
                    if pct > 0:
                        sal = round(sal * (1 + pct) / 100) * 100
                        if record:
                            compRows.append((eidArr[i], effDate, sal, "Merit"))
            if uTransfer[i, k] < 0.025:
                others = [x for x in departments if x != dept]
                dept = others[int(uTransferDept[i, k])]
                if record:
                    jobRows.append((eidArr[i], dt.date(year, 3, 15), dept, lvl, mgrId, "Transfer"))

        # quarterly engagement pulse (from 2022); recording only, never changes the career
        if record and month in (3, 6, 9, 12) and year >= 2022 and k >= 1 and surveyIdx < 60:
            sDate = dt.date(year, month, 15)
            if sDate <= snap:
                if surveyU[i, surveyIdx] < sigmoid(0.85 + 0.3 * engNow):
                    nz = surveyNoise[i, surveyIdx]
                    vals = np.clip(np.round([3.5 + 0.65 * engNow + nz[0],
                                             3.6 + 0.45 * engNow + 0.5 * mq + nz[1],
                                             3.3 + 0.55 * engNow + nz[2],
                                             3.7 + 0.75 * engNow + nz[3]]), 1, 5).astype(int)
                    surveyRows.append((eidArr[i], sDate, *vals))
                surveyIdx += 1

        # december performance review for anyone hired at least 60 days before
        if month == 12 and (monthStart - h).days >= 60:
            rIdx = min(reviewIdx, 14)
            if ratingMissing[i, rIdx]:
                lastRating = np.nan
            else:
                lastRating = float(np.clip(np.round(3 + 0.8 * ability[i] + ratingNoise[i, rIdx]), 1, 5))
            if record:
                reviewRows.append((eidArr[i], year, None if np.isnan(lastRating) else int(lastRating),
                                   "Not completed" if np.isnan(lastRating) else "Completed"))
            reviewIdx += 1

        # monthly exit hazards
        volLogit = (-4.55 + 0.95 * inFirstYear + 0.35 * (12 <= k < 24)
                    - 0.25 * (lvl - 1) - 3.5 * (cr - 1.0)
                    - 0.55 * isReferral[i] + 0.45 * isRemote[i]
                    + deptHazard[dept] - 0.40 * engNow - 0.25 * mq
                    - 0.45 * (k - lastPromoMonth < 12)
                    - (0.05 if (isMentored and inFirstYear) else 0.0))
        invLogit = -6.1 - 0.7 * ability[i]
        d = monthStart + dt.timedelta(days=int(uDay[i]))
        if d <= h:
            d = h + dt.timedelta(days=1)
        if uExit[i, k] < sigmoid(volLogit):
            if d > snap:
                return pd.NaT, None, None
            weights = np.array([1.0 + 10.0 * max(0.0, 1 - cr), 1.0 + 0.6 * (k - lastPromoMonth > 24),
                                0.6 + 0.8 * max(0.0, -mq), 0.5 + 0.4 * isRemote[i], 0.9, 0.6 + 0.3 * inFirstYear])
            r = reasons[int(np.argmax(np.log(weights) + reasonGumbel[i]))]
            return pd.Timestamp(d), "Voluntary", r
        if uInvol[i, k] < sigmoid(invLogit):
            if d > snap:
                return pd.NaT, None, None
            r = "Performance" if ability[i] < -0.3 else ("Restructuring" if uInvol[i, k] < 0.0008 else "Conduct")
            return pd.Timestamp(d), "Involuntary", r
        k += 1
    return pd.NaT, None, None


for i in range(n):
    managerOf[i] = pickManager(i)
    mgrId = int(eidArr[managerOf[i]]) if managerOf[i] >= 0 else None
    jobRows.append((eidArr[i], hireArr[i], deptArr[i], int(levelArr[i]), mgrId, "Hire"))
    compRows.append((eidArr[i], hireArr[i], float(salArr[i]), "Hire"))
    if eligible[i]:
        # potential outcomes: replay the career both ways (nothing recorded)
        t1, _, _ = runCareer(i, True, record=False)
        t0, _, _ = runCareer(i, False, record=False)
        cutoff = pd.Timestamp(hireArr[i]) + pd.Timedelta(days=365)
        firstYearLeft[i] = (int(pd.notna(t1) and t1 < cutoff), int(pd.notna(t0) and t0 < cutoff))
    t, tt, rr = runCareer(i, bool(mentored[i]), record=True)
    termDate[i], termType[i], termReason[i] = t, tt, rr
    if pd.notna(t):
        termOrdinal[i] = t.date().toordinal()

# sanity check: the recorded career must match the replayed potential outcome
for i in firstYearLeft:
    cutoff = pd.Timestamp(hireArr[i]) + pd.Timedelta(days=365)
    observed = int(pd.notna(termDate[i]) and termDate[i] < cutoff)
    assert observed == firstYearLeft[i][0 if mentored[i] else 1], i

# ---------- step 4: write tables ----------
fmt = lambda s: pd.to_datetime(s).dt.strftime("%Y-%m-%d")

employees = emp[["employee_id", "hire_date", "gender", "location", "hire_source", "prior_experience_years"]].copy()
employees["hire_date"] = fmt(employees["hire_date"])
employees.to_csv(os.path.join(outDir, "employees.csv"), index=False)

jobHistory = pd.DataFrame(jobRows, columns=["employee_id", "effective_date", "department", "job_level",
                                            "manager_id", "change_type"])
jobHistory = jobHistory.sort_values(["employee_id", "effective_date"]).reset_index(drop=True)
jobHistory["manager_id"] = jobHistory["manager_id"].astype("Int64")
jobHistory["effective_date"] = fmt(jobHistory["effective_date"])
jobHistory.to_csv(os.path.join(outDir, "job_history.csv"), index=False)

comp = pd.DataFrame(compRows, columns=["employee_id", "effective_date", "base_salary", "change_reason"])
comp = comp.sort_values(["employee_id", "effective_date"])
comp["effective_date"] = fmt(comp["effective_date"])
comp["base_salary"] = comp["base_salary"].round(0).astype(int)
comp.to_csv(os.path.join(outDir, "compensation.csv"), index=False)

bands = pd.DataFrame([(d, l, round(levelBase[l] * deptMult[d] * 0.8 / 100) * 100,
                       round(levelBase[l] * deptMult[d] / 100) * 100,
                       round(levelBase[l] * deptMult[d] * 1.2 / 100) * 100)
                      for d in departments for l in range(1, 8)],
                     columns=["department", "job_level", "band_min", "band_mid", "band_max"])
bands.to_csv(os.path.join(outDir, "salary_bands.csv"), index=False)

reviews = pd.DataFrame(reviewRows, columns=["employee_id", "review_year", "rating", "review_status"])
reviews["rating"] = reviews["rating"].astype("Int64")
reviews.to_csv(os.path.join(outDir, "performance_reviews.csv"), index=False)

survey = pd.DataFrame(surveyRows, columns=["employee_id", "survey_date", "belonging", "manager_support",
                                           "growth", "intent_to_stay"])
survey["survey_date"] = fmt(survey["survey_date"])
survey.to_csv(os.path.join(outDir, "engagement_survey.csv"), index=False)

ment = emp.loc[emp["mentored"], ["employee_id", "enroll_date"]].copy()
ment["enroll_date"] = fmt(ment["enroll_date"])
ment.to_csv(os.path.join(outDir, "mentoring_enrollments.csv"), index=False)

terms = pd.DataFrame({"employee_id": emp["employee_id"], "termination_date": termDate,
                      "termination_type": termType, "reason": termReason}).dropna(subset=["termination_date"])
terms["termination_date"] = fmt(terms["termination_date"])
terms.to_csv(os.path.join(outDir, "terminations.csv"), index=False)

# ---------- step 5: answer key (true effects from the replayed potential outcomes) ----------
idx = np.array(sorted(firstYearLeft))
y1 = np.array([firstYearLeft[i][0] for i in idx])
y0 = np.array([firstYearLeft[i][1] for i in idx])
treatedMask = mentored[idx]
eligibleCohort = (emp.loc[idx, "hire_date"] <= pd.Timestamp("2025-06-30")).to_numpy()
key = {
    "description": "True effect of mentoring on leaving within 365 days of hire, for hires 2023-01-01 to "
                   "2025-06-30. Negative = mentoring lowers the chance of leaving. Units: proportion "
                   "(multiply by 100 for percentage points).",
    "true_ATT": float((y1 - y0)[treatedMask & eligibleCohort].mean()),
    "true_ATE": float((y1 - y0)[eligibleCohort].mean()),
    "n_cohort": int(eligibleCohort.sum()),
    "n_mentored": int((treatedMask & eligibleCohort).sum()),
    "seed": seed,
}
with open(os.path.join(outDir, "_answer_key.json"), "w") as f:
    json.dump(key, f, indent=2)

print(f"employees: {len(employees):,}  job_history: {len(jobHistory):,}  compensation: {len(comp):,}")
print(f"reviews: {len(reviews):,}  survey responses: {len(survey):,}  terminations: {len(terms):,}")
print(f"mentored: {len(ment):,}  answer key written to data/_answer_key.json")
