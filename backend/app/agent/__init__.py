"""The voice agent, defined in code.

Everything that decides how a call sounds lives here and is versioned with the
repo: the system prompt (``prompt``), the model, voice and transcriber
(``config``). Vapi only carries the call; ``app.providers.voice.vapi`` sends
this configuration with every call, and the eval harness in ``backend/evals``
tests the same prompt against the same model.
"""
