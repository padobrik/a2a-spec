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
      threshold: 0.8

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
| `embedding_similarity` | Cosine similarity between embeddings |
| `entailment` | NLI-based entailment checking |
| `language_detection` | Verify output language |

## Policy Rules

| Method | Description |
|--------|-------------|
| `regex` | Match forbidden patterns (PII, profanity) |
| `custom` | Run a custom Python validator function |

## Best Practices

1. Start with structural specs — they're fast and free
2. Add semantic rules for text fields that can vary in wording
3. Use policies for hard safety requirements
4. Keep specs focused — one spec per producer-consumer pair
