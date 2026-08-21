"""
SYMPTOM WEAVER - The Temporal Symptom Correlator
================================================
Unlike basic RAG that just retrieves "similar" chunks, the SymptomWeaver 
analyzes the TEMPORAL RELATIONSHIP between symptoms over time.

It doesn't just say "User mentioned headache." 
It says "User's headache has migrated from frontal to occipital over 3 days, 
correlating with increased stress events on Day 2."

This is longitudinal intelligence, not vector similarity.

Author: Alex
Last Modified: 2026-03-14 (during the "Great Token Crisis")
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SymptomCluster:
    """A group of related symptoms with temporal metadata."""
    primary_symptom: str
    related_symptoms: List[str]
    timeline_days: int
    severity_trend: str  # "increasing", "decreasing", "stable", "fluctuating"
    contextual_triggers: List[str]


class SymptomWeaver:
    def __init__(self, db_path: str = "health_graph.db"):
        self.db_path = db_path
        # TODO: David - add connection pooling here if we scale past 100 concurrent users
        
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def analyze_temporal_patterns(self, user_id: str, current_symptom: str) -> Optional[SymptomCluster]:
        """
        Analyzes how the current symptom relates to historical symptoms over time.
        
        This is NOT vector search. This is SQL-based temporal reasoning.
        We look for:
        1. Previous occurrences of this symptom
        2. Symptoms that appeared within 48 hours before/after
        3. Severity progression patterns
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Get all instances of this symptom
            cursor.execute("""
                SELECT timestamp, severity, context 
                FROM health_events 
                WHERE user_id = ? AND LOWER(symptom) LIKE LOWER(?)
                ORDER BY timestamp DESC
                LIMIT 10
            """, (user_id, f"%{current_symptom}%"))
            
            symptom_history = cursor.fetchall()
        except sqlite3.OperationalError:
            # Table doesn't exist yet - return None gracefully
            conn.close()
            return None
        
        if not symptom_history:
            conn.close()
            return None
        
        # Calculate timeline span
        timestamps = [datetime.fromisoformat(row['timestamp']) for row in symptom_history]
        timeline_days = (max(timestamps) - min(timestamps)).days if len(timestamps) > 1 else 0
        
        # Find related symptoms within 48-hour windows
        related = set()
        triggers = set()
        
        for record in symptom_history:
            ts = datetime.fromisoformat(record['timestamp'])
            window_start = ts - timedelta(hours=48)
            window_end = ts + timedelta(hours=48)
            
            # Fetch symptoms in this window
            cursor.execute("""
                SELECT DISTINCT symptom, context 
                FROM health_events 
                WHERE user_id = ? AND timestamp BETWEEN ? AND ?
                AND LOWER(symptom) != LOWER(?)
            """, (user_id, window_start.isoformat(), window_end.isoformat(), current_symptom))
            
            neighbors = cursor.fetchall()
            for n in neighbors:
                related.add(n['symptom'])
                if n['context']:
                    # Simple keyword extraction for triggers
                    # TODO: Sarah - replace with actual NLP trigger detection when we have budget
                    trigger_words = ['stress', 'tired', 'after', 'before', 'during']
                    words = (n['context'] or '').lower().split()
                    triggers.update([w for w in words if w in trigger_words])
        
        # Determine severity trend
        severities = [row['severity'] for row in symptom_history if row['severity']]
        severity_trend = self._calculate_trend(severities)
        
        conn.close()
        
        return SymptomCluster(
            primary_symptom=current_symptom,
            related_symptoms=list(related)[:5],  # Cap at 5 for token efficiency
            timeline_days=timeline_days,
            severity_trend=severity_trend,
            contextual_triggers=list(triggers)[:3]
        )
    
    def _calculate_trend(self, severities: List[int]) -> str:
        """Simple trend calculation. Could be smarter."""
        if len(severities) < 2:
            return "stable"
        
        recent_avg = sum(severities[:3]) / min(3, len(severities))
        older_avg = sum(severities[-3:]) / min(3, len(severities))
        
        diff = recent_avg - older_avg
        if diff > 1:
            return "increasing"
        elif diff < -1:
            return "decreasing"
        else:
            return "fluctuating"
    
    def format_for_prompt(self, cluster: SymptomCluster) -> str:
        """
        Formats the symptom cluster into a concise, token-efficient string
        for injection into the system prompt.
        
        REAL TALK: We tried JSON first, but natural language saved us 40 tokens per call.
        At scale, that's $3000/month. Buy Alex a beer.
        """
        if not cluster:
            return "No historical pattern detected for this symptom."
        
        template = (
            f"HISTORICAL PATTERN: {cluster.primary_symptom} tracked over {cluster.timeline_days} days. "
            f"Trend: {cluster.severity_trend}. "
            f"Often co-occurs with: {', '.join(cluster.related_symptoms) or 'nothing specific'}. "
            f"Potential triggers: {', '.join(cluster.contextual_triggers) or 'unknown'}."
        )
        
        return template


# Quick test harness
if __name__ == "__main__":
    # TODO: Move this to proper pytest suite
    weaver = SymptomWeaver()
    print("SymptomWeaver initialized. Run tests via pytest for actual validation.")
