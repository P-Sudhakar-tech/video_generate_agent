"""Channel branding: the like / share / subscribe intro that opens every video.

Fixed templates rather than LLM output, so the call to action is always correct
and identical across videos. The channel name is supplied by the user at render
time (UI field or --channel) - never hard-coded.
"""

INTRO_TEXT = {
    "en": {
        "narration": (
            "Hey everyone, welcome to {channel}! Before we start, if you find this video helpful, "
            "please like it, share it with your friends, and subscribe to {channel}. "
            "And hit the bell icon so you never miss a new coding tutorial. Let's get started!"
        ),
        "welcome": "Welcome to",
        "like": "LIKE",
        "share": "SHARE",
        "subscribe": "SUBSCRIBE",
    },
    "te": {
        "narration": (
            "అందరికీ నమస్కారం, {channel} కి స్వాగతం! వీడియో స్టార్ట్ చేసే ముందు, ఈ వీడియో మీకు ఉపయోగపడితే "
            "like చేయండి, మీ friends తో share చేయండి, మరియు {channel} channel ని subscribe చేయండి. "
            "కొత్త coding వీడియోలు మిస్ అవ్వకుండా bell icon కూడా నొక్కండి. ఇక స్టార్ట్ చేద్దాం!"
        ),
        "welcome": "స్వాగతం",
        "like": "LIKE",
        "share": "SHARE",
        "subscribe": "SUBSCRIBE",
    },
}


def intro_narration(channel: str, language: str) -> str:
    return INTRO_TEXT[language]["narration"].format(channel=channel)


def intro_labels(language: str) -> dict:
    return INTRO_TEXT[language]
