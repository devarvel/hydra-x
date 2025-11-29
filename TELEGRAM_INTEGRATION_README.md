# Telegram Integration Module - Setup & Usage Guide

## Overview

The Telegram Integration module provides real-time trading alerts and notifications for the HYDRA-X v2 algorithmic trading bot. It sends alerts for trade entries, partial closes, full closes, daily summaries, and critical errors.

## Features

- **5 Alert Types**: Trade entry, partial close, full close, daily summary, error alerts
- **Beautiful Formatting**: Emojis (🚀, 🎯, ❌, ✅, 📊) with markdown table-like layout
- **Async Message Sending**: Non-blocking async/await patterns
- **Retry Logic**: 3x automatic retry with exponential backoff (0.5s, 2s, 5s)
- **Daily Summary Tracking**: State persistence with JSON, automatic reset at 00:00 UTC
- **Graceful Degradation**: Bot continues trading even if Telegram is unavailable
- **Comprehensive Logging**: All operations logged with timestamps and severity levels

## Installation

### Prerequisites

- Python 3.10+
- python-telegram-bot >= 20.0 (included in requirements.txt)
- Valid Telegram Bot Token (from @BotFather)
- Telegram Chat ID or User ID

### Setup Steps

1. **Get Telegram Bot Token**
   - Open Telegram and search for @BotFather
   - Send `/start` and follow the prompts
   - Send `/newbot` to create a new bot
   - Choose a name and username for your bot
   - BotFather will provide your bot token (save this!)

2. **Get Your Telegram Chat ID**
   - Add your bot to a Telegram group or chat
   - Send a message in the chat: `/start`
   - Use this helper to get chat ID:
     ```bash
     curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
     ```
   - Find the `"chat":{"id":YOUR_CHAT_ID}` in the response

3. **Configure config.yaml**
   ```yaml
   telegram:
     enabled: true
     token: "YOUR_BOT_TOKEN_HERE"
     chat_id: "YOUR_CHAT_ID_HERE"
   ```

4. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### config.yaml Parameters

```yaml
telegram:
  enabled: true              # Enable/disable Telegram notifications
  token: ""                 # Bot API token from @BotFather
  chat_id: ""              # Destination chat or user ID for alerts
```

### Using Environment Variables (Recommended for Security)

Instead of storing sensitive tokens in config.yaml, use environment variables:

```yaml
telegram:
  enabled: true
  token: "${TELEGRAM_TOKEN}"      # Will load from TELEGRAM_TOKEN env var
  chat_id: "${TELEGRAM_CHAT_ID}"  # Will load from TELEGRAM_CHAT_ID env var
```

Set environment variables:
```bash
export TELEGRAM_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
```

## Alert Types & Examples

### 1. Trade Entry Alert
Sent when a new trade position is opened.