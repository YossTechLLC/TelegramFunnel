from telegram import LabeledPrice

async def start_with_shipping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    title = "Sample Product"
    description = "This is a test invoice"
    payload = "CustomPayload"
    provider_token = PAYMENT_PROVIDER_TOKEN
    currency = "USD"

    # ✅ price must be an integer representing cents
    prices = [LabeledPrice(label="Sample Item", amount=100)]  # 1 USD

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token=provider_token,
        currency=currency,
        prices=prices,
        need_name=True,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False
    )
