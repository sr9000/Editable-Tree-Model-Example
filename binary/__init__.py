def format_hex_dump(data: bytes) -> str:
    """
    Formats a bytes object into a hex dump with custom spacing rules (4-8-16).

    Every 4 bytes joined with 2-spaces.
    Every 8 bytes joined with 4-spaces.
    Every 16 bytes starts a new line.

    Args:
        data: The bytes object to format.
    Returns:
        A string representing the formatted hex dump.
    """
    lines = []

    # Iterate over the data in chunks of bytes_per_line
    for i in range(0, len(data), 16):
        # Flatten the line_bytes into a list of hex strings
        h = data[i : i + 16].hex().ljust(32)

        # Build the formatted line using if-elif-else for 4 branches
        lines.append(
            " ".join(
                (
                    h[0:2],
                    h[2:4],
                    h[4:6],
                    h[6:8],
                    " ",
                    h[8:10],
                    h[10:12],
                    h[12:14],
                    h[14:16],
                    "   ",
                    h[16:18],
                    h[18:20],
                    h[20:22],
                    h[22:24],
                    " ",
                    h[24:26],
                    h[26:28],
                    h[28:30],
                    h[30:32],
                )
            )
        )

    return "\n".join(lines)
