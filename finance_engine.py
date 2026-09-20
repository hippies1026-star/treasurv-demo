"""Deterministic monthly scenario engine; no trading or probabilistic claims."""
import math
import hashlib
import json

KINDS = ("채용", "일회성 지출", "매출 증가", "자금조달")


def number(value, name, low=0, high=1e15):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: 숫자를 입력하세요.")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name}: {low:g}~{high:g} 범위를 확인하세요.")


def validate_plan(p):
    if not isinstance(p, dict) or p.get("kind") not in KINDS:
        raise ValueError("계획 유형을 확인하세요.")
    if not isinstance(p.get("name"), str) or not 1 <= len(p["name"].strip()) <= 80:
        raise ValueError("계획 이름은 1~80자로 입력하세요.")
    number(p.get("amount"), "계획 금액", 1)
    number(p.get("month"), "시작 월", 1, 24)
    if int(p["month"]) != p["month"]:
        raise ValueError("시작 월은 정수여야 합니다.")
    if not isinstance(p.get("recurring"), bool) or not isinstance(p.get("confirmed"), bool):
        raise ValueError("반복·확정 여부를 확인하세요.")
    if p["kind"] == "자금조달" and p["recurring"]:
        raise ValueError("자금조달은 일회성으로 입력하세요.")


def validate(d):
    for k in ("cash", "restricted", "inflow", "outflow"):
        number(d[k], k)
    if d["restricted"] > d["cash"]:
        raise ValueError("사용 제한 자금은 총 현금을 초과할 수 없습니다.")
    for k, lo, hi in [("target", 1, 24), ("buffer", 0, 12),
                      ("revenue_stress", 0, 100), ("cost_stress", 0, 100),
                      ("rate", 0, 20), ("baseline_rate", 0, 20),
                      ("allocation", 0, 100), ("tenor", 1, 12)]:
        number(d[k], k, lo, hi)
    for k in ("target", "tenor"):
        if int(d[k]) != d[k]:
            raise ValueError(f"{k}: 정수가 필요합니다.")
    for p in d["plans"]:
        validate_plan(p)


def fingerprint(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def forecast(d, stress=False, funding_delay=0, protective=False, months=24):
    validate(d)
    number(funding_delay, "조달 지연", 0, 24)
    balance = d["cash"] - d["restricted"]
    rows = []
    for month in range(1, months + 1):
        income = d["inflow"] * (1 - d["revenue_stress"] / 100 if stress else 1)
        expense = d["outflow"] * (1 + d["cost_stress"] / 100 if stress else 1)
        funding = 0
        for p in d["plans"]:
            start = p["month"] + (funding_delay if p["kind"] == "자금조달" else 0)
            if not (month == start or p["recurring"] and month >= start):
                continue
            if p["kind"] == "자금조달":
                # A survival reserve must not depend on money not yet received.
                if not protective:
                    funding += p["amount"]
            elif p["kind"] == "매출 증가":
                if not protective or p["confirmed"]:
                    income += p["amount"] * (1 - d["revenue_stress"] / 100 if stress else 1)
            else:
                expense += p["amount"] * (1 + d["cost_stress"] / 100 if stress else 1)
        net = income + funding - expense
        balance += net
        rows.append({"month": month, "inflow": income, "outflow": expense,
                     "funding": funding, "net": net, "balance": balance})
    return rows


def analyze(d):
    validate(d)
    cash = d["cash"] - d["restricted"]
    base = forecast(d)
    protective = forecast(d, stress=True, protective=True)
    target = int(d["target"])
    # Include the initial point: future receipts cannot increase today's capacity.
    cumulative = [0] + [r["balance"] - cash for r in protective[:target]]
    deficit = max(0, -min(cumulative))
    reserve = d["outflow"] * d["buffer"]
    floor = deficit + reserve
    capacity = max(0, cash - floor)
    principal = capacity * d["allocation"] / 100
    annual_interest = principal * d["rate"] / 100
    incremental = principal * (d["rate"] - d["baseline_rate"]) / 100
    first_shortfall = next((r["month"] for r in protective if r["balance"] < 0), None)
    return {"available": cash, "floor": floor, "deficit": deficit, "reserve": reserve,
            "capacity": capacity, "principal": principal,
            "interest": annual_interest, "incremental": incremental,
            "tenor_interest": annual_interest * d["tenor"] / 12,
            "shortfall": first_shortfall, "base": base, "protective": protective,
            "gap": max(0, floor - cash), "fingerprint": fingerprint(d)}
