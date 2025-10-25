import pandas as pd

def group_rates(df, label_col, group_col, positive_label=1):
    g = df.groupby(group_col)[label_col].apply(lambda s: (s==positive_label).mean()).reset_index()
    g.columns = [group_col, "positive_rate"]
    return g

def disparate_impact(df, label_col, group_col, privileged, unprivileged, positive_label=1):
    rates = group_rates(df, label_col, group_col, positive_label)
    pr = rates.loc[rates[group_col]==privileged, "positive_rate"].values
    ur = rates.loc[rates[group_col]==unprivileged, "positive_rate"].values
    if len(pr)==0 or len(ur)==0:
        return None
    return float(ur[0]/pr[0]) if pr[0] != 0 else None

def max_rate_gap(df, label_col, group_col, positive_label=1):
    rates = group_rates(df, label_col, group_col, positive_label)["positive_rate"]
    if rates.empty: return 0.0
    return float(rates.max() - rates.min())
