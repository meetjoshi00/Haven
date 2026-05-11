def generate_windows(
    sg_min: float, sg_max: float, window_s: float, stride_s: float
) -> list[tuple[float, float]]:
    """Sliding window generator over [sg_min, sg_max]. Only full windows included."""
    windows: list[tuple[float, float]] = []
    t0 = sg_min
    while t0 + window_s <= sg_max:
        windows.append((t0, t0 + window_s))
        t0 += stride_s
    return windows
