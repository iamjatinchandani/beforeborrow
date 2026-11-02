from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from dateutil.relativedelta import relativedelta

from app.engine.types import FinancialSnapshot


SUPPORTED_STRESS_CASES: set[str] = {
    "income_delay_7d",
    "income_drop_20pct_next_2",
    "expense_spike_5000_30d",
}


def _get_field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _to_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return date.fromisoformat(val)
    return None


def _to_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return dict(obj)
    return {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}


def stress(snapshot: FinancialSnapshot, case: str, **kwargs) -> FinancialSnapshot:
    """
    Applies a named stress scenario to a FinancialSnapshot.
    Returns a new FinancialSnapshot instance without mutating the original input.

    Supported Presets (Blueprint p. 22):
    - income_delay_7d: income arrives seven days later.
    - income_drop_20pct_next_2: income falls 20% for the next two income events.
    - expense_spike_5000_30d: an extra ₹5,000 essential expense in 30 days.
    """
    if case not in SUPPORTED_STRESS_CASES and case != "income_delay_30d":
        raise ValueError(f"Unknown stress case: {case!r}")

    # 1. Preset: Income delay (7 days default, or 30 days if specified)
    if case in ("income_delay_7d", "income_delay_30d"):
        delay_days = kwargs.get("days", 30 if case == "income_delay_30d" else 7)
        new_income_rules: list[dict] = []

        for rule in snapshot.income_rules or ():
            rule_dict = _to_dict(rule)
            due_d = _to_date(rule_dict.get("due_date"))
            start_d = _to_date(rule_dict.get("start_date"))
            end_d = _to_date(rule_dict.get("end_date"))

            if due_d:
                rule_dict["due_date"] = due_d + relativedelta(days=delay_days)
            if start_d:
                rule_dict["start_date"] = start_d + relativedelta(days=delay_days)
            if end_d:
                rule_dict["end_date"] = end_d + relativedelta(days=delay_days)

            new_income_rules.append(rule_dict)

        return FinancialSnapshot(
            opening_cash_paise=snapshot.opening_cash_paise,
            balance_as_of=snapshot.balance_as_of,
            reserve_floor_paise=snapshot.reserve_floor_paise,
            income_rules=tuple(new_income_rules),
            expense_rules=deepcopy(snapshot.expense_rules),
            obligations=deepcopy(snapshot.obligations),
            goals=deepcopy(snapshot.goals),
            data_version=snapshot.data_version,
        )

    # 2. Preset: Income drop 20% for next 2 events
    if case == "income_drop_20pct_next_2":
        drop_pct = Decimal(str(kwargs.get("drop_pct", "20.0")))
        factor = (Decimal(100) - drop_pct) / Decimal(100)

        # Collect upcoming income event occurrences on or after balance_as_of
        occurrences: list[tuple[date, int, dict]] = []
        for r_idx, rule in enumerate(snapshot.income_rules or ()):
            r_dict = _to_dict(rule)
            base_d = _to_date(r_dict.get("due_date") or r_dict.get("start_date"))
            if not base_d:
                continue
            freq = str(r_dict.get("frequency", "once")).lower()

            if freq == "once":
                if base_d >= snapshot.balance_as_of:
                    occurrences.append((base_d, r_idx, r_dict))
            elif freq == "monthly":
                i = 0
                while len(occurrences) < 10 and i < 24:
                    d = base_d + relativedelta(months=i)
                    if d >= snapshot.balance_as_of:
                        occurrences.append((d, r_idx, r_dict))
                    i += 1

        occurrences.sort(key=lambda x: x[0])
        target_dates = set(occ[0] for occ in occurrences[:2])

        new_income_rules = []
        for r_idx, rule in enumerate(snapshot.income_rules or ()):
            r_dict = _to_dict(rule)
            base_d = _to_date(r_dict.get("due_date") or r_dict.get("start_date"))
            if not base_d:
                new_income_rules.append(r_dict)
                continue

            freq = str(r_dict.get("frequency", "once")).lower()
            amt = Decimal(int(r_dict.get("amount_paise", 0)))

            if freq == "once":
                if base_d in target_dates:
                    reduced_amt = int((amt * factor).to_integral_value(rounding=ROUND_HALF_UP))
                    r_dict["amount_paise"] = reduced_amt
                new_income_rules.append(r_dict)
            elif freq == "monthly":
                # Check which of the first occurrences fall into target_dates
                matched_dates = [
                    base_d + relativedelta(months=i)
                    for i in range(24)
                    if (base_d + relativedelta(months=i)) in target_dates
                ]
                if matched_dates:
                    # Create discrete once rules for the reduced occurrences
                    for m_date in matched_dates:
                        reduced_amt = int((amt * factor).to_integral_value(rounding=ROUND_HALF_UP))
                        single_rule = dict(r_dict)
                        single_rule["frequency"] = "once"
                        single_rule["due_date"] = m_date
                        single_rule["amount_paise"] = reduced_amt
                        new_income_rules.append(single_rule)

                    # Resume recurring monthly rule starting after the last reduced date
                    last_matched = max(matched_dates)
                    resume_date = last_matched + relativedelta(months=1)
                    recurring_rule = dict(r_dict)
                    recurring_rule["due_date"] = resume_date
                    new_income_rules.append(recurring_rule)
                else:
                    new_income_rules.append(r_dict)
            else:
                new_income_rules.append(r_dict)

        return FinancialSnapshot(
            opening_cash_paise=snapshot.opening_cash_paise,
            balance_as_of=snapshot.balance_as_of,
            reserve_floor_paise=snapshot.reserve_floor_paise,
            income_rules=tuple(new_income_rules),
            expense_rules=deepcopy(snapshot.expense_rules),
            obligations=deepcopy(snapshot.obligations),
            goals=deepcopy(snapshot.goals),
            data_version=snapshot.data_version,
        )

    # 3. Preset: Extra ₹5,000 essential expense in 30 days
    if case == "expense_spike_5000_30d":
        spike_paise = int(kwargs.get("amount_paise", 500_000))  # ₹5,000
        days_ahead = int(kwargs.get("days", 30))
        spike_date = snapshot.balance_as_of + relativedelta(days=days_ahead)

        spike_rule = {
            "id": "stress-expense-spike-5k",
            "category": "essential_spike",
            "amount_paise": spike_paise,
            "due_date": spike_date,
            "frequency": "once",
            "timing": "known",
            "source": "stress_preset",
        }

        new_expense_rules = list(deepcopy(snapshot.expense_rules or ()))
        new_expense_rules.append(spike_rule)

        return FinancialSnapshot(
            opening_cash_paise=snapshot.opening_cash_paise,
            balance_as_of=snapshot.balance_as_of,
            reserve_floor_paise=snapshot.reserve_floor_paise,
            income_rules=deepcopy(snapshot.income_rules),
            expense_rules=tuple(new_expense_rules),
            obligations=deepcopy(snapshot.obligations),
            goals=deepcopy(snapshot.goals),
            data_version=snapshot.data_version,
        )

    return snapshot
