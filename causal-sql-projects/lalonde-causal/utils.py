"""Small helpers shared by the Lalonde notebooks. Each one is written out and explained
in the notebook where it first appears; this file just saves retyping."""
import os

import numpy as np
import pandas as pd

here = os.path.dirname(os.path.abspath(__file__))
covariates = ["age", "educ", "black", "hisp", "marr", "nodegree", "re74", "re75"]


def loadData():
    """returns (experiment, cps): the NSW experiment (Dehejia-Wahba sample) and the CPS comparison group"""
    expPath = os.path.join(here, "data", "nsw_experiment.csv")
    cpsPath = os.path.join(here, "data", "cps_comparison.csv")
    if os.path.exists(expPath) and os.path.exists(cpsPath):
        experiment, cps = pd.read_csv(expPath), pd.read_csv(cpsPath)
    else:  # fallback, e.g. on colab without the data folder: pip install causaldata
        from causaldata import cps_mixtape, nsw_mixtape
        experiment = nsw_mixtape.load_pandas().data.drop(columns="data_id")
        cps = cps_mixtape.load_pandas().data.drop(columns="data_id")
    return experiment, cps


def addFeatures(df):
    """extra columns used in richer models: squares, 'no earnings' flags, earnings in $1,000s"""
    out = df.copy()
    out["age2"] = out["age"] ** 2
    out["educ2"] = out["educ"] ** 2
    out["u74"] = (out["re74"] == 0).astype(int)  # unemployed all of 1974
    out["u75"] = (out["re75"] == 0).astype(int)
    out["re74k"] = out["re74"] / 1000
    out["re75k"] = out["re75"] / 1000
    return out


def smd(x, t, w=None):
    """standardized mean difference: (treated mean - control mean) / pooled sd (unweighted sds)"""
    x, t = np.asarray(x, float), np.asarray(t)
    w = np.ones_like(x) if w is None else np.asarray(w, float)
    m1 = np.average(x[t == 1], weights=w[t == 1])
    m0 = np.average(x[t == 0], weights=w[t == 0])
    pooledSd = np.sqrt((x[t == 1].var(ddof=1) + x[t == 0].var(ddof=1)) / 2)
    return (m1 - m0) / pooledSd if pooledSd > 0 else 0.0


def balanceTable(df, cols, treatCol="treat", w=None):
    """treated mean, control mean (weighted if w given), and smd for each covariate"""
    t = df[treatCol].to_numpy()
    w = np.ones(len(df)) if w is None else np.asarray(w, float)
    rows = []
    for c in cols:
        x = df[c].to_numpy(float)
        rows.append({"covariate": c,
                     "treated_mean": np.average(x[t == 1], weights=w[t == 1]),
                     "control_mean": np.average(x[t == 0], weights=w[t == 0]),
                     "smd": smd(x, t, w)})
    return pd.DataFrame(rows).set_index("covariate").round(3)
