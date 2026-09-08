import logging
import re
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError

import config
import db
import texts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vaultguard")

awaitReason, awaitConfirm = range(2)

linkRe = re.compile(r"t\.me/(c/)?([A-Za-z0-9_]+)/(\d+)")


def ownerOnly(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id != config.ownerId:
            if update.callback_query:
                await update.callback_query.answer(texts.ownerPermissionDeniedText(), show_alert=True)
            elif update.message:
                await update.message.reply_text(texts.ownerPermissionDeniedText())
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def parseChannelLink(text: str):
    m = linkRe.search(text)
    if not m:
        return None
    isInternal, ref, msgId = m.groups()
    if isInternal:
        chatId = int(f"-100{ref}")
        return chatId, int(msgId)
    else:
        return f"@{ref}", int(msgId)


async def userIsChannelMember(context: ContextTypes.DEFAULT_TYPE, userId: int) -> bool:
    try:
        member = await context.bot.get_chat_member(config.channelId, userId)
        return member.status not in ("left", "kicked")
    except TelegramError:
        return False


def reasonKeyboard(msgId: int):
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"reason:{msgId}:{code}")]
        for code, label in texts.reasonLabels.items()
    ]
    return InlineKeyboardMarkup(buttons)


def confirmKeyboard(msgId: int, reasonCode: str):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Yes, report it", callback_data=f"submit:{msgId}:{reasonCode}"),
        InlineKeyboardButton("Cancel", callback_data="cancelReport"),
    ]])


def ownerTicketKeyboard(ticketId: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Mark Valid", callback_data=f"valid:{ticketId}"),
        InlineKeyboardButton("Mark False Report", callback_data=f"false:{ticketId}"),
    ]])


def removeWarningKeyboard(ticketId: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Cancel", callback_data=f"rmCancel:{ticketId}"),
        InlineKeyboardButton("Confirm Remove", callback_data=f"rmConfirm:{ticketId}"),
    ]])


def removeFinalKeyboard(ticketId: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("No, go back", callback_data=f"rmCancel:{ticketId}"),
        InlineKeyboardButton("Yes, delete now", callback_data=f"rmFinal:{ticketId}"),
    ]])


def reportersLine(reporters: list) -> str:
    parts = []
    for r in reporters:
        parts.append(f"@{r['username']}" if r["username"] else r["firstName"])
    return ", ".join(parts)


async def startCmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(texts.welcomeText(), parse_mode=ParseMode.HTML)


async def handleLinkMessage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    parsed = parseChannelLink(text)
    if not parsed:
        await update.message.reply_text(texts.invalidLinkText())
        return ConversationHandler.END

    chatRef, msgId = parsed
    user = update.effective_user

    if not await userIsChannelMember(context, user.id):
        await update.message.reply_text(texts.notAMemberText())
        return ConversationHandler.END

    context.user_data["reportMsgId"] = msgId
    await update.message.reply_text(texts.askReasonText(), reply_markup=reasonKeyboard(msgId))
    return awaitReason


async def reasonSelected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, msgIdStr, reasonCode = query.data.split(":")
    msgId = int(msgIdStr)
    label = texts.reasonLabels.get(reasonCode, "Other")
    context.user_data["reportReasonCode"] = reasonCode
    await query.edit_message_text(
        texts.confirmReportText(label),
        reply_markup=confirmKeyboard(msgId, reasonCode),
    )
    return awaitConfirm


async def reportConfirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, msgIdStr, reasonCode = query.data.split(":")
    msgId = int(msgIdStr)
    label = texts.reasonLabels.get(reasonCode, "Other")
    user = update.effective_user

    existing = db.findOpenTicketForMessage(msgId)
    if existing:
        added = db.addReporter(existing["id"], user.id, user.username, user.first_name)
        await query.edit_message_text(texts.duplicateReportAddedText(existing["id"]))
        if added:
            await notifyOwnerNewReporter(context, existing["id"])
        return ConversationHandler.END

    ticketId = db.createTicket(msgId, label)
    db.addReporter(ticketId, user.id, user.username, user.first_name)
    await query.edit_message_text(texts.reportSubmittedText(ticketId))
    await notifyOwnerNewTicket(context, ticketId, msgId, label, user)
    return ConversationHandler.END


async def reportCancelled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(texts.reportCancelledText())
    return ConversationHandler.END


async def notifyOwnerNewTicket(context, ticketId, msgId, reasonLabel, user):
    text = texts.ownerNewTicketText(ticketId, reasonLabel, user.username, user.id, user.first_name)
    try:
        await context.bot.copy_message(
            chat_id=config.ownerId,
            from_chat_id=config.channelId,
            message_id=msgId,
        )
    except TelegramError as e:
        logger.warning(f"could not copy source message for ticket {ticketId}: {e}")
    await context.bot.send_message(
        chat_id=config.ownerId,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=ownerTicketKeyboard(ticketId),
    )


async def notifyOwnerNewReporter(context, ticketId):
    ticket = db.getTicket(ticketId)
    reporters = db.getReporters(ticketId)
    await context.bot.send_message(
        chat_id=config.ownerId,
        text=(
            f"Ticket #{ticketId} received another report ({len(reporters)} total). "
            f"Reported by: {reportersLine(reporters)}"
        ),
    )


@ownerOnly
async def markValid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticketId = int(query.data.split(":")[1])
    ticket = db.getTicket(ticketId)
    if not ticket or ticket["status"] != "NEW":
        await query.edit_message_text(texts.ownerNoActiveTicketText())
        return
    await query.edit_message_text(
        texts.ownerRemoveWarningText(ticketId),
        reply_markup=removeWarningKeyboard(ticketId),
    )


@ownerOnly
async def markFalse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticketId = int(query.data.split(":")[1])
    ticket = db.getTicket(ticketId)
    if not ticket or ticket["status"] != "NEW":
        await query.edit_message_text(texts.ownerNoActiveTicketText())
        return
    db.setTicketStatus(ticketId, "FALSE", resolved=True)
    reporters = db.getReporters(ticketId)
    for r in reporters:
        try:
            await context.bot.send_message(chat_id=r["userId"], text=texts.falseReportResolvedDmText())
        except TelegramError:
            pass
    await query.edit_message_text(query.message.text_html + "\n\nMarked as false report — closed.",
                                   parse_mode=ParseMode.HTML)


@ownerOnly
async def removeCancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(query.message.text_html + "\n\nRemoval cancelled.",
                                   parse_mode=ParseMode.HTML)


@ownerOnly
async def removeWarnConfirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticketId = int(query.data.split(":")[1])
    ticket = db.getTicket(ticketId)
    if not ticket or ticket["status"] not in ("NEW",):
        await query.edit_message_text(texts.ownerNoActiveTicketText())
        return
    await query.edit_message_text(
        texts.ownerRemoveFinalConfirmText(ticketId),
        reply_markup=removeFinalKeyboard(ticketId),
    )


@ownerOnly
async def removeFinal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ticketId = int(query.data.split(":")[1])
    ticket = db.getTicket(ticketId)
    if not ticket:
        await query.edit_message_text(texts.ownerNoActiveTicketText())
        return

    reporters = db.getReporters(ticketId)

    try:
        await context.bot.delete_message(chat_id=config.channelId, message_id=ticket["channelMsgId"])
        db.setTicketStatus(ticketId, "REMOVED", resolved=True)
        await query.edit_message_text(f"Ticket #{ticketId} — content removed. Broadcasting now.")

        await context.bot.send_message(
            chat_id=config.channelId,
            text=texts.channelRemovalBroadcast(reporters),
            parse_mode=ParseMode.HTML,
        )
        for r in reporters:
            try:
                await context.bot.send_message(
                    chat_id=r["userId"],
                    text=texts.reporterThankYouDm(ticketId),
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass

    except TelegramError as e:
        logger.info(f"delete_message failed for ticket {ticketId}: {e}")
        db.setTicketStatus(ticketId, "ALREADY_REMOVED", resolved=True)
        await query.edit_message_text(
            texts.alreadyRemovedPingText(ticketId, reportersLine(reporters))
        )


def buildApp():
    db.initDb()
    application = Application.builder().token(config.botToken).build()

    reportConv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.Regex(linkRe) & filters.ChatType.PRIVATE,
                                      handleLinkMessage)],
        states={
            awaitReason: [CallbackQueryHandler(reasonSelected, pattern=r"^reason:")],
            awaitConfirm: [
                CallbackQueryHandler(reportConfirmed, pattern=r"^submit:"),
                CallbackQueryHandler(reportCancelled, pattern=r"^cancelReport$"),
            ],
        },
        fallbacks=[CallbackQueryHandler(reportCancelled, pattern=r"^cancelReport$")],
    )

    application.add_handler(CommandHandler("start", startCmd))
    application.add_handler(reportConv)
    application.add_handler(CallbackQueryHandler(markValid, pattern=r"^valid:"))
    application.add_handler(CallbackQueryHandler(markFalse, pattern=r"^false:"))
    application.add_handler(CallbackQueryHandler(removeWarnConfirm, pattern=r"^rmConfirm:"))
    application.add_handler(CallbackQueryHandler(removeCancel, pattern=r"^rmCancel:"))
    application.add_handler(CallbackQueryHandler(removeFinal, pattern=r"^rmFinal:"))

    return application


def main():
    application = buildApp()
    if config.webhookUrl:
        application.run_webhook(
            listen="0.0.0.0",
            port=config.port,
            url_path=config.webhookPath.lstrip("/"),
            webhook_url=f"{config.webhookUrl}{config.webhookPath}",
        )
    else:
        application.run_polling()


if __name__ == "__main__":
    main()