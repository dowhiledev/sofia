"""Periodical summarization memory module."""

import math
from typing import List, Optional, Union

from nomos.models.agent import Event, Message, Step, Summary

from ..constants import PERIODICAL_SUMMARIZATION_SYSTEM_MESSAGE
from ..llms import LLMBase
from ..utils.logging import log_debug
from .base import Memory


class PeriodicalSummarizationMemory(Memory):
    """Memory module that summarizes periodically."""

    def __init__(
        self,
        llm: LLMBase,
        alpha: float = math.log(2) / 20,  # noqa
        W: int = 10,
        beta: float = 0.5,
        tau: float = 0.2,
        M: int = 10,
        N_max: int = 50,
        T_max: int = 4000,
        weights: Optional[dict] = None,
        preserve_history: bool = True,
    ) -> None:
        """
        Initialize periodical summarization memory.

        :param alpha: Decay rate for recency. (Default: log(2)/20)
        :param W: Hard recency window size. (Default: 10)
        :param beta: Mix between window and decay. (Default: 0.5)
        :param tau: Threshold for summarization. (Default: 0.2)
        :param M: Always keep last M items. (Default: 2)
        :param N_max: Max items before summarization. (Default: 50)
        :param T_max: Max token count before summarization. (Default: 4000)
        :param weights: Weights for different types of messages. (Default: {"summary": 0.5, "tool": 0.8, "error": 0.0, "fallback": 0.0})
        :param preserve_history: Flag to preserve history for debugging. (Default: True)
        """
        super().__init__()
        # Fixed
        self.alpha = alpha
        self.W = W
        self.beta = beta
        self.tau = tau
        self.M = M
        self.N_max = N_max
        self.T_max = T_max
        self.llm = llm
        self.weights = (
            {"summary": 0.5, "tool": 0.8, "error": 0.0, "fallback": 0.0}
            if weights is None
            else weights
        )
        self.preserve_history = preserve_history

    def token_counter(self, text: str) -> int:
        """Count tokens using the underlying LLM's tokenizer."""
        return self.llm.token_counter(text)

    def generate_summary(self, items: List[Union[Event, Summary]]) -> Summary:
        """Generate a summary from a list of events or summaries."""
        log_debug(f"Generating summary from {len(items)} items.")
        items_str = "\n".join([str(item) for item in items])
        summary = self.llm.get_output(
            messages=[
                Message(role="system", content=PERIODICAL_SUMMARIZATION_SYSTEM_MESSAGE),
                Message(
                    role="user",
                    content=f"Summarize the following Context:\n\n{items_str}",
                ),
            ],
            response_format=Summary,
        )
        assert isinstance(summary, Summary), "Summary generation failed."
        log_debug(f"Generated summary: {summary.content}")
        return summary

    def optimize(self) -> None:
        """Optimize memory usage by summarizing."""
        summary_i = next(
            (
                i
                for i in range(len(self.context) - 1, -1, -1)
                if isinstance(self.context[i], Summary)
            ),
            0,
        )
        context_cpy = self.context[summary_i:]
        N = len(context_cpy)
        total_context = " ".join([str(item) for item in context_cpy if not isinstance(item, Step)])
        T: int = self.token_counter(total_context)

        log_debug(
            f"Overall context length: {len(self.context)}, Selected context length: {N}, Summary index: {summary_i}"
        )
        log_debug(f"Token Fill Percentage: {T / self.T_max:.2%}, ")
        if N < self.N_max and T < self.T_max:
            return

        log_debug("Max token limit or item limit exceeded. Summarizing...")
        # Compute scores
        scores = []
        for i, item in enumerate(context_cpy, start=1):
            d = N - i
            decay = math.exp(-self.alpha * d)
            r = 1.0 if d <= self.W else 0.0

            # Type-based weight
            if isinstance(item, Summary):
                w_type = self.weights.get("summary", 0.5)
            elif isinstance(item, Event):
                w_type = self.weights.get(item.type, 1.0)
            else:
                w_type = 0.0

            s = w_type * (self.beta * r + (1 - self.beta) * decay)
            scores.append((i, s))

        # Determine Raw and Summarize sets
        raw_indices = {i for i, s in scores if s >= self.tau}
        recent_indices = {i for i in range(N - self.M + 1, N + 1)}
        raw_indices |= recent_indices

        summarize_items = [context_cpy[i - 1] for i, s in scores if i not in raw_indices]

        # Generate summary
        summary = self.generate_summary(summarize_items)
        # Update context (Previous context (-recent items) + summary + recent items)
        self.context = self.context[: -self.M] if self.preserve_history else []
        self.context += [summary] + self.context[-self.M :]
        log_debug(f"Updated context length: {len(self.context)}")

    def get_history(self) -> List[Union[Event, Summary, Step]]:
        """Get the history of messages."""
        summary_i = next(
            (
                i
                for i in range(len(self.context) - 1, -1, -1)
                if isinstance(self.context[i], Summary)
            ),
            0,
        )
        return self.context[summary_i:]


__all__ = ["PeriodicalSummarizationMemory"]
