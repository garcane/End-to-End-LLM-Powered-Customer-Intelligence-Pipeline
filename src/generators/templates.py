"""Free-text generation for member feedback and for placeholder AI insights.

Feedback text is assembled from a sentence bank that is conditioned on the feedback
category and the member's satisfaction, so that ``feedback_text`` genuinely agrees with
``rating`` and ``sentiment_label``.  That is what makes the table usable as a test set
for the LLM layer: summarisation and theme extraction can be checked against known
ground truth.

The ``ai_insights`` text produced here is an explicit placeholder.  In the running
pipeline these rows are overwritten by the real LLM layer; they exist so that the Power
BI model, the semantic layer and the report pages can be built before the LLM stage is
wired up.  ``validation_status`` is set to ``Template`` for every row generated here.
"""

from __future__ import annotations

import numpy as np

POSITIVE = {
    "Events and content": [
        "The webinar programme has been excellent this year and the speakers are genuinely practitioners rather than salespeople.",
        "I attended the regional branch meeting and found it far more useful than I expected. Good mix of technical content and networking.",
        "Recordings being available afterwards makes a real difference when I cannot attend live.",
    ],
    "Learning and development": [
        "The CPD modules are well structured and the assessments actually test understanding rather than recall.",
        "I completed two courses this quarter and both were directly applicable to my current role.",
        "Being able to export a CPD record straight into my appraisal documentation saves me hours.",
    ],
    "Membership value": [
        "My employer questioned the renewal cost this year and I was able to justify it easily on the CPD alone.",
        "Good value overall. The combination of events, learning and the technical library covers most of what I need.",
        "I have recommended membership to two colleagues in the last six months.",
    ],
    "Website and digital services": [
        "The site search has clearly been improved. I can now find guidance documents in a couple of clicks.",
        "The mobile app is quick and I use it far more than I expected to.",
        "Downloading standards is much easier than it used to be.",
    ],
    "Communications": [
        "The monthly newsletter is well edited and I read most of it, which is unusual for me.",
        "Communications are frequent enough to be useful without becoming noise.",
    ],
    "Customer service": [
        "The membership team resolved my query the same day and followed up to check I was happy.",
        "Helpful and responsive when I needed to change my payment details.",
    ],
    "Fees and billing": [
        "Spreading the fee over monthly payments made renewal straightforward this year.",
        "Billing was clear and the receipt arrived immediately, which my finance team appreciated.",
    ],
}

NEUTRAL = {
    "Events and content": [
        "The events are reasonable, although most of the in-person ones are a long way from where I live.",
        "I enjoy the webinars, but I have not been able to find many events relevant to my current role.",
        "Content quality varies. Some sessions are excellent and others feel like an hour of introductions.",
    ],
    "Learning and development": [
        "The courses are fine but there is not much at an advanced level for people who have been in the profession a while.",
        "I started a module but have not had time to finish it. The content itself seemed sound.",
    ],
    "Membership value": [
        "I am not certain I use enough of the benefits to justify the fee, but I intend to make more use of it next year.",
        "It is about what I would expect for the money. Nothing that stands out either way.",
    ],
    "Website and digital services": [
        "The website does what I need, though logging in on a second device is more awkward than it should be.",
        "Search results are hit and miss depending on the terminology I use.",
    ],
    "Communications": [
        "I receive a reasonable volume of email but much of it is not targeted to my sector.",
        "The updates are fine. I tend to skim rather than read them properly.",
    ],
    "Customer service": [
        "My query was answered eventually, although it took a few days and one follow-up.",
    ],
    "Fees and billing": [
        "The renewal process worked, but the fee increase was not explained anywhere I could find.",
    ],
}

NEGATIVE = {
    "Events and content": [
        "There has been nothing relevant to my specialism for over a year and the events that do run are always in London.",
        "I registered for two events that were then cancelled at short notice. That has put me off booking again.",
        "The last conference was disappointing for the price. Largely vendor presentations.",
    ],
    "Learning and development": [
        "The learning platform logged me out twice mid-assessment and I lost my progress both times.",
        "Course content has not been updated to reflect the new regulations, which makes it of limited use.",
    ],
    "Membership value": [
        "I cannot see what I get for the fee any more. I will not be renewing unless something changes.",
        "The fee went up again while the benefits stayed the same. That is difficult to justify to my employer.",
        "I have been a member for years and feel increasingly taken for granted.",
    ],
    "Website and digital services": [
        "The website is slow and the password reset process failed three times before it worked.",
        "I could not download the guidance I needed and the error message was meaningless.",
    ],
    "Communications": [
        "Far too many emails, none of which appear to take any account of what I actually do.",
        "I unsubscribed and still received two campaigns the following week.",
    ],
    "Customer service": [
        "It took three attempts and two weeks to get a straight answer about my membership grade.",
        "No one responded to my email at all. I had to telephone in the end.",
    ],
    "Fees and billing": [
        "My card was charged twice and it took a month to refund.",
        "The direct debit failed and the first I heard about it was a lapsed membership notice.",
    ],
}

_FOLLOW_UPS_NEGATIVE = [
    "I am seriously considering whether to renew.",
    "Please do not take this as a complaint for its own sake, but something needs to change.",
    "I would like someone to contact me about this.",
]

_FOLLOW_UPS_POSITIVE = [
    "Please pass my thanks on to the team.",
    "Keep doing this.",
]


def feedback_text(rng: np.random.Generator, category: str, rating: int) -> tuple[str, str]:
    """Return ``(text, sentiment_label)`` consistent with ``rating``."""
    if rating >= 4:
        bank, sentiment, follow = POSITIVE, "Positive", _FOLLOW_UPS_POSITIVE
    elif rating == 3:
        bank, sentiment, follow = NEUTRAL, "Neutral", []
    else:
        bank, sentiment, follow = NEGATIVE, "Negative", _FOLLOW_UPS_NEGATIVE

    options = bank.get(category) or NEUTRAL[category]
    text = str(rng.choice(options))
    if follow and rng.random() < 0.35:
        text = f"{text} {rng.choice(follow)}"
    return text, sentiment


# --------------------------------------------------------------------------------------
# Placeholder AI insight text
# --------------------------------------------------------------------------------------

_ACTIONS = {
    "No logins in the last 90 days": "Trigger a re-engagement email with a single, specific call to action and a personalised content recommendation.",
    "No event attendance in the last year": "Send a personalised invitation to the next event in the member's region and specialism.",
    "Failed renewal payment": "Contact the member to re-establish the payment mandate before the grace period expires.",
    "Negative feedback submitted in the last year": "Route to the membership support team for a personal follow-up call within 14 days.",
    "Login frequency down sharply on the previous quarter": "Include in the next lapsing-risk nurture wave and monitor weekly.",
    "Rarely opens member communications": "Reduce send frequency and switch to a sector-targeted content stream.",
    "Fee increase for a price-sensitive member": "Offer the monthly instalment plan and set out the year's benefits explicitly.",
    "Moving off the student rate to a full subscription": "Apply the graduate transition discount and offer a career-stage induction call.",
}

_DEFAULT_ACTION = "Add to the standard retention nurture programme and review at the next scoring run."


def insight_text(
    rng: np.random.Generator,
    *,
    member_id: str,
    probability: float,
    risk_level: str,
    factors: list[str],
    protective: list[str],
    features: dict,
) -> tuple[str, str, str]:
    """Return ``(executive_summary, risk_explanation, recommended_action)``."""
    primary = factors[0] if factors else "No dominant risk driver"

    summary = (
        f"Member {member_id} is scored {probability:.0%} likely to lapse at renewal "
        f"({risk_level.lower()} risk) after {features['tenure_years']:.1f} years of membership."
    )
    if risk_level == "Low":
        summary += " Engagement is consistent with a member who will renew without intervention."
    elif risk_level == "Medium":
        summary += " Engagement has softened and the renewal should not be treated as secure."
    else:
        summary += " Intervention is recommended before the renewal date."

    parts = []
    if features["logins_90d"] == 0:
        parts.append("the member has not logged in at all in the last 90 days")
    elif features["logins_prior_90d"] and features["logins_90d"] < features["logins_prior_90d"]:
        drop = 1 - features["logins_90d"] / max(features["logins_prior_90d"], 1)
        parts.append(f"logins are down {drop:.0%} on the previous quarter")
    if features["events_attended_365d"] == 0:
        parts.append("no events have been attended in the last twelve months")
    else:
        parts.append(f"{features['events_attended_365d']} events were attended in the last twelve months")
    if features["learning_completions_365d"]:
        parts.append(f"{features['learning_completions_365d']} learning courses were completed")
    if features["campaigns_sent_180d"] >= 4:
        parts.append(f"the campaign open rate over six months is {features['campaign_open_rate_180d']:.0%}")

    explanation = "Behaviourally, " + "; ".join(parts) + "."
    if protective:
        explanation += f" Offsetting this, {protective[0].lower()}."
    if factors:
        explanation += f" The strongest single risk driver is: {primary.lower()}."

    action = _ACTIONS.get(primary, _DEFAULT_ACTION)
    if risk_level == "High" and rng.random() < 0.4:
        action += " Escalate to the retention team if there is no response within 21 days."
    return summary, explanation, action
