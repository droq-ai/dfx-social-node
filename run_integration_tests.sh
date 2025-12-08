#!/bin/bash
# Integration Test Runner for DFX Social Executor Node

set -e

echo "🧪 DFX Social Executor Node Integration Test Runner"
echo "=================================================="

# Check if the server is running
echo "🔍 Checking if server is running on http://localhost:8007..."
if curl -s -f http://localhost:8007/health > /dev/null; then
    echo "✅ Server is running"
else
    echo "❌ Server is not running. Please start it with './start-local.sh'"
    echo "Then run this script again."
    exit 1
fi

# Check if .env.test exists and is configured
echo "🔍 Checking test configuration..."
if [ ! -f ".env.test" ]; then
    echo "❌ .env.test file not found"
    echo "Please create .env.test with your Telegram bot configuration:"
    echo ""
    echo "TELEGRAM_BOT_TOKEN=your_actual_bot_token_here"
    echo "TELEGRAM_CHAT_ID=your_actual_chat_id_here"
    echo "TEST_MESSAGE=Hello from DFX Social Executor Node Integration Test! 🤖"
    echo "TEST_PARSE_MODE=HTML"
    exit 1
fi

# Check if the environment file has actual values (not placeholders)
if grep -q "your_bot_token_here" .env.test || grep -q "your_chat_id_here" .env.test; then
    echo "❌ .env.test file contains placeholder values"
    echo "Please update .env.test with your actual Telegram bot token and chat ID:"
    echo ""
    echo "1. Get a bot token from @BotFather on Telegram"
    echo "2. Get your chat ID from @userinfobot on Telegram"
    echo "3. Update the values in .env.test"
    exit 1
fi

echo "✅ Configuration found"

# Install test dependencies if needed
if ! command -v python3 -m pytest &> /dev/null; then
    echo "📦 Installing test dependencies..."
    if command -v uv &> /dev/null; then
        uv pip install pytest pytest-asyncio httpx python-dotenv
    else
        python3 -m pip install pytest pytest-asyncio httpx python-dotenv
    fi
fi

# Run the integration tests
echo "🚀 Running integration tests..."
echo ""

# Run with current Python and uvicorn
export PYTHONPATH="${PYTHONPATH:-$(pwd)/src:$(pwd)/dfx}"

python3 -m pytest tests/test_telegram_integration.py -v --tb=short

echo ""
echo "=================================================="
echo "🎉 Integration tests completed!"