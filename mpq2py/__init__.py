import re
from decimal import Decimal

import simplejson
import yaml
from gmpy2 import mpq
from pandas import Timestamp

from core.raw_numeric import REASON_UNKNOWN, RawNumericValue
from core.safe_mpq import parse_mpq
from core.datetime_parsing.nano_time import NanoTime
from units.number_affix import NumberAffix, format_number_affix

# Strict JSON number grammar. A raw numeric value may only be injected directly
# into JSON output when its literal is a valid JSON number; otherwise saving as
# JSON must fail loudly rather than emit invalid JSON or silently quote it.
_JSON_NUMBER_TOKEN_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?\Z")


def raw_numeric_is_json_safe(raw: str) -> bool:
    return bool(_JSON_NUMBER_TOKEN_RE.match(raw.strip()))


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
    if isinstance(obj, RawNumericValue):
        if raw_numeric_is_json_safe(obj.raw):
            return simplejson.RawJSON(obj.raw.strip())
        raise ValueError(
            f"Raw numeric value {obj.raw!r} (reason: {obj.reason}) is not a valid "
            "JSON number; convert it to a supported number or save as YAML."
        )
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
    result = parse_mpq(node.value)
    if result.value is not None:
        return result.value

    # Preserve the original literal exactly (including non-finite spellings such
    # as ``.inf`` / ``.nan``) as editable raw text instead of constructing a
    # Python float, so rendering and validation never depend on float quirks.
    return RawNumericValue(raw=node.value, reason=result.reason or REASON_UNKNOWN, source_syntax="yaml")


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


def _raw_numeric_yaml_represent(dumper: MpqSafeDumper, data: RawNumericValue):
    return dumper.represent_scalar("tag:yaml.org,2002:float", data.raw)


MpqSafeDumper.add_representer(RawNumericValue, _raw_numeric_yaml_represent)
