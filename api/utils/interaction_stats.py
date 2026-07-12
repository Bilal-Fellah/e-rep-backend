# Shared helper functions for interaction stats.

def interpolate_series(values):
    """
    values: list of numbers (0 or None = missing)
    returns: list with gaps filled
    """
    n = len(values)
    result = values[:]

    for i in range(n):
        if i == 0:
            continue  # first row stays as-is

        if result[i] is None or result[i] == 0:
            # find previous non-zero
            prev = None
            for j in range(i - 1, -1, -1):
                if result[j] not in (0, None):
                    prev = result[j]
                    break

            # find next non-zero
            nxt = None
            for j in range(i + 1, n):
                if values[j] not in (0, None):
                    nxt = values[j]
                    break

            if prev is not None and nxt is not None:
                result[i] = (prev + nxt) / 2
            elif prev is not None:
                result[i] = prev
            elif nxt is not None:
                result[i] = nxt
            else:
                result[i] = 0

    return result
