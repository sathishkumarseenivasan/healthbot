# PulseWeaver Secret Sauce Modules 🚀

> **The differentiators. The stuff that makes investors lean in.**  
> *No generic RAG. No multi-agent chatter. Just pure, token-efficient magic.*

## Overview

While other health chatbots are burning tokens on agent-to-agent debates and vector database lookups, PulseWeaver uses **four proprietary local modules** to enhance intelligence WITHOUT additional API calls.

These modules run BEFORE the single API call, assembling the perfect prompt every time.

---

## 🧵 Module 1: SymptomWeaver

### What It Does
Unlike basic RAG that retrieves "similar" chunks, the **SymptomWeaver analyzes TEMPORAL RELATIONSHIPS** between symptoms over time.

**Basic RAG says:**  
> "User mentioned headache."

**SymptomWeaver says:**  
> "User's headache has migrated from frontal to occipital over 3 days, correlating with increased stress events on Day 2."

### How It Works
1. Queries SQLite for all instances of the current symptom
2. Finds co-occurring symptoms within 48-hour windows
3. Calculates severity trends (increasing/decreasing/stable)
4. Extracts contextual triggers from notes
5. Formats into a 40-token natural language summary

### Key Methods
```python
weaver = SymptomWeaver(db_path="health_graph.db")

# Analyze temporal patterns
cluster = weaver.analyze_temporal_patterns(
    user_id="u_123",
    current_symptom="headache"
)

# Format for prompt injection
prompt_text = weaver.format_for_prompt(cluster)
# Output: "HISTORICAL PATTERN: headache tracked over 3 days. 
#          Trend: increasing. Often co-occurs with: stress, fatigue.
#          Potential triggers: tired, after."
```

### Token Efficiency
- **Before:** 150+ tokens for raw history dump
- **After:** 40 tokens for synthesized insight
- **Savings:** 73% reduction

### Known Issues
- TODO: Sarah - Replace keyword-based trigger detection with actual NLP when budget allows
- BUG: Sometimes misses symptoms spelled slightly differently ("headake" vs "headache")

---

## 💝 Module 2: EmpathyCalibrator

### What It Does
Most chatbots have a static "empathetic" persona. Ours **CALIBRATES empathy dynamically** based on the user's emotional trajectory over time.

### Detection Signals
| Signal | What It Means |
|--------|---------------|
| High message frequency (10+ in 24h) | Anxiety indicator |
| Symptom repetition (same symptom 3+ times) | Rumination pattern |
| Late-night activity (midnight-5am) | Higher distress probability |
| Severity escalation | Urgent attention needed |

### Emotional States
```python
class EmotionalState(Enum):
    NEUTRAL           # Balanced, standard empathy
    ANXIOUS           # Elevated reassurance needed
    DISTRESSED        # High empathy, simplified info
    URGENT            # Minimal empathy, action-focused
    CHRONIC_CONCERN   # Sustained warmth, long-term acknowledgment
```

### Prompt Injection
The calibrator compresses tone instructions into ~25 tokens:

```
EMPATHY MODE: extra reassurance. User shows signs of anxiety. 
Be reassuring. Validate concerns before providing information.
```

### Author Note
> *"I cried testing this on my own data. It works."* — Sarah

### Token Efficiency
- **Previous version:** 200 tokens for empathy instructions
- **Current version:** 25 tokens (ultra-compressed format)
- **Savings:** 87.5% reduction

---

## 💰 Module 3: TokenBudgeter

### What It Does
Enforces a **STRICT token budget** across all components of the system prompt. If we exceed the budget, it SACRIFICES lower-priority content.

Yes, it will delete your beautiful prose to save money. That's its job.

### Budget Allocation (Default: 800 tokens)
| Section | Max Tokens | Priority | Sacrifice Order |
|---------|-----------|----------|-----------------|
| Persona | 100 | 1 (Highest) | Last |
| Disclaimers | 80 | 2 | 2nd-to-last |
| History | 150 | 3 | Middle |
| Symptom Pattern | 70 | 3 | Middle |
| Empathy | 60 | 4 | Early |
| Conversation | Remainder | 5 (Lowest) | First |

### Key Features
```python
budgeter = TokenBudgeter(total_budget=800)

# Allocate content (auto-truncates if over limit)
budgeter.allocate(PromptSection.PERSONA, persona_text)
budgeter.allocate(PromptSection.HISTORY, history_text)

# Optimize: Sacrifice low-priority sections if over budget
sacrificed = budgeter.optimize()
# Returns: ["conversation", "empathy"] if those were cut

# Assemble final prompt
final_prompt = budgeter.assemble_final_prompt()

# Get detailed report
report = budgeter.get_budget_report()
# {
#   "total_budget": 800,
#   "total_used": 623,
#   "remaining": 177,
#   "utilization_percent": 77.88,
#   "by_section": {...}
# }
```

### Author Note
> *"I wrote this at 3 AM after seeing our AWS bill. Never again."* — David

### Why Word-Based Counting?
We use a simple word-based estimator instead of the official tokenizer:
- **Official tokenizer:** +50ms latency per call
- **Word estimator:** <1ms latency
- **Trade-off:** ~10% accuracy loss, but 50x faster

At 10,000 requests/day, that's 500 seconds saved. Math.

---

## 🗜️ Module 4: ContextCompressor

### What It Does
Uses a **sliding window + extractive summarization** approach to compress conversation history without losing medical entities.

### Compression Strategy
1. **Keep last 3 messages verbatim** (recency matters)
2. **Summarize older messages** into bullet points
3. **Preserve ALL medical entities** (symptoms, severities, medications)
4. **Discard filler** ("thanks!", "you're welcome", "how are you")

### Example Compression

**Original (9 messages, ~120 tokens):**
```
User: I have a headache
Assistant: How severe is the headache?
User: It's pretty bad, like 7/10
Assistant: How long has it lasted?
User: About 3 days now
Assistant: Any other symptoms?
User: Feeling nauseous too
Assistant: Thanks for sharing. Anything else?
User: No that's all thanks
```

**Compressed (~45 tokens):**
```
CONVERSATION SUMMARY:
- I have a headache
- It's pretty bad, like 7/10
- About 3 days now

KEY MEDICAL ENTITIES: headache (symptom), 7/10 (severity), 3 days (duration), nauseous (symptom)

RECENT EXCHANGE:
  [1] Feeling nauseous too
  [2] No that's all thanks
```

**Compression Ratio:** 2.67x

### Medical Entity Preservation
The compressor NEVER loses these entities during compression:
- Symptoms (headache, fever, pain, nausea, etc.)
- Severities (severe, mild, 7/10, worst ever)
- Medications (ibuprofen, tylenol, metformin)
- Durations (3 days, 2 weeks, months)
- Body parts (chest, head, stomach, back)

### Authors
> *Alex + Sarah (pair-programmed during a thunderstorm)*

### Known Bugs
- Sometimes keeps too many "how are you" exchanges
- Filler pattern list needs expansion based on real user data

---

## 🔌 Integration with Prism Router

All four modules integrate seamlessly into the `PrismRouter.route_and_respond()` method:

```python
from pulseweaver import PrismRouter, MockSingleAPIClient

# Initialize router (Secret Sauce modules auto-loaded)
router = PrismRouter(api_client=MockSingleAPIClient())

# Process user input
result = router.route_and_respond(
    user_input="My headache is getting worse",
    user_id="u_123"
)

# Access Secret Sauce metadata
print(f"Emotional State: {result['emotional_state']}")
print(f"Symptom Pattern: {result['symptom_pattern_detected']}")
print(f"Compression Ratio: {result['compression_ratio']}x")
print(f"Token Budget: {result['token_budget_report']['utilization_percent']}% used")
print(f"Sacrificed Sections: {result['sacrificed_sections']}")
```

### Execution Flow
```
User Input
    ↓
Hard Interrupt Check (bypasses everything if emergency)
    ↓
┌─────────────────────────────────────┐
│ SECRET SAUCE (All Local, $0 Cost)  │
├─────────────────────────────────────┤
│ 1. SymptomWeaver → temporal insight │
│ 2. EmpathyCalibrator → tone adjust  │
│ 3. ContextCompressor → history sum  │
│ 4. TokenBudgeter → allocate & trim  │
└─────────────────────────────────────┘
    ↓
Assemble Final Prompt (budget-managed)
    ↓
SINGLE API CALL ($$$)
    ↓
Response + Metadata
```

---

## 📊 Performance Metrics

| Metric | Without Secret Sauce | With Secret Sauce | Improvement |
|--------|---------------------|-------------------|-------------|
| Avg tokens per call | 1,200 | 650 | 46% reduction |
| Context relevance | Low (vector similarity) | High (temporal + entity) | 3x better |
| Empathy accuracy | Static | Dynamic | User-tested |
| Emergency response | API-dependent | Instant (local) | 2-5s faster |
| Cost per 10k queries | ~$18 | ~$9.75 | 46% savings |

*Based on internal testing with 500 synthetic conversations. Your mileage may vary.*

---

## 🛠️ Extending the Secret Sauce

### Adding New Entity Types
Edit `ContextCompressor.entity_patterns`:
```python
self.entity_patterns["lab_value"] = r'\b(A1C|hemoglobin|cholesterol)\s*[:=]?\s*\d+\b'
```

### Adjusting Budget Allocations
```python
# Give history more tokens, less to conversation
budgeter = TokenBudgeter(total_budget=1000)
budgeter.allocations[PromptSection.HISTORY].max_tokens = 250
budgeter.allocations[PromptSection.CONVERSATION].max_tokens = 500
```

### Custom Emotional States
Add to `EmpathyCalibrator`:
```python
class EmotionalState(Enum):
    # ... existing states ...
    MANIC = "manic"  # High energy, rapid messages

# Then add handling in get_persona_modifiers()
```

---

## ⚠️ Real Talk: Limitations

1. **Not True AI Understanding**: These are rule-based systems. They don't "understand" emotions or symptoms—they match patterns.

2. **Language Assumption**: All regex patterns assume English. Non-English users will get degraded performance.

3. **Entity Extraction Gaps**: Our entity patterns are hand-crafted. We'll miss rare medications or unconventional symptom descriptions.

4. **Budget Trade-offs**: When the budgeter sacrifices sections, you lose context. Sometimes it cuts the wrong thing.

5. **No Learning**: The system doesn't learn from mistakes. If it misclassifies empathy once, it'll do it again.

---

## 📝 TODO List

- [ ] **David**: Hook token budget reports up to a dashboard for real-time burn rate monitoring
- [ ] **Sarah**: Expand filler phrase patterns based on real user conversation logs
- [ ] **Alex**: Replace keyword trigger detection in SymptomWeaver with lightweight NLP
- [ ] **Elena**: Review if disclaimer allocation (80 tokens) is sufficient for legal compliance
- [ ] **Team**: Add support for non-English entity patterns (Spanish first?)
- [ ] **Jamie**: Test compression ratios on conversations with 50+ messages

---

## 🎯 Why This Matters

Competitors are building multi-agent frameworks where:
- Agent 1 classifies intent (API call #1)
- Agent 2 retrieves context (API call #2)
- Agent 3 debates the response (API call #3)
- Agent 4 formats the output (API call #4)

**We make ONE call.**

Our Secret Sauce modules run locally, cost nothing, and assemble the perfect prompt before we spend a single token.

That's not just efficiency. That's survival.

---

*Last Updated: March 2026*  
*Team PulseWeaver - Building health AI that doesn't burn cash* ❤️‍🩹
