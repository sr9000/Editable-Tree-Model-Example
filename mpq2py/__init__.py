from decimal import Decimal

from gmpy2 import mpq


def mpq_serialization(q: mpq) -> float | Decimal:
    num = q.numerator
    den = q.denominator

    if den == 1:
        return Decimal(str(num) + ".0")

    twos = fives = 0
    while den % 2 == 0:
        den //= 2
        twos += 1
    while den % 5 == 0:
        den //= 5
        fives += 1

    if den != 1:
        return float(q)

    if twos > fives:
        num *= 5 ** (twos - fives)
    else:
        num *= 2 ** (fives - twos)

    tens = 0
    while num % 10 == 0:
        num //= 10
        tens += 1

    return Decimal(f"{num}.e{tens-max(twos, fives):+}")


def mpq_json_default(obj):
    if isinstance(obj, mpq):
        return mpq_serialization(obj)
    raise TypeError(f"Type {type(obj)} not serializable")
