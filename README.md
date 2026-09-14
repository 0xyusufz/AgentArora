# AgentArora

## Privacy-Preserving Browser Agent

**Smart India Hackathon 2026**<br>
**Problem Statement ID:** 26171<br>
**Theme:** Smart Automation

---

## Overview

AgentArora is a **privacy-preserving browser agent** designed to perform web-based tasks while minimizing unnecessary exposure of sensitive and personally identifiable information (PII).

The system combines webpage structure, accessibility information, and visual context to understand the current browser state. Sensitive information is detected and protected locally before the information required for reasoning is passed to the agent. The agent then generates validated browser actions and interacts with the webpage to complete the user's task.

The project follows a privacy-by-construction principle:

> **Provide the reasoning system with the minimum information necessary to complete the task while protecting sensitive user information locally.**

---

## Problem

Browser automation agents generally require access to webpage content and user interface information to understand and execute tasks.

However, modern webpages frequently contain sensitive information such as:

- Names and contact information
- Account and payment information
- Authentication information
- Private communications
- Medical or confidential information
- Other personally identifiable information

Sending complete webpage content or screenshots to a reasoning system can therefore expose information that is irrelevant to the requested task.

AgentArora addresses this problem by introducing a local privacy layer between webpage perception and AI reasoning.

---

## Solution

AgentArora processes browser information locally and separates **what the webpage contains** from **what the reasoning system actually needs to know**.

The overall workflow is:

User Task
→ Screen / Webpage Understanding
→ Sensitive Data Detection
→ Redaction / Protection
→ Sanitized Representation
→ AI Reasoning
→ Action Validation
→ Browser Execution
→ Observe Result
→ Continue / Complete Task

The system is designed so that sensitive information can be represented through safe placeholders while preserving the surrounding context required for task execution.

Example:

Original:
Account Number: 7845129034
Balance: ₹84,250
Latest Transaction: Amazon — ₹2,340

Sanitized:
Account Number: [ACCOUNT_01]
Balance: [MONEY_01]
Latest Transaction: Amazon — [MONEY_02]

Useful contextual information remains available while the original sensitive values are protected.

---

## Key Features

### Privacy-Preserving Perception

The browser state is represented using structured webpage and accessibility information together with visual context where required.

### Local Sensitive-Data Detection

Sensitive and personally identifiable information is detected before unnecessary exposure to the reasoning layer.

### Safe Redaction

Sensitive values are replaced with controlled placeholders while preserving useful context.

### Opaque Element Identification

Webpage elements are represented using temporary opaque identifiers such as:

EL_001
EL_002
EL_003

These identifiers do not encode the semantic meaning or sensitive content of the underlying element.

### Structured Browser Actions

The reasoning system produces explicit browser actions rather than unrestricted browser commands.

Initial supported actions include:

CLICK
TYPE
SCROLL
SELECT
PRESS_KEY
WAIT

### Action Validation

Generated actions are validated before execution to prevent malformed, unsupported, or unsafe operations.

### Untrusted Webpage Content

Webpage content is treated as untrusted input and cannot override system-level privacy or execution policies.

### Continuous Task Execution

The agent follows an observation and action loop:

Observe → Reason → Act → Observe → Reason → ...

The loop terminates when the task is successfully completed or a defined execution limit is reached.

---

## System Architecture

User Task
↓
Browser / Page
↓
Page Perception
↓
PageState
↓
Privacy Layer
↓
SanitizedPageState
↓
AI Reasoning
↓
ActionPlan
↓
Action Policy & Validation
↓
Browser Action
↓
ActionResult
↓
Next Step

---

## Privacy Boundary

The privacy boundary is one of the central design principles of the system.

Raw PageState
↓
Sensitive Data Detection
↓
Redaction / Sanitization
↓
SanitizedPageState
↓
AI Reasoning

The reasoning system should not receive the original sensitive-value mapping.

Only the sanitized representation required for the current task should enter the reasoning context.

---

## Data Contracts

The system uses structured contracts to maintain predictable communication between components.

### PageState

Represents the current webpage state, including information such as:

- Page metadata
- Visible text
- Element identifiers
- Roles
- Labels
- Visibility
- Enabled state
- Bounds
- Other required contextual information

Element identifiers use an opaque format such as `EL_001`.

### SanitizedPageState

Represents the privacy-processed version of `PageState`.

Sensitive values are replaced or protected while useful non-sensitive context is preserved.

### ActionPlan

Represents a structured browser action generated by the reasoning layer.

Example:

```json
{
  "action": "CLICK",
  "target_element_id": "EL_017",
  "reason": "Open the Transactions section"
}
```
