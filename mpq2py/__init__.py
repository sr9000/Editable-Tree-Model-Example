from decimal import Decimal

import simplejson
import yaml
from gmpy2 import mpq
from pandas import Timestamp

from core.frozen_value import FrozenValue
from core.safe_mpq import safe_mpq_from_text
from core.datetime_parsing.nano_time import NanoTime
from units.number_affix import NumberAffix, format_number_affix

_YAML_SPECIAL_FLOAT_LITERALS = frozenset(
    {
        ".inf",
        "+.inf",
        "-.inf",
        ".nan",
        "inf",
        "+inf",
        "-inf",
        "infinity",
        "+infinity",
        "-infinity",
        "nan",
        "+nan",
        "-nan",
    }
)


def _is_yaml_special_float_literal(text: str) -> bool:
    return text.replace("_", "").strip().lower() in _YAML_SPECIAL_FLOAT_LITERALS


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
    if isinstance(obj, FrozenValue):
        return simplejson.RawJSON(obj.raw)
    if isinstance(obj, Decimal):
        # ``mpq_serialization`` returns ``Decimal`` for terminating fractions. The stdlib
        # ``json`` module re-invokes this default on the Decimal because it is not natively
        # JSON-serializable; fall back to ``float`` so clipboard / file paths that use
        # stdlib json (rather than simplejson, which handles Decimal natively) succeed.
        return float(obj)
    if isinstance(obj, NumberAffix):
        # NumberAffix values are serialized as their canonical string form
        # (e.g. ``"$1234"``, ``"12 kg"``) so they survive any JSON pipeline
        # (clipboard, drag MIME, file dump). On reload / paste, name-/value-
        # based classification re-promotes the string back to a NumberAffix.
        return format_number_affix(obj)
    if isinstance(obj, Timestamp):
        return obj.isoformat()
    if isinstance(obj, NanoTime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


class MpqSafeLoader(yaml.SafeLoader):
    pass


def mpq_yaml_float_construct(loader: MpqSafeLoader, node: yaml.ScalarNode):
    parsed = safe_mpq_from_text(node.value)
    if parsed is not None:
        return parsed

    if _is_yaml_special_float_literal(node.value):
        return yaml.constructor.SafeConstructor.construct_yaml_float(loader, node)

    return FrozenValue(raw=node.value.strip(), reason="yaml-float-overflow")


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


def _timestamp_yaml_represent(dumper: MpqSafeDumper, data: Timestamp):
    return dumper.represent_scalar("tag:yaml.org,2002:timestamp", data.isoformat())


MpqSafeDumper.add_representer(Timestamp, _timestamp_yaml_represent)


def _nanotime_yaml_represent(dumper: MpqSafeDumper, data: NanoTime):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data.isoformat())


MpqSafeDumper.add_representer(NanoTime, _nanotime_yaml_represent)


def _frozen_value_yaml_represent(dumper: MpqSafeDumper, data: FrozenValue):
    return dumper.represent_scalar("tag:yaml.org,2002:float", data.raw)


MpqSafeDumper.add_representer(FrozenValue, _frozen_value_yaml_represent)
