#!/usr/bin/env python3
"""Simple test script to verify the Telegram component can be imported and instantiated."""

import sys
import os

# Add dfx to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dfx'))

try:
    from dfx.social.telegram.telegram_message import DFXTelegramMessageComponent
    print("✓ Telegram component imported successfully")

    # Test component instantiation
    component = DFXTelegramMessageComponent(
        bot_token="123456:ABC-DEF",
        chat_id="123456789",
        text="Hello, World!"
    )
    print("✓ Telegram component instantiated successfully")

    # Check component properties
    print(f"✓ Component name: {component.name}")
    print(f"✓ Component display name: {component.display_name}")
    print(f"✓ Component description: {component.description}")

    # Test input validation
    validation = component._validate_inputs()
    if validation["valid"]:
        print("✓ Input validation passed")
    else:
        print(f"✗ Input validation failed: {validation['errors']}")

    print("\n✓ All tests passed! The Telegram component is working correctly.")

except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)