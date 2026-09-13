"""Generate the dimension catalogues that member activity refers to.

These are produced up-front and held in memory: they are small, and every chunk of
members needs to draw from the same catalogue.

``courses`` is not in the table list in ``Data Recomendations.md``, but
``learning_activity.course_id`` implies it, and a star schema needs somewhere to put
course attributes.  It is generated here as a supporting dimension.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .utils import from_ordinal, pick, to_ordinal

EVENT_COLUMNS = [
    "event_id",
    "event_name",
    "event_category",
    "event_format",
    "event_date",
    "region",
    "capacity",
    "event_cost",
]

CAMPAIGN_COLUMNS = [
    "campaign_id",
    "campaign_name",
    "campaign_type",
    "start_date",
    "end_date",
    "target_segment",
    "channel",
    "campaign_cost",
]

COURSE_COLUMNS = [
    "course_id",
    "course_name",
    "course_category",
    "course_level",
    "expected_minutes",
    "cpd_hours",
    "launch_date",
]

_EVENT_TITLES = {
    "Webinar": ["{topic} in Practice", "Lunchtime Briefing: {topic}", "{topic} Update"],
    "Conference": ["Annual {topic} Conference", "National Congress on {topic}"],
    "Regional branch meeting": ["{region} Branch Meeting", "{region} Members' Evening"],
    "Technical workshop": ["Hands-on Workshop: {topic}", "Technical Clinic: {topic}"],
    "Networking": ["{region} Networking Breakfast", "Members' Networking Evening"],
    "Awards and celebration": ["Annual Awards Dinner", "Fellowship Admission Ceremony"],
    "Career development": ["Career Surgery: {topic}", "Mentoring Circle: {topic}"],
}

_EVENT_TOPICS = config.COURSE_TOPICS + [
    "Emerging Regulation",
    "AI and Automation",
    "Professional Standards",
    "Public Trust",
]

_CAMPAIGN_TITLES = {
    "Newsletter": "Member Update {month} {year}",
    "Event promotion": "{quarter} {year} Events Programme",
    "Renewal reminder": "{year} Renewal Reminder Wave {wave}",
    "Learning promotion": "CPD Spotlight {month} {year}",
    "Win-back": "We Miss You {month} {year}",
    "Member survey": "{year} Member Voice Survey",
    "Upgrade offer": "Chartered Pathway Offer {quarter} {year}",
}


def generate_events(rng: np.random.Generator, n_events: int) -> pd.DataFrame:
    start, end = to_ordinal(config.WINDOW_START), to_ordinal(config.AS_OF_DATE)

    category = pick(rng, config.EVENT_CATEGORIES, n_events)
    fmt = pick(rng, config.EVENT_FORMATS, n_events)
    # In-person formats are effectively impossible for the awards dinner to be online.
    fmt = np.where(category == "Awards and celebration", "In person", fmt)
    fmt = np.where(category == "Webinar", "Online", fmt)

    # Events cluster into the spring and autumn programme, away from August.
    day = np.empty(n_events, dtype=int)
    pool = np.arange(start, end + 1)
    doy = np.array([from_ordinal(int(d)).timetuple().tm_yday for d in pool], dtype=float)
    weight = 1.0 + 0.45 * np.sin(2 * np.pi * (doy - 55) / 365.25)
    weight -= 0.75 * np.exp(-(((doy - 225) / 20.0) ** 2))
    weight -= 0.85 * np.exp(-(((doy - 360) / 12.0) ** 2))
    weekday = np.array([from_ordinal(int(d)).weekday() for d in pool])
    weight *= np.where(weekday >= 5, 0.08, 1.0)
    weight = np.clip(weight, 0.01, None)
    day = rng.choice(pool, size=n_events, p=weight / weight.sum())

    region = pick(rng, config.REGIONS, n_events)
    region = np.where(fmt == "Online", "All regions", region)

    capacity = np.where(
        category == "Conference",
        rng.integers(350, 1400, n_events),
        np.where(
            fmt == "Online",
            rng.integers(200, 2500, n_events),
            rng.integers(25, 220, n_events),
        ),
    )

    cost = np.where(
        category == "Conference",
        rng.uniform(180, 640, n_events),
        np.where(
            category == "Webinar",
            np.where(rng.random(n_events) < 0.78, 0.0, rng.uniform(15, 45, n_events)),
            np.where(fmt == "Online", rng.uniform(0, 90, n_events), rng.uniform(20, 190, n_events)),
        ),
    )
    cost = np.round(cost, 2)

    names = []
    for i in range(n_events):
        template = rng.choice(_EVENT_TITLES[category[i]])
        names.append(
            template.format(topic=rng.choice(_EVENT_TOPICS), region=region[i].replace(" and ", " & "))
            + f" ({from_ordinal(int(day[i])).strftime('%b %Y')})"
        )

    return pd.DataFrame(
        {
            "event_id": [f"E{i:06d}" for i in range(1, n_events + 1)],
            "event_name": names,
            "event_category": category,
            "event_format": fmt,
            "event_date": [from_ordinal(int(d)).isoformat() for d in day],
            "event_ord": day,
            "region": region,
            "capacity": capacity,
            "event_cost": cost,
        }
    ).sort_values("event_ord", ignore_index=True)


def generate_campaigns(rng: np.random.Generator, n_campaigns: int) -> pd.DataFrame:
    start, end = to_ordinal(config.WINDOW_START), to_ordinal(config.AS_OF_DATE)
    ctype = pick(rng, config.CAMPAIGN_TYPES, n_campaigns)
    channel = pick(rng, config.CAMPAIGN_CHANNELS, n_campaigns)
    channel = np.where(ctype == "Newsletter", "Email", channel)

    start_ord = np.sort(rng.integers(start, end - 5, n_campaigns))
    duration = np.where(ctype == "Newsletter", 1, rng.integers(3, 28, n_campaigns))
    end_ord = np.minimum(start_ord + duration, end)

    segment = np.array(
        [
            {
                "Newsletter": "All members",
                "Renewal reminder": "Lapsing risk",
                "Win-back": "Lapsing risk",
                "Learning promotion": "Learning audience",
                "Upgrade offer": "Student and early career",
                "Member survey": "All members",
            }.get(t, rng.choice(config.TARGET_SEGMENTS))
            for t in ctype
        ],
        dtype=object,
    )

    cost = np.round(
        np.where(
            channel == "Direct mail",
            rng.uniform(4_000, 22_000, n_campaigns),
            np.where(channel == "SMS", rng.uniform(600, 3_500, n_campaigns), rng.uniform(150, 6_500, n_campaigns)),
        ),
        2,
    )

    names = []
    for i in range(n_campaigns):
        d = from_ordinal(int(start_ord[i]))
        names.append(
            _CAMPAIGN_TITLES[ctype[i]].format(
                month=d.strftime("%B"),
                year=d.year,
                quarter=f"Q{(d.month - 1) // 3 + 1}",
                wave=int(rng.integers(1, 4)),
            )
        )

    return pd.DataFrame(
        {
            "campaign_id": [f"C{i:05d}" for i in range(1, n_campaigns + 1)],
            "campaign_name": names,
            "campaign_type": ctype,
            "start_date": [from_ordinal(int(d)).isoformat() for d in start_ord],
            "end_date": [from_ordinal(int(d)).isoformat() for d in end_ord],
            "start_ord": start_ord,
            "target_segment": segment,
            "channel": channel,
            "campaign_cost": cost,
        }
    )


def generate_courses(rng: np.random.Generator, n_courses: int) -> pd.DataFrame:
    start, end = to_ordinal(config.WINDOW_START) - 400, to_ordinal(config.AS_OF_DATE) - 30
    topics = rng.choice(config.COURSE_TOPICS, size=n_courses)
    prefixes = rng.choice(config.COURSE_CATALOGUE_PREFIXES, size=n_courses)
    level = rng.choice(["Introductory", "Intermediate", "Advanced"], size=n_courses, p=[0.38, 0.42, 0.20])
    expected = np.where(
        level == "Introductory",
        rng.integers(25, 70, n_courses),
        np.where(level == "Intermediate", rng.integers(60, 160, n_courses), rng.integers(120, 420, n_courses)),
    )
    launch = rng.integers(start, end, n_courses)

    return pd.DataFrame(
        {
            "course_id": [f"L{i:05d}" for i in range(1, n_courses + 1)],
            "course_name": [f"{p} {t}" for p, t in zip(prefixes, topics)],
            "course_category": topics,
            "course_level": level,
            "expected_minutes": expected,
            "cpd_hours": np.round(expected / 60.0, 2),
            "launch_date": [from_ordinal(int(d)).isoformat() for d in launch],
            "launch_ord": launch,
        }
    )
