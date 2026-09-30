# Jeebour Gold Signal Bot v1

Signal-only Telegram bot for XAUUSD. It does NOT place trades.

## What it does
- Polls a configurable XAUUSD market-data API.
- Calculates EMA trend, RSI, ATR and breakout/structure-style conditions.
- Sends BUY/SELL alerts to Telegram only when the score threshold is met.
- Includes Entry, SL, TP1, TP2 and risk information.
- Designed around a $1,000 account and $5 maximum risk per trade.

## Important
This is a starter system, not a guaranteed-profit strategy. Test on demo/backtest before risking money.

## Required environment variables
TELEGRAM_BOT_TOKEN=your_BotFather_token
TELEGRAM_CHAT_ID=your_chat_or_user_id
TWELVE_DATA_API_KEY=your_Twelve_Data_key

Optional:
SYMBOL=XAU/USD
RISK_USD=5
MIN_SCORE=4
POLL_SECONDS=60
ATR_SL_MULT=1.5
RR1=1.5
RR2=2.5

## Run
pip install -r requirements.txt
python bot.py

## Telegram
Open your bot and press /start. To get a private chat id, the bot can answer /chatid after it is running.

## Cloud
Put these files on a Python-capable cloud host and add the environment variables there. Never publish your Telegram bot token.
