# Writing Specs

A spec defines the contract between a **producer** agent and a **consumer** agent.

## Spec File Structure

```yaml
spec:
  name: triage-to-resolution      # Unique name
  version: "1.0"                   # Spec version
  producer: triage-agent           # Agent producing the output
  consumer: resolution-agent       # Agent consuming the output
  description: "What resolution expects from triage"

  structural:                      # JSON Schema validation
    type: object
    required: [category, summary]
    properties:
      category:
        type: string
        enum: [billing, shipping, product, general]
      summary:
        type: string
        minLength: 10

  semantic:                        # Meaning-based validation
    - rule: summary_reflects_input
      method: embedding_similarity
      threshold: 0.5
      source_field: message        # field in the agent's input
      target_field: summary        # field in the agent's output

  policy:                          # Hard rules (pass/fail)
    - rule: no_pii
      method: regex
      patterns:
        - '\b\d{3}-\d{2}-\d{4}\b'  # SSN pattern
```

## Structural Spec

Uses JSON Schema (Draft 7) to validate output structure. Supports:

- `type`, `required`, `properties`
- `enum`, `minLength`, `maxLength`
- `minimum`, `maximum`
- Nested objects

## Semantic Rules

| Method | Description |
|--------|-------------|
| `embedding_similarity` | Cosine similarity between `input[source_field]` and `output[target_field]` |
| `entailment` | Not implemented yet — a rule using it fails |
| `language_detection` | Not implemented yet — a rule using it fails |

`handshake test` evaluates semantic rules against each snapshot's recorded input
and output. It requires `pip install agent-handshake[semantic]`; pass `--no-semantic`
(or set `semantic.enabled: false` in `handshake.yaml`) to skip them.

Calibrate thresholds on real outputs. With the default `all-MiniLM-L6-v2`
model, faithful summaries of a short message typically score 0.6–0.8 and
off-topic ones around 0.3, so `0.8` is usually too strict for
input-to-summary comparisons.

## Policy Rules

| Method | Description |
|--------|-------------|
| `regex` | Match forbidden patterns (PII, profanity) |
| `custom` | Run a custom Python validator function |

A `custom` rule names its function by dotted path. The module is imported
from the directory you run `handshake` in, so a file in your project works:

```yaml
policy:
  - rule: no_refund_promise
    method: custom
    validator: checks.no_refund_promise   # checks.py: def no_refund_promise(output, input_data)
```

The function returns `(passed, detail)`. The built-in validators work the
same way: `agent_handshake.policy.builtin.no_pii_in_output` and
`agent_handshake.policy.builtin.output_not_empty`.

## Best Practices

1. Start with structural specs — they're fast and free
2. Add semantic rules for text fields that can vary in wording
3. Use policies for hard safety requirements
4. Keep specs focused — one spec per producer-consumer pair
