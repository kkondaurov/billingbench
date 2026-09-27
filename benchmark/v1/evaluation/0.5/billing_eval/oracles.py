"""Small exact economic calculations, independent of candidate implementation."""

from calendar import monthrange
from datetime import date, datetime, timedelta
from fractions import Fraction


def rational(value):
    if isinstance(value, dict):
        return Fraction(int(value["numerator"]), int(value["denominator"]))
    return Fraction(str(value))


def money(value):
    value = rational(value)
    sign = -1 if value < 0 else 1
    n, d = abs(value.numerator), value.denominator
    return sign * ((2 * n + d) // (2 * d))


def allocate(total, weights):
    """Weights keyed by published business tie keys; signed totals conserve cents."""
    if not weights:
        if total:
            raise ValueError("nonzero allocation has no recipients")
        return {}
    weights = {key: rational(weight) for key, weight in weights.items()}
    if any(weight < 0 for weight in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("allocation requires positive total nonnegative weight")
    shares = {key: abs(total) * weight / sum(weights.values()) for key, weight in weights.items()}
    result = {key: share.numerator // share.denominator for key, share in shares.items()}
    order = sorted(shares, key=lambda key: (-(shares[key] - result[key]), key))
    for key in order[:abs(total) - sum(result.values())]:
        result[key] += 1
    return {key: value if total >= 0 else -value for key, value in result.items()}


def day(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def days(start, end):
    return (day(end) - day(start)).days


def shift_month(value, delta, selected_day=None, month_end=False):
    value = day(value)
    number = value.year * 12 + value.month - 1 + delta
    year, month = number // 12, number % 12 + 1
    last = monthrange(year, month)[1]
    return date(year, month, last if month_end else min(selected_day or value.day, last))


def periods(starts_on, ends_before, months=1, anchor="service_start", anchor_day=None):
    start, end = day(starts_on), day(ends_before)
    if end <= start:
        raise ValueError("empty term")
    selected = anchor_day if anchor == "day" else start.day
    index = 0
    boundary = lambda i: shift_month(start, months * i, selected, anchor == "month_end")
    while boundary(index) > start:
        index -= 1
    while boundary(index + 1) <= start:
        index += 1
    result = []
    while boundary(index) < end:
        left, right = boundary(index), boundary(index + 1)
        result.append((max(left, start), min(right, end), left, right))
        index += 1
    return result


def tariff(quantity, bands, model):
    quantity = rational(quantity)
    if quantity < 0:
        raise ValueError("negative quantity")
    if quantity == 0:
        return Fraction(0)
    if model in ("volume", "per_unit"):
        for band in bands:
            if band["up_to"] is None or quantity < rational(band["up_to"]):
                return quantity * rational(band["unit_price"]) * 100
    elif model == "graduated":
        total, lower = Fraction(0), Fraction(0)
        for band in bands:
            upper = quantity if band["up_to"] is None else rational(band["up_to"])
            width = max(Fraction(0), min(quantity, upper) - lower)
            total += width * rational(band["unit_price"]) * 100
            lower = upper
        return total
    raise ValueError("tariff does not cover quantity or unknown model")


def charge(quantity, bands, model, included=0, minimum=None, maximum=None, ratio=1):
    raw = tariff(max(Fraction(0), rational(quantity) - rational(included)), bands, model)
    bounded = max(raw, minimum) if minimum is not None else raw
    bounded = min(bounded, maximum) if maximum is not None else bounded
    return money(bounded * rational(ratio))


def recurring(price, quantity, included, active_days, period_days, model="per_unit", minimum=None, maximum=None):
    units = 1 if model == "flat" else max(Fraction(0), rational(quantity) - rational(included))
    gross = rational(price) * 100 * units
    gross = max(gross, minimum) if minimum is not None else gross
    gross = min(gross, maximum) if maximum is not None else gross
    return money(gross * Fraction(active_days, period_days))


def earned(amount, completed, total):
    return money(amount * rational(completed) / rational(total))


def positions(billed, recognized):
    return {"position_minor": billed - recognized, "asset_minor": max(recognized - billed, 0),
            "deferred_minor": max(billed - recognized, 0)}


def discount(amounts, groups):
    net, distributions = dict(amounts), []
    for group in sorted(groups, key=lambda g: (g["priority"], g["key"])):
        eligible = {key: amount for key, amount in net.items() if key in group["keys"]}
        total = sum(eligible.values())
        if total == 0:
            portions = {key: 0 for key in eligible}
        elif group["kind"] == "fixed":
            portions = allocate(min(total, group["amount"]), eligible)
        else:
            rates = [rational(p) / 100 for p in group["percentages"]]
            if group["mode"] == "additive":
                factor = max(Fraction(0), 1 - sum(rates))
            else:
                factor = Fraction(1)
                for rate in rates:
                    factor *= 1 - rate
            remaining = allocate(money(total * factor), eligible)
            portions = {key: eligible[key] - remaining[key] for key in eligible}
        for key, amount in portions.items():
            net[key] -= amount
        distributions.append(portions)
    return net, distributions


def allowance(contributions, units):
    remaining, used, billable = rational(units), {}, {}
    for key in sorted(contributions):
        quantity = rational(contributions[key])
        used[key] = min(remaining, quantity)
        billable[key] = quantity - used[key]
        remaining -= used[key]
    return used, billable


def grant_draws(amounts, grants):
    """Amounts key (service_date, bucket_tuple, consumer); inputs include eligible sets."""
    remaining = {g["key"]: g["face"] for g in grants}
    basis, draws, overage = {g["key"]: 0 for g in grants}, [], {}
    for key, amount in sorted(amounts.items()):
        when, _, consumer = key
        left = amount
        for g in sorted(grants, key=lambda x: (x["priority"], x["ends_before"], x["key"])):
            if not (g["starts_on"] <= when < g["ends_before"] and consumer in g["consumers"]):
                continue
            used = min(left, remaining[g["key"]])
            if used:
                remaining[g["key"]] -= used
                target = earned(g["basis"], g["face"] - remaining[g["key"]], g["face"])
                draws.append({"key": key, "grant": g["key"], "face": used,
                              "basis": target - basis[g["key"]]})
                basis[g["key"]] = target
                left -= used
        overage[key] = left
    return {"remaining": remaining, "earned": basis, "draws": draws, "overage": overage}


def replacement(price, recognized, billed, new_price, remaining_ssp):
    unearned = price - recognized
    if unearned + new_price < 0:
        raise ValueError("negative successor consideration")
    return {"allocation": allocate(unearned + new_price, remaining_ssp),
            "carry": unearned, "transfer": min(unearned, max(billed - recognized, 0))}


def modification_treatment(facts, new_ssp):
    if facts["new_services_only"] and facts["new_services_distinct"] and Fraction(facts["price_delta_minor"], 100) == sum(map(rational, new_ssp)):
        return "separate"
    if facts["remaining_distinct"] and not facts["changes_ongoing_progress"]:
        return "prospective"
    if facts["changes_ongoing_progress"]:
        return "cumulative"
    raise ValueError("unclassified modification")


def terminate(retained_price, billed, performed_ssp):
    if retained_price and not sum(map(rational, performed_ssp.values())):
        raise ValueError("fee promise required")
    allocations = allocate(retained_price, performed_ssp) if retained_price else {key: 0 for key in performed_ssp}
    return allocations, retained_price - billed


def billing_delta(consideration_delta, old_future, new_future):
    return consideration_delta - (new_future - old_future)


def minimum_residual(amount, overage):
    return max(0, amount - sum(overage))


def gross_overage(gross, net, overage):
    value = earned(gross, overage, net) if net else 0
    return value, value - overage


def peak(intervals, starts_at, ends_before):
    """Union seat identities, choose earliest peak; reject conflicting ownership."""
    instant = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    left, right = instant(starts_at), instant(ends_before)
    clipped = [(max(left, instant(a)), min(right, instant(b)), seat, owner)
               for a, b, seat, owner in intervals]
    clipped = [row for row in clipped if row[0] < row[1]]
    best, when = {}, None
    for point in sorted({row[0] for row in clipped}):
        present = {}
        for a, b, seat, owner in clipped:
            if a <= point < b:
                if seat in present and present[seat] != owner:
                    raise ValueError("conflicting seat ownership")
                present[seat] = owner
        if len(present) > len(best):
            best, when = present, point
    counts = {owner: list(best.values()).count(owner) for owner in set(best.values())}
    return when, counts
