"""Seeded, deterministic simulation of a SYNTHETIC freemium B2B SaaS ("Vaultly").

Produces *clean* ground-truth tables; ``messify.py`` turns them into dirty raw exports.
Only qualitative shapes are modelled (heavy-tailed usage, monotonic funnel, countries with
different economics). All parameters are round, generic numbers from ``config/synthetic.yaml``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import load_config

EMAIL_DOMAIN = "example.test"  # reserved TLD: addresses can never be real


@dataclass
class Truth:
    ads: pd.DataFrame      # campaign x country x month
    users: pd.DataFrame    # one row per person (+ alias account rows flagged)
    usage: pd.DataFrame    # person x day (clean)
    events: pd.DataFrame   # subscription events
    cfg: dict


def _month_starts(cfg) -> pd.DatetimeIndex:
    return pd.date_range(cfg["start_date"], cfg["as_of_date"], freq="MS")


def simulate_ads(cfg: dict, rng: np.random.Generator) -> pd.DataFrame:
    g, sc = cfg["growth"], cfg["scale"]["spend_scale"]
    months = _month_starts(cfg)
    as_of = pd.Timestamp(cfg["as_of_date"])
    rows = []
    chan_cpm = {"Meta Ads": 1.0, "Google Ads": 3.0}
    for code, c in cfg["countries"].items():
        for camp in cfg["campaigns"]:
            for i, m in enumerate(months):
                if i < camp["start"]:
                    continue
                season = 1 + g["seasonality_amplitude"] * np.sin(2 * np.pi * (m.month - 2) / 12)
                spend = (c["budget"] * sc * camp["share"] * (1 + g["budget_monthly_growth"]) ** i * season
                         * rng.lognormal(0, g["budget_noise_sd"]))
                cpm = c["cpm"] * chan_cpm[camp["channel"]] * rng.lognormal(0, 0.08)
                impressions = int(spend / cpm * 1000)
                if impressions < 1:
                    continue
                ctr = min(c["ctr"] * camp["ctr_mult"] * rng.lognormal(0, 0.06), 0.6)
                clicks = int(rng.binomial(impressions, ctr))
                lpv = int(rng.binomial(clicks, min(c["lpv_rate"] * rng.normal(1, 0.02), 0.99)))
                su_rate = min(c["signup_rate"] * camp["signup_mult"] * rng.lognormal(0, 0.06), 0.9)
                signups = int(rng.binomial(lpv, su_rate))
                freq = max(1.0, c["freq"] * rng.lognormal(0, 0.05))
                end = min(m + pd.offsets.MonthEnd(0), as_of)
                rows.append((camp["name"], camp["channel"], code, m, end, round(spend, 2), impressions,
                             int(impressions / freq), clicks, lpv, signups))
    cols = ["campaign", "channel", "country", "period_start", "period_end", "spend_eur", "impressions",
            "reach", "link_clicks", "landing_page_views", "signups"]
    return pd.DataFrame(rows, columns=cols)


def _new_users(cfg: dict, ads: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Paid users equal ad signups (so ad data and user data reconcile); organic users are added."""
    g, osc = cfg["growth"], cfg["scale"]["organic_scale"]
    as_of = pd.Timestamp(cfg["as_of_date"])
    src_of = {c["name"]: c["source"] for c in cfg["channels"]}
    parts = []
    for r in ads.itertuples(index=False):
        if r.signups <= 0:
            continue
        span = (r.period_end - r.period_start).days + 1
        offs = rng.integers(0, span, r.signups)
        parts.append(pd.DataFrame({
            "country": r.country, "source": src_of[r.channel],
            "signup_date": r.period_start + pd.to_timedelta(offs, unit="D")}))
    months = _month_starts(cfg)
    for code, c in cfg["countries"].items():
        for i, m in enumerate(months):
            n = rng.poisson(c["organic"] * osc * (1 + g["organic_monthly_growth"]) ** i)
            if n == 0:
                continue
            end = min(m + pd.offsets.MonthEnd(0), as_of)
            offs = rng.integers(0, (end - m).days + 1, n)
            ref = cfg["users"]["referral_share_of_organic"]
            src = rng.choice(["organic_search", "referral", "direct"], n, p=[1 - ref - 0.25, ref, 0.25])
            parts.append(pd.DataFrame({"country": code, "source": src,
                                       "signup_date": m + pd.to_timedelta(offs, unit="D")}))
    u = pd.concat(parts, ignore_index=True)
    u = u[u.signup_date <= as_of].sort_values(["signup_date", "country", "source"], kind="stable")
    u = u.reset_index(drop=True)
    u.insert(0, "person_id", np.arange(1, len(u) + 1))
    return u


def _lifecycle(cfg: dict, u: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Latent engagement -> usage intensity, dormancy, upgrade, plan changes and cancellation."""
    uc, countries = cfg["users"], cfg["countries"]
    n = len(u)
    as_of = pd.Timestamp(cfg["as_of_date"])
    t0 = pd.Timestamp(cfg["start_date"])
    sday = (u.signup_date - t0).dt.days.to_numpy()
    last_day = (as_of - t0).days
    z = rng.normal(size=n)
    eps = rng.normal(size=n)
    power = rng.random(n) < uc["power_user_rate"]
    lam = uc["usage_median_assets"] * np.exp(uc["usage_sigma"] * (0.7 * z + 0.714 * eps))
    lam = np.where(power, lam * uc["power_user_usage_multiplier"], lam)
    logit = np.log(uc["active_day_prob_mean"] / (1 - uc["active_day_prob_mean"])) + 0.6 * z + 0.4 * rng.normal(size=n)
    p_active = 1 / (1 + np.exp(-logit))
    p_active = np.where(power, np.maximum(p_active, 0.5), p_active)

    h = uc["free_dormancy_monthly"] * np.exp(-uc["engagement_dormancy_beta"] * z)
    dormant_day = sday + np.ceil(rng.exponential(30.0 / h)).astype(int)

    ctry = u.country.map(lambda k: countries[k]["upgrade"]).to_numpy()
    churn = u.country.map(lambda k: countries[k]["churn"]).to_numpy()
    src_mult = np.where(u.source.isin(["paid_social", "paid_search"]),
                        uc["paid_upgrade_multiplier"], uc["organic_upgrade_multiplier"])
    beta = uc["engagement_upgrade_beta"]
    prob = ctry * src_mult * np.exp(beta * z) / np.exp(beta**2 / 2)
    prob = np.where(power, prob * uc["power_user_upgrade_multiplier"], prob)
    prob = np.clip(prob, 0, 0.7)
    willing = rng.random(n) < prob
    delay = uc["upgrade_delay_min_days"] + np.ceil(rng.exponential(uc["upgrade_delay_mean_days"], n)).astype(int)
    up_day = sday + delay
    upgraded = willing & (up_day <= dormant_day) & (up_day <= last_day)

    cancel_day = up_day + np.ceil(rng.exponential(30.0 / churn)).astype(int)
    cancelled = upgraded & (cancel_day <= last_day)
    end_day = np.where(upgraded, np.where(cancelled, cancel_day, last_day), np.minimum(dormant_day, last_day))

    mix = uc["plan_mix_by_engagement"]
    w = np.stack([mix["starter"] * np.exp(-0.5 * z), mix["pro"] * np.ones(n), mix["team"] * np.exp(1.0 * z)], 1)
    w /= w.sum(1, keepdims=True)
    pick = (rng.random(n)[:, None] > w.cumsum(1)).sum(1)  # 0 starter, 1 pro, 2 team
    pick = np.minimum(pick, 2)
    down = upgraded & (pick > 0) & (rng.random(n) < uc["downgrade_rate"])
    last_paid = np.where(cancelled, cancel_day, last_day)
    down_day = np.where(down, up_day + 1 + (rng.random(n) * np.maximum(last_paid - up_day - 1, 1)).astype(int), -1)
    down = down & (down_day < last_paid)

    out = u.copy()
    out["z"], out["lam"], out["p_active"], out["is_power"] = z, lam, p_active, power
    out["signup_day"], out["end_day"] = sday, end_day
    out["upgraded"], out["up_day"], out["cancelled"], out["cancel_day"] = upgraded, up_day, cancelled, cancel_day
    out["plan_idx"], out["downgraded"], out["down_day"] = pick, down, down_day
    return out


def _usage(cfg: dict, u: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    uc = cfg["users"]
    t0 = pd.Timestamp(cfg["as_of_date"]) - pd.Timedelta(days=0)
    start = pd.Timestamp(cfg["start_date"])
    frames = []
    for lo in range(0, len(u), 4000):
        c = u.iloc[lo:lo + 4000]
        lens = (c.end_day.to_numpy() - c.signup_day.to_numpy() + 1).clip(min=1)
        idx = np.repeat(np.arange(len(c)), lens)
        starts = np.cumsum(lens) - lens
        t = np.arange(lens.sum()) - np.repeat(starts, lens)
        up = np.where(c.upgraded.to_numpy(), c.up_day.to_numpy() - c.signup_day.to_numpy(), 10**9)[idx]
        paid_now = t >= up
        pre = (t >= up - 30) & (t < up)
        base = c.p_active.to_numpy()[idx]
        decay = np.where(paid_now, 0.6 + 0.4 * np.exp(-t / 90), 0.4 + 0.6 * np.exp(-t / 60))
        p = base * decay
        p = np.where(pre, np.minimum(p * 1.3, 0.95), p)
        p = np.where(t == 0, 0.8, p)
        active = rng.random(len(t)) < p
        lam = c.lam.to_numpy()[idx] * np.where(pre, uc["pre_upgrade_surge"], 1.0) * np.where(paid_now, uc["paid_usage_multiplier"], 1.0)
        ins = 1 + rng.poisson(lam * rng.gamma(1.5, 1 / 1.5, len(t)))
        sel = active
        day = c.signup_day.to_numpy()[idx][sel] + t[sel]
        frames.append(pd.DataFrame({"person_id": c.person_id.to_numpy()[idx][sel],
                                    "usage_date": start + pd.to_timedelta(day, unit="D"),
                                    "assets_inserted": ins[sel].astype(int)}))
    _ = t0
    return pd.concat(frames, ignore_index=True)


def _events(cfg: dict, u: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    start = pd.Timestamp(cfg["start_date"])
    plans = [p for p in cfg["plans"] if p["tier"] == "paid"]
    names = [p["name"] for p in plans]
    price = {p["name"]: p["price"] for p in plans}
    pidx = u.country.map(lambda k: cfg["countries"][k]["price_index"]).to_numpy()
    rows = []

    def ts(day):
        return start + pd.to_timedelta(day, unit="D") + pd.to_timedelta(rng.integers(8 * 3600, 20 * 3600, len(day)), unit="s")

    t_sign = ts(u.signup_day.to_numpy())
    rows.append(pd.DataFrame({"person_id": u.person_id, "event_ts": t_sign, "event_type": "signup",
                              "plan_from": None, "plan_to": "free", "mrr_before": 0.0, "mrr_after": 0.0}))
    m = u.upgraded.to_numpy()
    plan_to = np.array(names)[u.plan_idx.to_numpy()]
    mrr_up = np.round(np.array([price[p] for p in plan_to]) * pidx, 2)
    rows.append(pd.DataFrame({"person_id": u.person_id[m], "event_ts": ts(u.up_day.to_numpy()[m]),
                              "event_type": "upgrade", "plan_from": "free", "plan_to": plan_to[m],
                              "mrr_before": 0.0, "mrr_after": mrr_up[m]}))
    d = u.downgraded.to_numpy()
    lower = np.array(names)[np.maximum(u.plan_idx.to_numpy() - 1, 0)]
    mrr_dn = np.round(np.array([price[p] for p in lower]) * pidx, 2)
    rows.append(pd.DataFrame({"person_id": u.person_id[d], "event_ts": ts(u.down_day.to_numpy()[d]),
                              "event_type": "downgrade", "plan_from": plan_to[d], "plan_to": lower[d],
                              "mrr_before": mrr_up[d], "mrr_after": mrr_dn[d]}))
    c = u.cancelled.to_numpy()
    last_plan = np.where(d, lower, plan_to)
    last_mrr = np.where(d, mrr_dn, mrr_up)
    rows.append(pd.DataFrame({"person_id": u.person_id[c], "event_ts": ts(u.cancel_day.to_numpy()[c]),
                              "event_type": "cancel", "plan_from": last_plan[c], "plan_to": "free",
                              "mrr_before": last_mrr[c], "mrr_after": 0.0}))
    ev = pd.concat(rows, ignore_index=True)
    ev = ev.sort_values(["event_ts", "person_id"], kind="stable").reset_index(drop=True)
    return ev


def simulate(cfg: dict | None = None) -> Truth:
    cfg = cfg or load_config()
    master = np.random.SeedSequence(cfg["seed"])
    r_ads, r_users, r_life, r_use, r_ev = (np.random.default_rng(s) for s in master.spawn(5))
    ads = simulate_ads(cfg, r_ads)
    users = _new_users(cfg, ads, r_users)
    users = _lifecycle(cfg, users, r_life)
    usage = _usage(cfg, users, r_use)
    events = _events(cfg, users, r_ev)
    return Truth(ads=ads, users=users, usage=usage, events=events, cfg=cfg)
