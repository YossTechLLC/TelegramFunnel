# main.py
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ShippingQueryHandler, PreCheckoutQueryHandler, ConversationHandler
from fetch import fetch_telegram_token, fetch_payment_provider_token
from echo import script1_start, script1_help, script1_echo
from webapp import script2_start_crypto, script2_web_app_data, update_invoice_url, dynamic_invoice_url
from payment import (
    script3_start_payment, script3_start_with_shipping_callback, script3_start_without_shipping_callback,
    script3_shipping_callback, script3_precheckout_callback, script3_successful_payment_callback,
    newpayment_handler
)
from database import database_handler


def main():
    telegram_token = fetch_telegram_token()
    payment_provider_token = fetch_payment_provider_token()

    if not telegram_token:
        raise RuntimeError("Bot cannot start: TELEGRAM_BOT_SECRET_NAME is missing or invalid.")
    if not payment_provider_token:
        raise RuntimeError("Bot cannot start: PAYMENT_PROVIDER_SECRET_NAME is missing or invalid.")

    application = Application.builder().token(telegram_token).build()
    application.bot_data["PAYMENT_PROVIDER_TOKEN"] = payment_provider_token

    # Database
    application.add_handler(database_handler)

    # Echo
    application.add_handler(CommandHandler("start", script1_start))
    application.add_handler(CommandHandler("help", script1_help))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, script1_echo))

    # WebApp
    application.add_handler(CommandHandler("start_crypto", script2_start_crypto))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, script2_web_app_data))

    # Payments
    application.add_handler(CommandHandler("start_payment", script3_start_payment))
    application.add_handler(CommandHandler("shipping", script3_start_with_shipping_callback))
    application.add_handler(CommandHandler("noshipping", script3_start_without_shipping_callback))
    application.add_handler(ShippingQueryHandler(script3_shipping_callback))
    application.add_handler(PreCheckoutQueryHandler(script3_precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, script3_successful_payment_callback))
    application.add_handler(newpayment_handler)

    application.post_init(update_invoice_url)
    application.run_polling(allowed_updates=None)


if __name__ == "__main__":
    main()
