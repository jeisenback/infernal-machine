"""Typed prompts (issue #440).

A player is asked a question as `choose(prompt, options)`. The prompt used to be a plain string that the bot, the client and the tests
matched by its wording (`prompt.startswith("Choose what to copy for ")`), so rewording a prompt broke whoever matched it. A `PromptKind`
is the fixed start of a prompt and *is* that string, so everything that treated prompts as strings still works; calling it builds a
`Prompt`, which is the text as before plus what it is (`kind`) and about (`subject`):

    CLONE_PROMPT = PromptKind("clone", "Choose what to copy for ")
    prompt = CLONE_PROMPT("Clone")          # "Choose what to copy for Clone"; prompt.kind == CLONE_PROMPT; prompt.subject == "Clone"
    CLONE_PROMPT.matches(prompt)            # True, by kind (and for a plain string, by its start, so a prompt that came over the wire works)

The wire format is unchanged: a `Prompt` is a `str`, and the server sends it as one.
"""

from __future__ import annotations

from typing import Any


class Prompt(str):
    """The text of a question to a player, with the kind of question it is and what it is about."""
    kind: "PromptKind | None"
    subject: str

    def __new__(cls, text: str, kind: "PromptKind | None" = None, subject: str = "") -> "Prompt":
        prompt = super().__new__(cls, text)
        prompt.kind = kind
        prompt.subject = subject
        return prompt

    def __reduce__(self) -> tuple:
        return (Prompt, (str(self), self.kind, self.subject))


class PromptKind(str):
    """The start of a prompt, as a string (so `prompt.startswith(KIND)` and `KIND + name` keep working) that can also make a `Prompt`."""
    name: str

    def __new__(cls, name: str, text: str) -> "PromptKind":
        kind = super().__new__(cls, text)
        kind.name = name
        return kind

    def __reduce__(self) -> tuple:
        return (PromptKind, (self.name, str(self)))

    def __call__(self, subject: Any = "") -> Prompt:
        """The prompt of this kind about `subject` (the text is the start followed by the subject, as it always was)."""
        subject = str(subject)
        return Prompt(str(self) + subject, self, subject)

    def matches(self, prompt: str) -> bool:
        """Whether `prompt` is of this kind: by the kind's name if it is typed (so rewording the text does not matter), else (a plain
        string: over the wire, or a test's own) by its start."""
        kind = getattr(prompt, "kind", None)
        return kind.name == self.name if kind is not None else str.startswith(prompt, str(self))
