"""
CONTEXT COMPRESSOR - The Summarizer
====================================
We can't feed the entire conversation history into every API call.
That would burn through our token budget in 3 messages.

The ContextCompressor uses a sliding window + extractive summarization approach:
1. Keep the last 3 messages verbatim (recency matters)
2. Summarize older messages into bullet points
3. Preserve ALL medical entities (symptoms, severities, medications) even during compression
4. Discard pleasantries and filler ("thanks!", "you're welcome")

This is NOT abstractive summarization (no LLM calls). It's rule-based extraction.
Fast, deterministic, and free.

Author: Alex + Sarah (pair-programmed during a thunderstorm)
Bug Report: Sometimes keeps too many "how are you" exchanges. Working on it.
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CompressedContext:
    """Result of context compression."""
    recent_messages: List[str]  # Last N messages, verbatim
    summary_bullets: List[str]  # Extracted key points from older messages
    preserved_entities: List[Dict[str, str]]  # Medical entities that must not be lost
    original_token_count: int
    compressed_token_count: int
    compression_ratio: float


class ContextCompressor:
    def __init__(self, keep_recent: int = 3, max_summary_bullets: int = 5):
        """
        Initialize the compressor.
        
        Args:
            keep_recent: Number of recent messages to keep verbatim
            max_summary_bullets: Maximum number of summary bullets from older messages
        """
        self.keep_recent = keep_recent
        self.max_summary_bullets = max_summary_bullets
        
        # Medical entities to preserve during compression
        # TODO: Expand this list based on real user data patterns
        self.entity_patterns = {
            "symptom": r'\b(headache|fever|pain|nausea|dizziness|fatigue|cough|rash|swelling)\b',
            "severity": r'\b(severe|mild|moderate|intense|worst ever|\d+/10)\b',
            "medication": r'\b(ibuprofen|tylenol|aspirin|metformin|lisinopril|antibiotic)\b',
            "duration": r'\b(\d+\s*(days?|hours?|weeks?|months?))\b',
            "body_part": r'\b(chest|head|stomach|back|arm|leg|throat|abdomen)\b'
        }
        
        # Filler phrases to discard during compression
        self.filler_patterns = [
            r'^thanks!?$',
            r'^thank you$',
            r'^you\'?re welcome$',
            r'^no problem$',
            r'^how are you$',
            r'^i\'?m fine$',
            r'^that\'?s all$',
            r'^anything else',
        ]
    
    def _count_tokens(self, text: str) -> int:
        """Simple word-based token estimation."""
        if not text:
            return 0
        return len(text.split()) // 4 + 1
    
    def _extract_entities(self, text: str) -> List[Dict[str, str]]:
        """Extracts medical entities from text."""
        entities = []
        text_lower = text.lower()
        
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                entities.append({
                    "type": entity_type,
                    "value": match,
                    "source_text": text[:50]  # First 50 chars for context
                })
        
        return entities
    
    def _is_filler(self, message: str) -> bool:
        """Checks if a message is just filler/pleasantry."""
        msg_clean = message.strip().lower()
        for pattern in self.filler_patterns:
            if re.match(pattern, msg_clean):
                return True
        return False
    
    def _summarize_message(self, message: str) -> Optional[str]:
        """
        Converts a message into a concise bullet point.
        Uses extractive approach: pulls out key clauses.
        """
        # If message contains medical entities, keep the clause with them
        for entity_type, pattern in self.entity_patterns.items():
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                # Extract surrounding context (±20 chars)
                start = max(0, match.start() - 20)
                end = min(len(message), match.end() + 20)
                excerpt = message[start:end].strip()
                return f"- {excerpt}"
        
        # No entities found, skip this message in summary
        return None
    
    def compress(self, conversation_history: List[Dict[str, str]]) -> CompressedContext:
        """
        Compresses a conversation history into a token-efficient format.
        
        Args:
            conversation_history: List of dicts with 'role' and 'content' keys
            
        Returns:
            CompressedContext object with recent messages, summary, and entities
        """
        if not conversation_history:
            return CompressedContext(
                recent_messages=[],
                summary_bullets=[],
                preserved_entities=[],
                original_token_count=0,
                compressed_token_count=0,
                compression_ratio=1.0
            )
        
        # Calculate original token count
        original_text = " ".join([msg.get('content', '') for msg in conversation_history])
        original_tokens = self._count_tokens(original_text)
        
        # Split into recent vs older
        recent = conversation_history[-self.keep_recent:]
        older = conversation_history[:-self.keep_recent] if len(conversation_history) > self.keep_recent else []
        
        # Keep recent messages verbatim (but skip fillers)
        recent_messages = []
        for msg in recent:
            content = msg.get('content', '')
            if not self._is_filler(content):
                recent_messages.append(content)
        
        # Process older messages into summary bullets
        summary_bullets = []
        all_entities = []
        
        for msg in older:
            content = msg.get('content', '')
            
            # Extract entities first (preserve regardless of filler status)
            entities = self._extract_entities(content)
            all_entities.extend(entities)
            
            # Skip fillers for summary
            if self._is_filler(content):
                continue
            
            # Try to summarize
            bullet = self._summarize_message(content)
            if bullet and bullet not in summary_bullets:  # Avoid duplicates
                summary_bullets.append(bullet)
        
        # Cap summary bullets
        summary_bullets = summary_bullets[:self.max_summary_bullets]
        
        # Deduplicate entities by value
        seen = set()
        unique_entities = []
        for entity in all_entities:
            key = (entity['type'], entity['value'])
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)
        
        # Calculate compressed token count
        compressed_text = " ".join(recent_messages) + " " + " ".join(summary_bullets)
        compressed_tokens = self._count_tokens(compressed_text)
        
        # Add entity tokens (they get injected separately but count toward budget)
        entity_text = " ".join([f"{e['type']}: {e['value']}" for e in unique_entities])
        compressed_tokens += self._count_tokens(entity_text)
        
        compression_ratio = original_tokens / max(compressed_tokens, 1)
        
        return CompressedContext(
            recent_messages=recent_messages,
            summary_bullets=summary_bullets,
            preserved_entities=unique_entities,
            original_token_count=original_tokens,
            compressed_token_count=compressed_tokens,
            compression_ratio=round(compression_ratio, 2)
        )
    
    def format_for_prompt(self, compressed: CompressedContext) -> str:
        """
        Formats the compressed context for injection into the system prompt.
        
        Token-efficient format:
        - Recent messages as dialogue
        - Summary as bullets
        - Entities as inline notes
        """
        parts = []
        
        if compressed.summary_bullets:
            parts.append("CONVERSATION SUMMARY:")
            parts.extend(compressed.summary_bullets)
        
        if compressed.preserved_entities:
            entity_str = ", ".join([f"{e['value']} ({e['type']})" for e in compressed.preserved_entities])
            parts.append(f"\nKEY MEDICAL ENTITIES PRESERVED: {entity_str}")
        
        if compressed.recent_messages:
            parts.append("\nRECENT EXCHANGE:")
            for i, msg in enumerate(compressed.recent_messages):
                parts.append(f"  [{i+1}] {msg}")
        
        return "\n".join(parts)


if __name__ == "__main__":
    # Quick test
    compressor = ContextCompressor(keep_recent=2, max_summary_bullets=3)
    
    test_history = [
        {"role": "user", "content": "I have a headache"},
        {"role": "assistant", "content": "How severe is the headache?"},
        {"role": "user", "content": "It's pretty bad, like 7/10"},
        {"role": "assistant", "content": "How long has it lasted?"},
        {"role": "user", "content": "About 3 days now"},
        {"role": "assistant", "content": "Any other symptoms?"},
        {"role": "user", "content": "Feeling nauseous too"},
        {"role": "assistant", "content": "Thanks for sharing. Anything else?"},
        {"role": "user", "content": "No that's all thanks"},
    ]
    
    result = compressor.compress(test_history)
    print(f"Original tokens: {result.original_token_count}")
    print(f"Compressed tokens: {result.compressed_token_count}")
    print(f"Compression ratio: {result.compression_ratio}x")
    print("\nFormatted output:")
    print(compressor.format_for_prompt(result))
