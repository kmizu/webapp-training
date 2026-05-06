from datetime import date


def validate_due_on(due_on: date | None) -> tuple[bool, str | None]:
    """期限の業務ルール。極端な未来は受け付けない。"""
    if due_on is None:
        return True, None
    if (due_on - date.today()).days > 365 * 50:
        return False, "期限がだいぶ未来すぎます"
    return True, None
