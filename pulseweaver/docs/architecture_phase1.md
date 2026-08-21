# PulseWeaver Architecture: Phase 1 (Prism Router)

## Flow Diagram

```mermaid
flowchart TD
    A[User Input] --> B{Local State Machine}
    
    subgraph LocalProcessing ["🟢 LOCAL PROCESSING (Zero Token Cost)"]
        B -->|Regex & Keyword Match| C{Intent Classification}
        C -->|Emergency Keywords<br/>suicide, chest pain| D[HARD INTERRUPT]
        C -->|Symptom Keywords<br/>fever, pain, rash| E[Persona: TRIAGE]
        C -->|Emotional Keywords<br/>sad, anxious, tired| F[Persona: EMPATH]
        C -->|Data Keywords<br/>lab results, mg/dl| G[Persona: ANALYST]
        C -->|No Match| H[Persona: GENERAL]
        
        D --> I[Return Hardcoded<br/>Emergency Protocol]
    end
    
    subgraph ContextAssembly ["🔵 CONTEXT ASSEMBLY"]
        E --> J[Fetch User History<br/>from Longitudinal Graph DB]
        F --> J
        G --> J
        H --> J
        
        J --> K[Assemble Final System Prompt<br/>Persona Instructions + User Context]
    end
    
    subgraph APICall ["🔴 SINGLE API CALL (Token Cost Incurred)"]
        K --> L[Construct Messages Array<br/>System Prompt + User Input]
        L --> M{{EXTERNAL AI API}}
        M --> N[Receive Response]
    end
    
    I --> O[Final Response to User]
    N --> O
    
    style LocalProcessing fill:#e8f5e9,stroke:#2e7d32
    style ContextAssembly fill:#e3f2fd,stroke:#1565c0
    style APICall fill:#ffebee,stroke:#c62828
    style D fill:#ff5722,color:white
    style M fill:#ff9800,color:black
```

## Key Metrics

| Stage | Token Cost | Latency | Purpose |
|-------|-----------|---------|---------|
| **State Machine** | 0 | <5ms | Classify intent locally using regex |
| **Hard Interrupt** | 0 | <10ms | Return emergency info without API call |
| **Context Fetch** | 0 | ~50ms* | Retrieve user history from local DB |
| **API Call** | $$$ | ~1-3s | Single LLM inference with injected persona |

*\*Will be faster with proper indexing in Phase 2*

## Design Decisions

1. **Why Local Regex?** 
   - Alex: "We can't afford to burn tokens on classification. Regex is free and deterministic."

2. **Why Hard Interrupts?**
   - Legal requirement: Emergency responses must be immediate and vetted, not hallucinated by an LLM.
   - Saves money: Zero token cost for life-saving protocols.

3. **Why Single Persona Injection?**
   - Jamie: "Multi-agent frameworks like AutoGen are cool, but they chat with each other. That's 10+ API calls per user message. We do ONE."

## TODOs & Known Issues

- [ ] **David**: Move regex patterns to config file for hot-reloading
- [ ] **Sarah**: Expand keyword lists based on beta user logs
- [ ] **Alex**: Implement sliding window for context injection (token limit concerns)
- [ ] **Jamie**: Add retry logic with exponential backoff for API calls
- [ ] **Team**: REAL TALK - The General persona fallback needs better handling for out-of-domain queries
