"""Evals for the voice agent.

Talks to the same prompt the real calls use (``app.agent``), with a scripted
callee who pushes back: asks who is calling, asks if it's a bot, wants details,
says they're busy. Rule checks catch the call-center habits we never want; an
optional LLM judge scores how natural the call sounds.

    python -m evals.run                      # offline, mock model
    EVAL_LLM_PROVIDER=openai python -m evals.run --judge
"""
