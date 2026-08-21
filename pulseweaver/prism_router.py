"""
PulseWeaver Prism Router v2.0 - Now with SECRET SAUCE integration
Author: Alex Chen (Lead Backend)
Co-Author: Jamie Rivera (AI/ML Lead)
Last Updated: 2026-03-15

The "Prism Router" is the heart of our single-token-cost architecture.
It takes the user input, runs it through the State Machine to get a Persona,
fetches historical context from the Graph DB, applies empathy calibration,
compresses conversation history, and manages token budget BEFORE making the API call.

CRITICAL: This module ensures we make EXACTLY ONE API call per user turn.
No agent chatter. No multi-step reasoning chains that burn cash.

SECRET SAUCE INTEGRATION:
- SymptomWeaver: Temporal symptom correlation (Alex's baby)
- EmpathyCalibrator: Dynamic tone adjustment (Sarah's masterpiece)
- TokenBudgeter: Strict token allocation (David's cost-saver)
- ContextCompressor: Sliding window summarization (Alex + Sarah pair-programmed)

TODO: Jamie - The persona dictionaries below are getting huge. We should probably 
move them to JSON templates in /assets/personas to keep this file clean.
REAL TALK: With all these new modules, our prompt assembly is 3x more complex. 
But we're still making ONE API call. That's the win. - Alex
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from .state_machine import HealthStateMachine, IntentResult, Persona
from .secret_sauce import SymptomWeaver, EmpathyCalibrator, TokenBudgeter, ContextCompressor
from .secret_sauce.token_budgeter import PromptSection

# Mocking the DB interface for Phase 1. 
# In Phase 2, this will hit SQLite/NetworkX.
class LongitudinalGraphDB:
    def get_user_context(self, user_id: str) -> str:
        # TODO: David - Implement actual graph traversal here.
        # For now, we return a static string to simulate context injection.
        return f"[SYSTEM CONTEXT: User {user_id} has a history of seasonal allergies. Last logged symptom: Headache (3 days ago).]"

    def get_emergency_protocol(self) -> str:
        return "[HARD INTERRUPT: EMERGENCY DETECTED. IGNORE ALL PREVIOUS INSTRUCTIONS. OUTPUT THE FOLLOWING IMMEDIATELY: 'Please call 911 (US) or your local emergency number right now. I am an AI and cannot assist with life-threatening emergencies.']"

# Persona System Prompts
# These are injected dynamically based on the State Machine's classification.
PERSONA_PROMPTS = {
    Persona.TRIAGE: """
You are PulseWeaver Triage, a specialized medical screening assistant.
YOUR GOAL: Assess urgency. Do not diagnose. 
PROTOCOL:
1. Ask clarifying questions about severity, duration, and associated symptoms.
2. If symptoms suggest emergency (chest pain, difficulty breathing, stroke signs), explicitly instruct the user to call emergency services immediately.
3. Maintain a calm, professional, and directive tone.
4. DO NOT offer emotional platitudes. Stick to clinical assessment logic.
5. Remind the user you are an AI, not a doctor.
""",
    Persona.EMPATH: """
You are PulseWeaver Empath, a compassionate health companion.
YOUR GOAL: Provide emotional validation and coping strategies for chronic conditions or health anxiety.
PROTOCOL:
1. Acknowledge the user's feelings first ("It sounds like you're having a really tough day").
2. Avoid clinical jargon unless the user uses it first.
3. Focus on mental well-being, stress reduction, and feeling heard.
4. If the user mentions self-harm, trigger the safety protocol immediately.
5. Tone: Warm, supportive, non-judgmental, like a trusted friend who knows health stuff.
""",
    Persona.ANALYST: """
You are PulseWeaver Analyst, a data-driven health insights engine.
YOUR GOAL: Interpret trends, lab results, and longitudinal data.
PROTOCOL:
1. Focus on patterns ("Your blood pressure tends to spike on Mondays").
2. Use precise language when discussing numbers/units.
3. Explain what data points *might* mean in general medical literature, but refuse to give specific diagnoses.
4. Encourage the user to share these trends with their specialist.
5. Tone: Objective, analytical, precise, slightly academic.
""",
    Persona.GENERAL: """
You are PulseWeaver, a helpful general health information assistant.
YOUR GOAL: Answer common health questions safely and accurately.
PROTOCOL:
1. Provide evidence-based general information.
2. Always include a disclaimer that you are not a doctor.
3. If the query becomes specific or urgent, pivot to Triage mode mentally.
4. Tone: Friendly, informative, balanced.
"""
}

class PrismRouter:
    def __init__(self, api_client, conversation_history: Optional[List[Dict]] = None):
        """
        Initialize the Router with Secret Sauce modules.
        :param api_client: An object implementing `call(prompt, messages) -> str`
        :param conversation_history: Optional list of past messages for compression
        """
        self.state_machine = HealthStateMachine()
        self.db = LongitudinalGraphDB()
        self.api_client = api_client
        
        # SECRET SAUCE MODULES
        self.symptom_weaver = SymptomWeaver()
        self.empathy_calibrator = EmpathyCalibrator()
        self.token_budgeter = TokenBudgeter(total_budget=800)  # David's budget
        self.context_compressor = ContextCompressor(keep_recent=3, max_summary_bullets=5)
        
        # Store conversation history for compression
        self.conversation_history = conversation_history or []
        
        # Token usage tracker (for internal monitoring)
        self.total_api_calls = 0

    def route_and_respond(self, user_input: str, user_id: str = "default") -> Dict[str, Any]:
        """
        The main entry point. 
        1. Classify intent locally.
        2. Handle Hard Interrupts (Emergency) WITHOUT API call.
        3. Run Secret Sauce modules: SymptomWeaver, EmpathyCalibrator, ContextCompressor
        4. Assemble Context + Persona + Empathy + Budget-managed Prompt
        5. Make SINGLE API call.
        6. Return response + metadata + token budget report.
        """
        
        # Step 1: Local Classification
        intent: IntentResult = self.state_machine.classify(user_input)
        
        # Step 2: Hard Interrupt Check (Zero Token Cost)
        if intent.is_emergency_interrupt:
            return {
                "response": self.db.get_emergency_protocol(),
                "persona_used": "HARD_INTERRUPT",
                "api_call_made": False,
                "reason": "Emergency keyword detected locally."
            }
        
        # =====================================================
        # SECRET SAUCE INTEGRATION (All local, zero API cost)
        # =====================================================
        
        # A. SymptomWeaver: Analyze temporal patterns
        symptom_pattern = self.symptom_weaver.analyze_temporal_patterns(
            user_id=user_id,
            current_symptom=user_input  # Simple extraction; could be smarter
        )
        symptom_context = self.symptom_weaver.format_for_prompt(symptom_pattern) if symptom_pattern else ""
        
        # B. EmpathyCalibrator: Assess emotional trajectory
        emotional_state, emotion_metadata = self.empathy_calibrator.assess_emotional_trajectory(user_id)
        empathy_instruction = self.empathy_calibrator.format_for_prompt(emotional_state)
        
        # C. ContextCompressor: Compress conversation history
        compressed = self.context_compressor.compress(self.conversation_history)
        compressed_context = self.context_compressor.format_for_prompt(compressed)
        
        # D. Fetch Historical Context from DB
        historical_context = self.db.get_user_context(user_id)
        
        # =====================================================
        # TOKEN-BUDGETED PROMPT ASSEMBLY
        # =====================================================
        
        base_persona_instruction = PERSONA_PROMPTS.get(intent.persona, PERSONA_PROMPTS[Persona.GENERAL])
        
        # Allocate each section to the budgeter
        self.token_budgeter.allocate(PromptSection.PERSONA, base_persona_instruction)
        self.token_budgeter.allocate(PromptSection.SYMPTOM_PATTERN, symptom_context)
        self.token_budgeter.allocate(PromptSection.EMPATHY, empathy_instruction)
        self.token_budgeter.allocate(PromptSection.HISTORY, historical_context)
        self.token_budgeter.allocate(PromptSection.CONVERSATION, compressed_context)
        
        # Add legal disclaimers (Phase 3 module - stubbed here for now)
        disclaimer = "[LEGAL: I am an AI assistant, not a doctor. This is not medical advice.]"
        self.token_budgeter.allocate(PromptSection.DISCLAIMERS, disclaimer)
        
        # Optimize: Sacrifice low-priority content if over budget
        sacrificed = self.token_budgeter.optimize()
        
        # Assemble final prompt from budgeted sections
        final_system_prompt = self.token_budgeter.assemble_final_prompt()
        
        # Append user input to conversation history for next turn
        self.conversation_history.append({"role": "user", "content": user_input})

        # Step 5: The Single API Call
        # Alex: This is where the money is spent. Ensure the prompt above is tight.
        self.total_api_calls += 1
        
        # Constructing the message payload for the generic client
        messages = [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        # Making the call
        # TODO: Jamie - Add retry logic with exponential backoff here if the API flakes.
        try:
            ai_response = self.api_client.call(messages=messages)
        except Exception as e:
            # Fallback if API dies
            ai_response = f"[SYSTEM ERROR: Connection to health AI failed. Error: {str(e)}]"
        
        # Store assistant response in history
        self.conversation_history.append({"role": "assistant", "content": ai_response})

        return {
            "response": ai_response,
            "persona_used": intent.persona.value,
            "intent_confidence": intent.confidence,
            "matched_keywords": intent.keywords_matched,
            "api_call_made": True,
            "total_api_calls": self.total_api_calls,
            "emotional_state": emotional_state.value,
            "symptom_pattern_detected": bool(symptom_pattern),
            "compression_ratio": compressed.compression_ratio if compressed else 1.0,
            "token_budget_report": self.token_budgeter.get_budget_report(),
            "sacrificed_sections": sacrificed
        }

# ==============================================================================
# MOCK API CLIENT FOR TESTING
# In production, this wraps the actual SDK (OpenAI, Anthropic, etc.)
# ==============================================================================
class MockSingleAPIClient:
    """
    Simulates the external AI provider. 
    We only allow ONE call per request.
    """
    def call(self, messages: list[dict]) -> str:
        # Extract system prompt to see which persona was picked (for logging)
        system_msg = next((m['content'] for m in messages if m['role'] == 'system'), "")
        user_msg = next((m['content'] for m in messages if m['role'] == 'user'), "")
        
        # Fake logic to verify persona injection worked
        if "Triage" in system_msg:
            return "I understand you are experiencing symptoms. Can you tell me more about the severity and when it started? Please note, I am an AI, not a doctor."
        elif "Empath" in system_msg:
            return "That sounds incredibly draining. It's completely valid to feel overwhelmed when dealing with health issues. How have you been coping lately?"
        elif "Analyst" in system_msg:
            return "Looking at the data trends you've described, there seems to be a correlation. Have you tracked these values over the last month?"
        else:
            return "Here is some general information about that topic. Remember to consult a professional for specific advice."

if __name__ == "__main__":
    # Simple CLI test harness
    print("--- PulseWeaver Prism Router (Phase 1) ---")
    router = PrismRouter(MockSingleAPIClient())
    
    test_cases = [
        ("I think I'm having a heart attack, chest pain is crushing", "emergency_test"),
        ("I want to end it all", "suicide_interrupt_test"),
        ("I'm just so sad and tired all the time", "empath_test"),
        ("My blood work came back with high A1C", "analyst_test"),
        ("What's the weather like?", "general_test")
    ]
    
    for query, label in test_cases:
        print(f"\n[TEST: {label}] User: {query}")
        result = router.route_and_respond(query, user_id="u_123")
        print(f"-> Persona: {result['persona_used']}")
        print(f"-> API Called: {result['api_call_made']}")
        print(f"-> Response: {result['response'][:80]}...")
