import simplejson as json
import yaml
from gmpy2 import mpq

from core.raw_numeric import REASON_NON_FINITE, RawNumericValue

from mpq2py import MpqSafeDumper, MpqSafeLoader, mpq_json_default

json_floats = """
{
  "finite1": 987654345678.9876543567890009099087,
  "finite2": 6.54345678976543567E-83,
  "root of 2": 1.414213562373095E-20,
  "pi": 3.142857142857143,
  "negative": -0.05,
  "one third": 0.3333333333333333,
  "integer": 123.0
}
""".strip()

yaml_floats = """
finite1: 987654345678.9876543567890009099087
finite2: 6.54345678976543567E-83
root of 2: 1.414213562373095E-20
pi: 3.142857142857143
negative: -0.05
one third: 0.3333333333333333
integer: 123.0
""".lstrip()


def test_mpq_with_json():
    data = json.loads(json_floats, parse_float=mpq)
    res = json.dumps(data, default=mpq_json_default, indent=2)

    assert res == json_floats


def test_mpq_with_yaml():
    data = yaml.load(yaml_floats, Loader=MpqSafeLoader)
    res = yaml.dump(data, Dumper=MpqSafeDumper, sort_keys=False)

    assert res == yaml_floats


def test_yaml_special_floats_become_raw_numeric_values() -> None:
    data = yaml.load("pinf: .inf\nninf: -.inf\nnanv: .nan\n", Loader=MpqSafeLoader)

    for key in ("pinf", "ninf", "nanv"):
        assert isinstance(data[key], RawNumericValue)
        assert data[key].reason == REASON_NON_FINITE

    # The original literal is preserved exactly.
    assert data["pinf"].raw == ".inf"
    assert data["ninf"].raw == "-.inf"
    assert data["nanv"].raw == ".nan"
