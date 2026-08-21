"""
EMPATHY CALIBRATOR - Dynamic Tone Adjustment
============================================
Most chatbots have a static "empathetic" persona. Ours CALIBRATES empathy 
based on the user's emotional trajectory over time.

If the user has been distressed for 3+ days → Increase warmth, reduce clinical coldness.
If the user is asking repetitive questions → Detect anxiety spiral, adjust response style.
If the user is in TRIAGE mode → Suppress empathy, maximize clarity.

This is not "be nice." This is algorithmic compassion.

Author: Sarah
Note: I cried testing this on my own data. It works.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum


class EmotionalState(Enum):
    NEUTRAL = "neutral"
    ANXIOUS = "anxious"
    DISTRESSED = "distressed"
    URGENT = "urgent"
    CHRONIC_CONCERN = "chronic_concern"


class EmpathyCalibrator:
    def __init__(self, db_path: str = "health_graph.db"):
        self.db_path = db_path
        # Elena's requirement: Never store raw emotional labels, only derived states
        # We calculate these on-the-fly and discard them after the session
        
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def assess_emotional_trajectory(self, user_id: str) -> Tuple[EmotionalState, Dict[str, any]]:
        """
        Analyzes the user's conversation history to determine their emotional state.
        
        Factors considered:
        1. Frequency of messages in last 24h (high freq = anxiety)
        2. Repetition of similar symptoms (rumination indicator)
        3. Time-of-day patterns (late night = higher distress probability)
        4. Escalation in severity ratings
        
        Returns: (EmotionalState, metadata_dict)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            now = datetime.now()
            day_ago = (now - timedelta(days=1)).isoformat()
            week_ago = (now - timedelta(days=7)).isoformat()
            
            # Count messages in last 24h
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM health_events 
                WHERE user_id = ? AND timestamp > ?
            """, (user_id, day_ago))
            recent_count = cursor.fetchone()['count']
            
            # Check for symptom repetition (same symptom mentioned 3+ times in 24h)
            cursor.execute("""
                SELECT symptom, COUNT(*) as mentions
                FROM health_events 
                WHERE user_id = ? AND timestamp > ?
                GROUP BY LOWER(symptom)
                HAVING COUNT(*) >= 3
                ORDER BY mentions DESC
                LIMIT 1
            """, (user_id, day_ago))
            repetition = cursor.fetchone()
            
            # Check for late-night activity (midnight to 5am)
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM health_events
                WHERE user_id = ? AND timestamp > ?
                AND (strftime('%H', timestamp) >= '00' AND strftime('%H', timestamp) <= '05')
            """, (user_id, week_ago))
            night_activity = cursor.fetchone()['count']
            
            # Get severity trend
            cursor.execute("""
                SELECT severity, timestamp
                FROM health_events
                WHERE user_id = ? AND severity IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 5
            """, (user_id,))
            severity_records = cursor.fetchall()
        except sqlite3.OperationalError:
            # Table doesn't exist - return neutral state
            conn.close()
            return EmotionalState.NEUTRAL, {
                "recent_message_count": 0,
                "repetitive_symptom": None,
                "night_activity_count": 0,
                "severity_escalation": False
            }
        
        conn.close()
        
        # Calculate escalation
        escalation = False
        if len(severity_records) >= 2:
            severities = [r['severity'] for r in severity_records]
            if severities[0] > severities[-1] + 1:  # Recent is worse than older
                escalation = True
        
        # Decision tree for emotional state
        metadata = {
            "recent_message_count": recent_count,
            "repetitive_symptom": repetition['symptom'] if repetition else None,
            "night_activity_count": night_activity,
            "severity_escalation": escalation
        }
        
        # Urgent: High severity + escalation
        if escalation and any(r['severity'] >= 8 for r in severity_records):
            return EmotionalState.URGENT, metadata
        
        # Chronic concern: Symptoms spanning 5+ days with night activity
        if night_activity > 3 and repetition:
            return EmotionalState.CHRONIC_CONCERN, metadata
        
        # Distressed: High message frequency + repetition
        if recent_count > 10 and repetition:
            return EmotionalState.DISTRESSED, metadata
        
        # Anxious: Moderate repetition or night activity
        if repetition or night_activity > 2:
            return EmotionalState.ANXIOUS, metadata
        
        return EmotionalState.NEUTRAL, metadata
    
    def get_persona_modifiers(self, emotional_state: EmotionalState) -> Dict[str, str]:
        """
        Returns prompt modifiers that adjust the AI's tone based on emotional state.
        
        These are INJECTED into the system prompt by the Prism Router.
        Token budget: Max 60 tokens for all modifiers combined.
        """
        modifiers = {
            EmotionalState.NEUTRAL: {
                "tone_instruction": "Maintain a balanced, informative tone. Be friendly but professional.",
                "empathy_level": "standard",
                "response_structure": "Direct answer first, optional context second."
            },
            EmotionalState.ANXIOUS: {
                "tone_instruction": "User shows signs of anxiety. Be reassuring. Validate concerns before providing information. Use calming language.",
                "empathy_level": "elevated",
                "response_structure": "Validation → Clear answer → Reassurance → Actionable next steps."
            },
            EmotionalState.DISTRESSED: {
                "tone_instruction": "User is highly distressed. Prioritize emotional support. Keep information simple and digestible. Avoid overwhelming with options.",
                "empathy_level": "high",
                "response_structure": "Deep validation → One clear recommendation → Offer continued support."
            },
            EmotionalState.URGENT: {
                "tone_instruction": "URGENT SITUATION. Be direct, clear, and action-oriented. Minimize empathy statements to save tokens for critical instructions. Prioritize safety.",
                "empathy_level": "minimal",
                "response_structure": "Immediate action step → Reason → Emergency resources if applicable."
            },
            EmotionalState.CHRONIC_CONCERN: {
                "tone_instruction": "User has ongoing concerns. Acknowledge the duration of their struggle. Emphasize professional long-term support options. Show sustained care.",
                "empathy_level": "sustained_warmth",
                "response_structure": "Acknowledge journey → Validate persistence → Professional referral → Supportive closing."
            }
        }
        
        return modifiers.get(emotional_state, modifiers[EmotionalState.NEUTRAL])
    
    def format_for_prompt(self, emotional_state: EmotionalState) -> str:
        """
        Compresses the empathy calibration into a single, token-efficient line.
        
        REAL TALK: We went through 7 iterations of this. The previous version was 200 tokens.
        This one is 25. That's the difference between profit and loss.
        - Sarah
        """
        modifiers = self.get_persona_modifiers(emotional_state)
        
        # Ultra-compressed format
        empathy_map = {
            "standard": "normal empathy",
            "elevated": "extra reassurance",
            "high": "prioritize emotional support",
            "minimal": "direct/action-focused",
            "sustained_warmth": "acknowledge long-term struggle"
        }
        
        level_text = empathy_map.get(modifiers["empathy_level"], "normal empathy")
        
        return f"EMPATHY MODE: {level_text}. {modifiers['tone_instruction']}"


if __name__ == "__main__":
    calibrator = EmpathyCalibrator()
    print("EmpathyCalibrator ready. Test with actual user data for meaningful results.")
