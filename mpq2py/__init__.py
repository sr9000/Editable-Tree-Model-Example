from decimal import Decimal

import yaml
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
    v = mpq_serialization(data)
    if isinstance(v, Decimal):
        # Emit as a YAML float scalar so it round-trips back through our loader
        return dumper.represent_scalar("tag:yaml.org,2002:float", str(v))
    else:
        # Non-terminating decimal: fall back to binary float
        return dumper.represent_float(v)


MpqSafeDumper.add_representer(mpq, mpq_yaml_represent)
