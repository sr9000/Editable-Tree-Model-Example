def bits(n: int) -> str:
    units = ("byte", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")

    if n < 1000:
        return f"{n} byte"

    for p, u in enumerate(units, start=1):
        if n < 1024**p:
            divisor = 1024 ** (p - 1)
            if (value := n / divisor) < 10:
                return f"{value:.2f} {u}"
            elif value < 100:
                return f"{value:.1f} {u}"
            elif value < 999:
                return f"{int(value)} {u}"

    return "∞ byte"


def format_bytes(n: int) -> str:
    return bits(n)


def counts(n: int) -> str:
    units = ("", "K", "M", "B")

    if n < 1000:
        return str(n)

    for p, u in enumerate(units, start=1):
        if n < 1000**p:
            divisor = 1000 ** (p - 1)
            if (value := n / divisor) < 10:
                return f"{value:.2f}{u}"
            elif value < 100:
                return f"{value:.1f}{u}"
            elif value < 999:
                return f"{int(value)}{u}"

    return "∞"
