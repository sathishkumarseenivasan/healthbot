"""
TOKEN BUDGETER - The Gatekeeper
================================
We have ONE API key. Every token costs money. This module enforces a STRICT 
token budget across all components of the system prompt.

It's not just about counting tokens; it's about ALLOCATING them wisely:
- 100 tokens for persona definition
- 150 tokens for historical context
- 50 tokens for legal disclaimers
- 200 tokens for empathy calibration
- REMAINDER for the actual conversation

If we exceed the budget, this module SACRIFICES lower-priority content.
Yes, it will delete your beautiful prose to save money. That's its job.

Author: David
Note: I wrote this at 3 AM after seeing our AWS bill. Never again.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class PromptSection(Enum):
    PERSONA = "persona"
    HISTORY = "history"
    DISCLAIMERS = "disclaimers"
    EMPATHY = "empathy"
    SYMPTOM_PATTERN = "symptom_pattern"
    CONVERSATION = "conversation"


@dataclass
class BudgetAllocation:
    """Defines how many tokens each section gets."""
    section: PromptSection
    max_tokens: int
    priority: int  # Lower number = higher priority (will be sacrificed last)
    current_tokens: int = 0
    content: str = ""


class TokenBudgeter:
    def __init__(self, total_budget: int = 800):
        """
        Initialize with a total token budget.
        
        Default is 800 tokens for system prompt + context.
        Adjust based on your model's context window and cost constraints.
        
        REAL TALK: We use 800 because our model has a 4k window and we need
        ~3k for the conversation history + response. Math.
        """
        self.total_budget = total_budget
        self.allocations = self._create_default_allocations()
        # TODO: Elena - review if disclaimer allocation is sufficient for legal compliance
        
    def _create_default_allocations(self) -> Dict[PromptSection, BudgetAllocation]:
        return {
            PromptSection.PERSONA: BudgetAllocation(
                section=PromptSection.PERSONA,
                max_tokens=100,
                priority=1,  # Highest priority - core functionality
                content=""
            ),
            PromptSection.HISTORY: BudgetAllocation(
                section=PromptSection.HISTORY,
                max_tokens=150,
                priority=3,
                content=""
            ),
            PromptSection.DISCLAIMERS: BudgetAllocation(
                section=PromptSection.DISCLAIMERS,
                max_tokens=80,
                priority=2,  # Legal must stay
                content=""
            ),
            PromptSection.EMPATHY: BudgetAllocation(
                section=PromptSection.EMPATHY,
                max_tokens=60,
                priority=4,
                content=""
            ),
            PromptSection.SYMPTOM_PATTERN: BudgetAllocation(
                section=PromptSection.SYMPTOM_PATTERN,
                max_tokens=70,
                priority=3,
                content=""
            ),
            # Conversation gets whatever is left
            PromptSection.CONVERSATION: BudgetAllocation(
                section=PromptSection.CONVERSATION,
                max_tokens=9999,  # Effectively unlimited, gets remainder
                priority=5,
                content=""
            )
        }
    
    def _count_tokens(self, text: str) -> int:
        """
        Simple token counter. Uses word-based estimation.
        
        NOTE: This is NOT the same as the model's tokenizer.
        For production, swap this with tiktoken or the model's official counter.
        
        Why this approximation? Speed. We call this function 10+ times per request.
        Official tokenizers add 50ms latency. This adds <1ms.
        Trade-offs, baby.
        """
        if not text:
            return 0
        # Rough estimate: 1 token ≈ 0.75 words for English
        words = len(text.split())
        return int(words / 0.75) + 1  # +1 for safety margin
    
    def allocate(self, section: PromptSection, content: str) -> bool:
        """
        Allocates content to a section, truncating if necessary.
        
        Returns True if content fit within budget, False if truncated.
        """
        if section not in self.allocations:
            raise ValueError(f"Unknown section: {section}")
        
        allocation = self.allocations[section]
        token_count = self._count_tokens(content)
        
        if token_count <= allocation.max_tokens:
            allocation.content = content
            allocation.current_tokens = token_count
            return True
        else:
            # Truncate content to fit budget
            truncated = self._truncate_to_tokens(content, allocation.max_tokens)
            allocation.content = truncated
            allocation.current_tokens = self._count_tokens(truncated)
            return False  # Signal that truncation occurred
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncates text to approximately max_tokens."""
        words = text.split()
        # Estimate word count from token count
        max_words = int(max_tokens * 0.75)
        
        if len(words) <= max_words:
            return text
        
        # Truncate and add ellipsis
        truncated_words = words[:max_words]
        return " ".join(truncated_words) + "..."
    
    def get_total_used(self) -> int:
        """Returns total tokens currently allocated."""
        return sum(a.current_tokens for a in self.allocations.values())
    
    def get_remaining(self) -> int:
        """Returns remaining tokens in budget."""
        used = self.get_total_used()
        return max(0, self.total_budget - used)
    
    def optimize(self) -> List[str]:
        """
        Reviews allocations and sacrifices low-priority content if over budget.
        
        Returns a list of sections that were sacrificed/truncated.
        """
        sacrificed = []
        total_used = self.get_total_used()
        
        if total_used <= self.total_budget:
            return sacrificed  # All good!
        
        # Sort by priority (highest number = lowest priority = sacrifice first)
        sorted_sections = sorted(
            self.allocations.values(),
            key=lambda x: x.priority,
            reverse=True
        )
        
        for allocation in sorted_sections:
            if self.get_total_used() <= self.total_budget:
                break
            
            # Skip high-priority sections (persona, disclaimers)
            if allocation.priority <= 2:
                continue
            
            # Sacrifice this section: reduce to 50% or minimum viable
            original_tokens = allocation.current_tokens
            reduced_content = self._truncate_to_tokens(
                allocation.content, 
                max(10, allocation.max_tokens // 2)
            )
            
            if reduced_content != allocation.content:
                allocation.content = reduced_content
                allocation.current_tokens = self._count_tokens(reduced_content)
                sacrificed.append(allocation.section.value)
        
        return sacrificed
    
    def assemble_final_prompt(self) -> str:
        """
        Assembles all sections into the final system prompt.
        
        Order matters: Persona first, then context, then conversation.
        """
        sections_order = [
            PromptSection.PERSONA,
            PromptSection.DISCLAIMERS,
            PromptSection.EMPATHY,
            PromptSection.SYMPTOM_PATTERN,
            PromptSection.HISTORY,
            PromptSection.CONVERSATION
        ]
        
        parts = []
        for section in sections_order:
            content = self.allocations[section].content
            if content:
                parts.append(content)
        
        return "\n\n".join(parts)
    
    def reset(self):
        """Resets all allocations for a new request."""
        for allocation in self.allocations.values():
            allocation.content = ""
            allocation.current_tokens = 0
    
    def get_budget_report(self) -> Dict:
        """
        Returns a detailed report of token usage.
        Useful for debugging and optimization.
        
        TODO: Hook this up to a dashboard so we can monitor burn rate.
        """
        return {
            "total_budget": self.total_budget,
            "total_used": self.get_total_used(),
            "remaining": self.get_remaining(),
            "utilization_percent": round((self.get_total_used() / self.total_budget) * 100, 2),
            "by_section": {
                s.value: {
                    "tokens": a.current_tokens,
                    "max": a.max_tokens,
                    "priority": a.priority
                }
                for s, a in self.allocations.items()
            }
        }


if __name__ == "__main__":
    budgeter = TokenBudgeter(total_budget=500)  # Smaller budget for testing
    
    # Test allocation
    budgeter.allocate(PromptSection.PERSONA, "You are a helpful medical assistant.")
    budgeter.allocate(PromptSection.HISTORY, "User has had headaches for 3 days, severity increasing.")
    
    print(f"Used: {budgeter.get_total_used()} / {budgeter.total_budget}")
    print(f"Remaining: {budgeter.get_remaining()}")
    print(budgeter.get_budget_report())
