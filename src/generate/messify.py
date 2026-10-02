"""Turn clean SYNTHETIC tables into messy raw exports.

The mess is deliberate so that the pipeline's cleaning code has real work to do:
period strings, mixed-case and "+alias" e-mails, decimal commas, numbers stored as strings,
trailing blank columns, all-empty rows and exact duplicate rows.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import ROOT, load_config
from .simulate import EMAIL_DOMAIN, Truth, simulate


def _dec_comma(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def _inject_blank_rows(df: pd.DataFrame, rate: float, rng: np.random.Generator) -> pd.DataFrame:
    n_blank = int(len(df) * rate)
    if n_blank == 0:
        return df
    pos = np.sort(rng.integers(0, len(df), n_blank))
    blank = pd.DataFrame({c: [""] * n_blank for c in df.columns})
    out = pd.concat([df.iloc[:0], df], ignore_index=True)
    pieces, prev = [], 0
    for i, p in enumerate(pos):
        pieces.append(out.iloc[prev:p])
        pieces.append(blank.iloc[[i]])
        prev = p
    pieces.append(out.iloc[prev:])
    return pd.concat(pieces, ignore_index=True)


def _email(pid: int, rng_case: float, mix_rate: float, alias: str | None = None) -> str:
    local = f"user{pid:06d}" + (f"+{alias}" if alias else "")
    mail = f"{local}@{EMAIL_DOMAIN}"
    if rng_case < mix_rate:  # mixed-case variant of the same address
        mail = mail.replace("user", "User", 1).replace("example", "Example")
    return mail


def build_raw(t: Truth) -> dict[str, pd.DataFrame]:
    cfg, m = t.cfg, t.cfg["messiness"]
    rng = np.random.default_rng(cfg["seed"] + 99)
    as_of = pd.Timestamp(cfg["as_of_date"])

    # --- ad performance -------------------------------------------------------------
    a = t.ads
    ad = pd.DataFrame({
        "Campaign name": a.campaign,
        "Channel": a.channel,
        "Country": a.country,
        "Reporting period": a.period_start.dt.strftime("%Y-%m-%d") + " - " + a.period_end.dt.strftime("%Y-%m-%d"),
        "Amount spent (EUR)": [_dec_comma(x) for x in a.spend_eur],
        "Impressions": a.impressions.astype(str),
        "Reach": a.reach.astype(str),
        "Frequency": [_dec_comma(i / r, 2) if r else "" for i, r in zip(a.impressions, a.reach)],
        "Link clicks": a.link_clicks.astype(str),
        "Landing page views": a.landing_page_views.astype(str),
        "Subscriptions": a.signups.astype(str),
    })
    ad = _inject_blank_rows(ad, m["blank_row_rate"], rng)
    ad[""] = ""   # trailing blank columns, as left by spreadsheet exports
    ad[" "] = ""

    # --- users (people + "+alias" second accounts) ------------------------------------
    u = t.users
    case = rng.random(len(u))
    plan_now = np.array(["free"] * len(u), dtype=object)
    last = t.events.sort_values(["event_ts", "person_id"]).groupby("person_id").plan_to.last()
    plan_now = u.person_id.map(last).fillna("free").to_numpy()
    users = pd.DataFrame({
        "email": [_email(p, c, m["mixed_case_rate"]) for p, c in zip(u.person_id, case)],
        "signup_date": u.signup_date.dt.strftime("%Y-%m-%d"),
        "country": np.where(rng.random(len(u)) < 0.05, u.country.str.lower(), u.country),
        "acquisition_source": u.source,
        "plan": plan_now,
    })
    alias_mask = rng.random(len(u)) < cfg["users"]["alias_duplicate_rate"]
    alias_delay = rng.integers(1, 46, len(u))
    alias_signup = (u.signup_date + pd.to_timedelta(alias_delay, unit="D")).clip(upper=as_of)
    alias = pd.DataFrame({
        "email": [_email(p, 1.0, 0.0, "promo") for p in u.person_id[alias_mask]],
        "signup_date": alias_signup[alias_mask].dt.strftime("%Y-%m-%d"),
        "country": u.country[alias_mask], "acquisition_source": u.source[alias_mask], "plan": "free"})
    users = pd.concat([users, alias], ignore_index=True)
    users = _inject_blank_rows(users, m["blank_row_rate"], rng)
    users[""] = ""

    # --- daily usage (alias accounts take a share of their owner's activity) ----------
    use = t.usage.copy()
    use["email"] = [_email(p, c, m["mixed_case_rate"]) for p, c in
                    zip(use.person_id, rng.random(len(use)))]
    a_signup = pd.Series(alias_signup.values, index=u.person_id.values).where(alias_mask, pd.NaT)
    use_alias = use.person_id.map(a_signup)
    swap = use_alias.notna() & (use.usage_date >= use_alias) & (rng.random(len(use)) < 0.4)
    use.loc[swap, "email"] = [_email(p, 1.0, 0.0, "promo") for p in use.person_id[swap]]
    usage = pd.DataFrame({"email": use.email, "usage_date": use.usage_date.dt.strftime("%Y-%m-%d"),
                          "assets_inserted": use.assets_inserted.astype(str)})
    dup = usage.sample(frac=m["exact_duplicate_rate"], random_state=cfg["seed"])
    usage = pd.concat([usage, dup], ignore_index=True).sample(frac=1, random_state=cfg["seed"]).reset_index(drop=True)
    usage = _inject_blank_rows(usage, m["blank_row_rate"] / 4, rng)
    usage[""] = ""

    # --- subscription events -----------------------------------------------------------
    e = t.events
    ecase = rng.random(len(e))
    events = pd.DataFrame({
        "email": [_email(p, c, m["mixed_case_rate"]) for p, c in zip(e.person_id, ecase)],
        "event_ts": e.event_ts.dt.strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": e.event_type,
        "plan_from": e.plan_from.fillna(""),
        "plan_to": e.plan_to,
        "mrr_before_eur": [_dec_comma(x) for x in e.mrr_before],
        "mrr_after_eur": [_dec_comma(x) for x in e.mrr_after],
    })
    events = _inject_blank_rows(events, m["blank_row_rate"] / 4, rng)
    return {"ad_performance_raw": ad, "users_raw": users, "usage_daily_raw": usage,
            "subscription_events_raw": events}


def write_raw(out_dir: str | Path | None = None, cfg: dict | None = None) -> dict[str, int]:
    cfg = cfg or load_config()
    out = Path(out_dir or ROOT / "data" / "raw")
    out.mkdir(parents=True, exist_ok=True)
    raw = build_raw(simulate(cfg))
    counts = {}
    for name, df in raw.items():
        df.to_csv(out / f"{name}.csv", index=False)
        counts[name] = len(df)
    return counts
