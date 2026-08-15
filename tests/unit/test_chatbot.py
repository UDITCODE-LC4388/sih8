"""
Unit Tests for AI Lunar Mission Chatbot & GCS Copilot (Module 6)
"""

from __future__ import annotations

import os
import pytest
from src.navigation_interface.chatbot import LunarMissionChatbot


def test_chatbot_initialization():
    bot = LunarMissionChatbot()
    assert bot.model == "llama-3.3-70b-versatile"
    assert isinstance(bot.conversation_history, list)


def test_chatbot_system_prompt_generation():
    bot = LunarMissionChatbot()
    prompt = bot.build_system_prompt(active_patch_id="ch2_tmc_patch_001_r25000_c4000")
    
    # Verify core safety constraints and flight rules are present in system prompt
    assert "SIH260008" in prompt
    assert "Chandrayaan-2" in prompt
    assert "10.0°" in prompt
    assert "24m x 24m" in prompt
    assert "ch2_tmc_patch_001_r25000_c4000" in prompt
    assert "1192" in prompt or "Elevation Range" in prompt


def test_chatbot_live_or_fallback_query():
    bot = LunarMissionChatbot()
    reply = bot.chat(
        "State the Vikram lander maximum slope threshold in degrees.",
        active_patch_id="ch2_tmc_patch_001_r25000_c4000",
    )
    assert isinstance(reply, str)
    assert len(reply) > 10
    assert "10" in reply or "slope" in reply.lower()
