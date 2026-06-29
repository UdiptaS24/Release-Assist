from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from calendar import monthrange
try:
    import holidays
    PUBLIC_HOLIDAYS = holidays.India()
except Exception:
    PUBLIC_HOLIDAYS = {}

try:
    BUSINESS_TIMEZONE = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    BUSINESS_TIMEZONE = None
BUSINESS_START = time(10, 0)
BUSINESS_END = time(18, 0)
DEFAULT_DEPLOYMENT_DURATION_MINUTES = 60

MONTH_END_FREEZE_DAYS = 3

YEAR_END_FREEZE_START = (12, 24)
YEAR_END_FREEZE_END = (1, 2)



def to_business_timezone(dt: datetime) -> datetime:
    if not BUSINESS_TIMEZONE:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=BUSINESS_TIMEZONE)
    return dt.astimezone(BUSINESS_TIMEZONE)


def is_weekend(dt: datetime) -> bool:
    return dt.weekday() >= 5


def is_month_end_freeze(dt: datetime, days_before_month_end: int = MONTH_END_FREEZE_DAYS) -> bool:
    try:
        last_day = monthrange(dt.year, dt.month)[1]
        freeze_start_day = last_day - days_before_month_end + 1
        return dt.day >= freeze_start_day
    except Exception:
        return False


def is_year_end_freeze(dt: datetime) -> bool:
    month_day = (dt.month, dt.day)
    start = YEAR_END_FREEZE_START
    end = YEAR_END_FREEZE_END
    return month_day >= start or month_day <= end


def is_public_holiday(dt: datetime) -> bool:
    try:
        return dt.date() in PUBLIC_HOLIDAYS
    except Exception:
        return False


def get_public_holiday_name(dt: datetime) -> str:
    try:
        return PUBLIC_HOLIDAYS.get(dt.date()) or "Public holiday"
    except Exception:
        return "Public holiday"



def _parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None
    return None


def check_blackout_conflicts(start: datetime, end: datetime) -> list[dict]:
    start = to_business_timezone(start)
    end = to_business_timezone(end)
    conflicts = []

    if is_weekend(start) or is_weekend(end):
        conflicts.append({
            "type": "WEEKEND",
            "name": "Weekend",
            "reason": "Weekends are not allowed for deployments."
        })

    if is_month_end_freeze(start) or is_month_end_freeze(end):
        conflicts.append({
            "type": "MONTH_END_FREEZE",
            "name": "Month-end freeze",
            "reason": f"Last {MONTH_END_FREEZE_DAYS} days of every month are reserved for finance close-out."
        })
    
    if is_year_end_freeze(start) or is_year_end_freeze(end):
        conflicts.append({
            "type": "YEAR_END_FREEZE",
            "name": "Year-end freeze",
            "reason": "Year-end freeze period (Dec 24 - Jan 2). No deployments allowed."
        })

    for dt in (start, end):
        if is_public_holiday(dt):
            conflicts.append({
                "type": "PUBLIC_HOLIDAY",
                "name": get_public_holiday_name(dt),
                "reason": "Public holiday - deployments not allowed."
            })
            break

    return conflicts


def normalize_to_business_window(candidate: datetime) -> datetime:
    candidate = to_business_timezone(candidate)

    if candidate.time() < BUSINESS_START:
        return candidate.replace(
            hour=BUSINESS_START.hour,
            minute=BUSINESS_START.minute,
            second=0,
            microsecond=0
        )

    if candidate.time() >= BUSINESS_END:
        next_day = candidate + timedelta(days=1)
        return next_day.replace(
            hour=BUSINESS_START.hour,
            minute=BUSINESS_START.minute,
            second=0,
            microsecond=0
        )

    return candidate


def suggest_next_available_slot(
    requested_start: datetime,
    duration_minutes: int = DEFAULT_DEPLOYMENT_DURATION_MINUTES
) -> tuple[datetime, datetime]:

    candidate_start = normalize_to_business_window(requested_start + timedelta(days=1))

    safety_counter = 0
    while True:
        safety_counter += 1
        if safety_counter > 60:
            break
        candidate_start = normalize_to_business_window(candidate_start)
        candidate_end = candidate_start + timedelta(minutes=duration_minutes)

        if not check_blackout_conflicts(candidate_start, candidate_end):
            return candidate_start, candidate_end

        candidate_start = candidate_start + timedelta(days=1)
    
    return candidate_start, candidate_start + timedelta(minutes=duration_minutes)


def _blocked(reason: str, conflict_type: str, start: datetime, end: datetime, contacts: list[str]) -> dict:
    return {
        "status": "BLOCKED",
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "scheduled_start": None,
        "scheduled_end": None,
        "reason": reason,
        "conflicts": [
            {
                "type": conflict_type,
                "reason": reason
            }
        ],
        "notified_contacts": contacts
    }


def run_scheduler(release_record: dict) -> dict:

    requested_start = _parse_datetime(release_record["requested_start"])
    requested_end = _parse_datetime(release_record["requested_end"])
    notify_contacts = release_record["notify_contacts"] or []
    release_status = release_record.get("status")
    
    if not requested_start or not requested_end:
        return _blocked(
            "Invalid or missing requested deployment dates.",
            "INVALID_REQUEST",
            requested_start,
            requested_end,
            notify_contacts
        )
    
    if requested_end <= requested_start:
        return _blocked(
            "Deployment end time must be after start time.",
            "INVALID_TIME_RANGE",
            requested_start,
            requested_end,
            notify_contacts
        )

    if release_status == "BLOCKED":
        return _blocked(
            "Release is BLOCKED by gate logic and cannot be scheduled.",
            "GATE_BLOCK",
            requested_start,
            requested_end,
            notify_contacts
        )

    if release_status == "NEEDS_REVIEW":
        return _blocked(
            "Release requires manual review before scheduling.",
            "MANUAL_REVIEW_REQUIRED",
            requested_start,
            requested_end,
            notify_contacts
        )

    if release_status != "APPROVED":
        return _blocked(
            f"Release status '{release_status}' is not eligible for scheduling.",
            "NOT_APPROVED",
            requested_start,
            requested_end,
            notify_contacts
        )

    conflicts = check_blackout_conflicts(requested_start, requested_end)

    if conflicts:
        duration_minutes = int((requested_end - requested_start).total_seconds() // 60)
        alt_start, alt_end = suggest_next_available_slot(requested_start, duration_minutes)

        return {
            "status": "SUGGESTED_ALTERNATE",
            "requested_start": requested_start.isoformat(),
            "requested_end": requested_end.isoformat(),
            "scheduled_start": alt_start.isoformat(),
            "scheduled_end": alt_end.isoformat(),
            "reason": "Requested deployment window conflicts with deployment calendar.",
            "conflicts": conflicts,
            "notified_contacts": notify_contacts
        }

    return {
        "status": "SCHEDULED",
        "requested_start": requested_start.isoformat(),
        "requested_end": requested_end.isoformat(),
        "scheduled_start": requested_start.isoformat(),
        "scheduled_end": requested_end.isoformat(),
        "reason": "Deployment window accepted.",
        "conflicts": [],
        "notified_contacts": notify_contacts
    }