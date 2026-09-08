import random

import config

appreciationQuotes = [
    "A community stays safe because someone chose to speak up.",
    "Small actions, taken by someone who cares, are what keep a place worth being part of.",
    "Vigilance is a quiet kind of kindness.",
    "The safest spaces are built by people who refuse to look away.",
    "It takes one person paying attention to protect everyone else.",
]


def welcomeText():
    return (
        f"<b>{config.botName}</b>\n\n"
        "This is the reporting line for our channel. If you've come across a post that "
        "shouldn't be here, send the message link and we'll walk through it together.\n\n"
        "Just paste the link whenever you're ready."
    )


def notAMemberText():
    return (
        "This link doesn't look like it's from our channel, or we couldn't verify you're a "
        "member there. Please make sure you're sending a link copied directly from the channel."
    )


def invalidLinkText():
    return (
        "That didn't look like a valid channel message link. Try copying it again using "
        "Telegram's \"Copy Message Link\" option."
    )


def askReasonText():
    return "Thanks for bringing this forward. What's the concern with this post?"


reasonLabels = {
    "illegal": "Illegal content",
    "maybeIllegal": "Possibly illegal, not sure",
    "disturbing": "Disturbing content",
    "other": "Something else",
}


def confirmReportText(reasonLabel: str):
    return (
        f"Got it — flagged as: <b>{reasonLabel}</b>.\n\n"
        "Do you want to go ahead and send this to the team for review?"
    )


def reportSubmittedText(ticketId: int):
    return (
        f"Report #{ticketId} has been sent to the team.\n\n"
        "Thank you for taking the time to flag this — we'll take it from here."
    )


def reportCancelledText():
    return "No problem, that report has been cancelled. Nothing was sent."


def duplicateReportAddedText(ticketId: int):
    return (
        f"This post had already been reported by someone else — we've added your report to "
        f"ticket #{ticketId} as well. Appreciate you flagging it too."
    )


def falseReportResolvedDmText():
    return (
        "Thanks for flagging that one. Our team has checked it and it's fine — no action needed. "
        "We'd rather double check every report than miss something real, so thank you for looking out."
    )


def alreadyRemovedPingText(ticketId: int, reportersLine: str):
    return (
        f"Ticket #{ticketId} — heads up, this content was already removed before the ticket "
        f"was reviewed (likely removed manually).\n\n"
        f"Reported by: {reportersLine}\n\n"
        "Marking this as resolved. No further action needed, but flagging so you have full visibility."
    )


def ownerNewTicketText(ticketId: int, reasonLabel: str, username: str, userId: int, firstName: str):
    handle = f"@{username}" if username else "(no username)"
    return (
        f"<b>New report — Ticket #{ticketId}</b>\n\n"
        f"Reason: {reasonLabel}\n"
        f"Reported by: {handle}\n"
        f"Name: {firstName}\n"
        f"User ID: {userId}\n\n"
        "Review the content below and decide how to proceed."
    )


def ownerRemoveWarningText(ticketId: int):
    return (
        f"You're about to remove the content for Ticket #{ticketId}.\n\n"
        "This cannot be undone. Please confirm this wasn't an accidental tap."
    )


def ownerRemoveFinalConfirmText(ticketId: int):
    return f"Final check — remove this content permanently for Ticket #{ticketId}?"


def ownerPermissionDeniedText():
    return "You don't have permission to do this."


def ownerNoActiveTicketText():
    return "This ticket is no longer active or was already handled."


def channelRemovalBroadcast(reportersRanked: list):
    lines = []
    for i, r in enumerate(reportersRanked, start=1):
        handle = f"@{r['username']}" if r["username"] else r["firstName"]
        lines.append(f"{i}. {handle}")
    reporterList = "\n".join(lines)
    quote = random.choice(appreciationQuotes)

    return (
        "<b>Content removed</b>\n\n"
        "We were notified that a post here violated our channel guidelines. After review, "
        "our team confirmed it and the content has been removed.\n\n"
        f"Reported by:\n{reporterList}\n\n"
        f"<i>{quote}</i>\n\n"
        "We can't keep this channel safe without members choosing to speak up. Thank you."
    )


def reporterThankYouDm(ticketId: int):
    quote = random.choice(appreciationQuotes)
    return (
        "Thank you for helping us maintain the legality and safety of our channel.\n\n"
        "We could not have caught this without your report. It genuinely makes a difference.\n\n"
        f"<i>{quote}</i>"
    )