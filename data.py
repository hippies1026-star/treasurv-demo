"""Fictional demonstration records, monetary values in KRW."""
from copy import deepcopy

DEFAULT = {
    "company": "NOVA Labs", "owner": "가태용",
    "cash": 1_032_000_000, "restricted": 80_000_000,
    "inflow": 100_000_000, "outflow": 120_000_000,
    "target": 12, "buffer": 2, "revenue_stress": 15,
    "cost_stress": 5, "rate": 3.0, "baseline_rate": 0.2,
    "allocation": 70, "tenor": 3,
    "plans": [
        {"id": "demo-hire", "name": "개발자 채용", "kind": "채용", "month": 3,
         "amount": 6_000_000, "recurring": True, "confirmed": True},
        {"id": "demo-rd", "name": "제품 R&D 장비", "kind": "일회성 지출", "month": 6,
         "amount": 40_000_000, "recurring": False, "confirmed": True},
        {"id": "demo-funding", "name": "Series A 유치 계획", "kind": "자금조달", "month": 9,
         "amount": 300_000_000, "recurring": False, "confirmed": False},
    ],
}


def demo():
    return deepcopy(DEFAULT)
