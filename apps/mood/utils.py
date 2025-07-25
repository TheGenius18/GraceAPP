# apps/mood/utils.py

def message_for_mood(mood: str) -> str:
    """
    Returns a friendly message based on the mood choice.
    """
    messages = {
        'happy':   "We heard that you’re feeling great! Good luck! 🌟",
        'sad':     "We noticed you’re feeling sad. We’re here if you need help ❤️",
        'anxious': "Feeling anxious can be tough. Take a deep breath — we’re here for you.",
        'calm':    "Calm and steady — we’re proud of you! 🌿",
        'angry':   "We’re here to support you through these feelings. 💪",
        'tired':   "Remember to rest — we’re rooting for you! 💙",
    }
    return messages.get(mood, "Thanks for sharing how you feel!")
