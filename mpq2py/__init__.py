from decimal import Decimal

import yaml
from gmpy2 import mpq


def mpq_serialization(q: mpq) -> tuple[float | Decimal, mpq]:
    num, den = q.as_integer_ratio()

    if num == 0:
        return Decimal("0.0"), mpq(1, 10)  # zero value

    if den == 1:
        least_magnitude = 0
        while num % 10 == 0:
            num //= 10
            least_magnitude += 1

        if least_magnitude < 4 or least_magnitude == 4 and num < 10:
            return Decimal(f"{num}{"0"*least_magnitude}.0"), mpq(10**least_magnitude)  # small value

        return Decimal(f"{num}.0e{least_magnitude}"), mpq(10**least_magnitude)  # big value

    twos = fives = 0
    while den % 2 == 0:
        den //= 2
        twos += 1
    while den % 5 == 0:
        den //= 5
        fives += 1

    if den != 1:
        return float(q), q / 10  # non-terminating decimal

    if twos > fives:
        num *= 5 ** (twos - fives)
    else:
        num *= 2 ** (fives - twos)

    tens = 0
    while num % 10 == 0:
        num //= 10
        tens += 1

    least_magnitude = tens - max(twos, fives)

    # if least_magnitude > -4:
    #     s = f"{"0"*abs(least_magnitude)}{num}"
    #     s = s[:least_magnitude] + "." + s[least_magnitude:]
    #     return Decimal(s), mpq(1, 10**-least_magnitude)

    return Decimal(f"{num}.e{least_magnitude :+}"), mpq(1, 10**-least_magnitude)


def mpq_json_default(obj):
    if isinstance(obj, mpq):
        # Emit only the scalar value; the helper's denominator metadata is not JSON-serializable.
        return mpq_serialization(obj)[0]
    raise TypeError(f"Type {type(obj)} not serializable")


class MpqSafeLoader(yaml.SafeLoader):
    pass


def mpq_yaml_float_construct(loader: MpqSafeLoader, node: yaml.ScalarNode):
    try:
        return mpq(node.value.replace("_", "").lower().strip())
    except Exception:
        # If mpq can't parse some odd form, fall back to default behavior
        return yaml.constructor.SafeConstructor.construct_yaml_float(loader, node)


MpqSafeLoader.add_constructor("tag:yaml.org,2002:float", mpq_yaml_float_construct)


class MpqSafeDumper(yaml.SafeDumper):
    pass


def mpq_yaml_represent(dumper: MpqSafeDumper, data: mpq):
    v = mpq_serialization(data)[0]
    if isinstance(v, Decimal):
        # Emit as a YAML float scalar so it round-trips back through our loader
        return dumper.represent_scalar("tag:yaml.org,2002:float", str(v))
    else:
        # Non-terminating decimal: fall back to binary float
        return dumper.represent_float(v)


MpqSafeDumper.add_representer(mpq, mpq_yaml_represent)
