"""Speaking orders [E]: hold the push-to-talk key, say the order, let go.

The words are heard by a speech engine (`engines.py`): the Mac's own on-device
recogniser, whisper.cpp on this computer, a whisper.cpp server on the network,
or a cloud transcription service. What was heard goes to the console exactly
as if typed, so the parser (and the language model, if one is set up)
understand it, and the officer reads it back. Settings and downloaded models
live in the project's config/ folder (config/settings.json "voice",
config/voice/).
"""
