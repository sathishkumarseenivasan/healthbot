"""
PulseWeaver State Machine
Author: Alex Chen (Lead Backend)
Last Updated: 2024-10-27

This module handles the local intent classification. 
We deliberately avoid using an LLM here to save tokens and latency.
Regex and keyword matching are fast, free, and deterministic.

TODO: Sarah - We need to expand the 'vague_symptom' list based on real user logs from beta.
REAL TALK: The threshold for 'EMERGENCY' is intentionally low. Better to false positive 
and catch a heart attack than miss one to save 50ms of regex processing.
"""

import re
from enum import Enum, auto
from typing import Tuple, Optional
from dataclasses import dataclass

class Persona(Enum):
    TRIAGE = "TRIAGE"       # High urgency, medical protocol focus
    EMPATH = "EMPATH"       # Emotional support, chronic illness venting
    ANALYST = "ANALYST"     # Data interpretation, lab results, trends
    GENERAL = "GENERAL"     # Fallback

@dataclass
class IntentResult:
    persona: Persona
    confidence: float
    keywords_matched: list[str]
    is_emergency_interrupt: bool

class HealthStateMachine:
    def __init__(self):
        # Compiled regexes for performance. 
        # TODO: David - Move these to a config file so we can hot-reload without restart?
        self.emergency_patterns = [
            re.compile(r'\b(suicide|kill myself|end it all)\b', re.IGNORECASE),
            re.compile(r'\b(chest pain|crushing chest|can\'t breathe)\b', re.IGNORECASE),
            re.compile(r'\b(severe bleeding|unconscious|stroke symptoms)\b', re.IGNORECASE),
        ]
        
        self.triage_keywords = [
            'fever', 'vomiting', 'rash', 'infection', 'broken', 'fracture', 
            'bleeding', 'hurt', 'pain', 'sudden', 'acute'
        ]
        
        self.empath_keywords = [
            'sad', 'anxious', 'overwhelmed', 'tired', 'scared', 'worried', 
            'lonely', 'depressed', 'stress', 'burnout', 'cant sleep'
        ]
        
        self.analyst_keywords = [
            'lab results', 'blood work', 'mg/dl', 'mmol/l', 'chart', 'graph', 
            'trend', 'history', 'compare', 'percentage', 'reading'
        ]

    def classify(self, user_input: str) -> IntentResult:
        """
        Runs local heuristics to determine the system persona.
        Returns the persona and metadata.
        """
        input_lower = user_input.lower()
        
        # 1. Check for Hard Interrupts (Emergency)
        for pattern in self.emergency_patterns:
            if pattern.search(user_input):
                return IntentResult(
                    persona=Persona.TRIAGE, # Force Triage for emergency handling
                    confidence=1.0,
                    keywords_matched=["EMERGENCY_PROTOCOL"],
                    is_emergency_interrupt=True
                )
        
        # 2. Scoring Logic
        scores = {p: 0 for p in Persona}
        matched_keywords = []

        # Triage Score
        for kw in self.triage_keywords:
            if kw in input_lower:
                scores[Persona.TRIAGE] += 1
                matched_keywords.append(kw)
        
        # Empath Score
        for kw in self.empath_keywords:
            if kw in input_lower:
                scores[Persona.EMPATH] += 1
                matched_keywords.append(kw)
                
        # Analyst Score
        for kw in self.analyst_keywords:
            if kw in input_lower:
                scores[Persona.ANALYST] += 1
                matched_keywords.append(kw)

        # Determine Winner
        max_score = max(scores.values())
        
        if max_score == 0:
            return IntentResult(
                persona=Persona.GENERAL,
                confidence=0.5,
                keywords_matched=[],
                is_emergency_interrupt=False
            )
        
        # Tie-breaking logic: Triage > Empath > Analyst > General
        # Safety first: If Triage and Empath are tied, pick Triage.
        priority_order = [Persona.TRIAGE, Persona.EMPATH, Persona.ANALYST, Persona.GENERAL]
        
        winner = None
        for p in priority_order:
            if scores[p] == max_score:
                winner = p
                break
        
        # Normalize confidence (arbitrary scaling for now)
        confidence = min(1.0, max_score / 5.0) 

        return IntentResult(
            persona=winner,
            confidence=confidence,
            keywords_matched=matched_keywords,
            is_emergency_interrupt=False
        )
