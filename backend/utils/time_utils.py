def format_seconds_to_srt_time(seconds: float) -> str:
    """Format rounded milliseconds as subtitle timestamps, including hour boundaries."""

    total_milliseconds = int(round(seconds * 1000))

    hours, remaining_ms = divmod(total_milliseconds, 3_600_000)
    minutes, remaining_ms = divmod(remaining_ms, 60_000)
    seconds, milliseconds = divmod(remaining_ms, 1_000)

    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"
