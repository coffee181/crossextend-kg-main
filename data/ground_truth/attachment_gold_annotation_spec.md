# Attachment Gold Annotation Specification

## Purpose

This document defines the annotation standard for attachment gold labels.
Both human annotators and the preprocessing LLM pipeline must follow these rules
so that gold labels and pipeline outputs are directly comparable.

## General Principle

Extract every meaningful noun phrase that can serve as an independent, queryable
concept in the knowledge graph. Apply the normalization rules below **consistently**
so that the same real-world entity always produces the same label.

---

## Normalization Rules

### 1. Singular Form

Always use the **singular** form of the label.

| Original text | Normalized label |
|---|---|
| cracks | crack |
| heat spots | heat spot |
| retaining tabs | retaining tab |
| busbar edges | busbar edge |
| foam barriers | foam barrier |
| cover ribs | cover rib |
| stud exits | stud exit |
| rub marks | rub mark |
| trimmed openings | trimmed opening |
| missing tabs | missing tab |
| brass tube necks | brass tube neck |

### 2. No Leading Articles

Remove "the", "a", "an" from the beginning of labels.

| Original text | Normalized label |
|---|---|
| the shield edge | shield edge |
| a failed tab | failed tab |

### 3. Lowercase

All labels are **lowercase** for matching purposes. Display labels may retain
original casing, but the canonical `label` field must be lowercase.

### 4. Named Entities Keep Original Casing and IDs

Proper names and alphanumeric identifiers are preserved exactly as written.

| Original text | Normalized label |
|---|---|
| Velorian ModuleShield-584 | Velorian ModuleShield-584 |
| Kestrel VMC-850 | Kestrel VMC-850 |
| Helion PackLine-327 EV | Helion PackLine-327 EV |
| HC-S1 | HC-S1 |
| CL-R1 | CL-R1 |
| PC-RC1 | PC-RC1 |

### 5. Merge Exact Synonyms Within One Document

If the same real-world entity appears with different wordings in the same
document, use the **more specific** variant as the canonical label and mark
the other as a surface form alias. Only create **one** gold entry.

| Variant 1 | Variant 2 | Canonical label |
|---|---|---|
| stand-off | loss of stand-off | loss of stand-off |
| crack | cracked shield panel | cracked shield panel |
| missing tab | missing retaining tab | missing retaining tab |
| shield | busbar shield | busbar shield |

**Rule**: if one variant fully contains the meaning of the other and adds
specificity, keep the specific one. If they are truly different entities
(e.g., "crack" as a phenomenon vs "cracked shield panel" as a specific fault
instance), keep both.

### 6. Do Not Extract These

Exclude the following categories entirely:

| Category | Example | Reason |
|---|---|---|
| Enumeration context | "electrical event, dropped-tool incident, or routine service access" | These are context setting, not independent entities |
| Procedure meta | "the note names the exact concern" | Instructional text, not an entity |
| Vague placeholders | "the exact concern", "the same repaired branch" | Not a reusable concept |
| Person names | — | Provenance, not graph nodes |
| Document titles | — | Provenance, not graph nodes |

### 7. Compound Nouns Stay Intact

Do not split compound technical terms.

| Original text | Correct | Wrong |
|---|---|---|
| O-ring land | O-ring land | ~~O-ring~~, ~~land~~ |
| busbar shield | busbar shield | ~~busbar~~, ~~shield~~ |
| worm-drive clamp | worm-drive clamp | ~~worm~~, ~~drive~~, ~~clamp~~ |
| quick connector | quick connector | ~~quick~~, ~~connector~~ |

---

## Anchor Assignment Rules

Each extracted concept must be assigned to exactly one of the 15 backbone concepts:

| Backbone | Scope | Typical Members |
|---|---|---|
| **Asset** | Named top-level equipment | machine, vehicle, pack, cabinet, line |
| **Component** | Physical hardware parts | bracket, hose, manifold, bead, neck, seat, panel, shield, tube, clip, fitting, block, tray, rail, cover, shell |
| **Signal** | Observable evidence or measurement target | wetting, residue, mark, level, depth, path, boundary, odor, witness, reading, condition (inspection dimension) |
| **State** | Concluded or verified status | dry condition, full insertion, flush and symmetric, neutral state, acceptance state |
| **Fault** | Defect or failure mode | crack, scoring, flattening, leak, missing, mis-seated, interference, failure, loss |
| **Seal** | Seal interfaces and components | O-ring, O-ring land, O-ring seat, O-ring track, sealing land, gasket |
| **Connector** | Electrical/fluid connectors | quick connector, latch window, terminal, splice, junction |
| **Sensor** | Measurement devices | temperature sensor, pressure sensor, NTC, Hall sensor |
| **Controller** | Control electronics | BMS controller, motor controller, inverter, PLC, gateway |
| **Coolant** | Coolant fluid and pathway | coolant hose, cooling branch, drain path, chiller branch, refrigerant line |
| **Actuator** | Actuation devices | contactor, relay, solenoid, valve, pump, motor, brake |
| **Power** | Power distribution | HV bus, DC-DC converter, fuse, MSD, precharge circuit, OBC |
| **Housing** | Structural enclosures | enclosure, case, cover, tray, shield (structural), bracket (structural), mount, bushing |
| **Fastener** | Fastening hardware | bolt, nut, washer, stud, clip, retainer, screw, rivet, clamp, tab |
| **Media** | Fluids and gases | refrigerant gas, oil, grease, lubricant, dielectric fluid, air, nitrogen |

### Ambiguity Resolution

When a concept fits multiple backbones:

1. **Seal > Component**: If the concept is a seal interface (O-ring land, sealing land),
   use **Seal** not Component.
2. **Connector > Component**: If the concept is a connector feature (latch window,
   quick connector), use **Connector** not Component.
3. **Coolant > Component**: If the concept is a coolant pathway (coolant hose,
   return hose), use **Coolant** not Component.
4. **Fastener > Component**: If the concept is a fastening feature (clamp, clip,
   retaining tab, worm-drive clamp), use **Fastener** not Component.
5. **Housing > Component**: If the concept is a structural enclosure or cover
   (shield, tray, manifold casting), use **Housing** not Component.
6. **Fault > State**: "loss of stand-off" is a Fault (something wrong), not a State
   (normal condition).
7. **Signal > State**: "clamp position" is a Signal (measured dimension), not a State
   (concluded status). The test: can you measure it? → Signal. Is it a conclusion? → State.

---

## Annotation Format

```json
{
  "schema_version": "attachment_gold.v2",
  "annotation_policy": "See attachment_gold_annotation_spec.md for full rules.",
  "domain": "battery",
  "source_doc": "Battery_Module_Busbar_Insulator_Shield_Inspection",
  "backbone_concepts": ["Asset", "Component", "Signal", "State", "Fault",
    "Seal", "Connector", "Sensor", "Controller", "Coolant", "Actuator",
    "Power", "Housing", "Fastener", "Media"],
  "gold_attachments": [
    {
      "label": "busbar shield",
      "surface_form": "busbar shield",
      "parent_anchor": "Housing",
      "accept": true,
      "rationale": "Insulating shield covering the busbar — structural housing/cover"
    }
  ],
  "_statistics": {
    "total_concepts": 0,
    "accepted": 0,
    "rejected": 0,
    "anchor_distribution": {}
  }
}
```

### Field Definitions

| Field | Required | Description |
|---|---|---|
| `label` | yes | Normalized canonical label (singular, lowercase, compound intact) |
| `surface_form` | yes | The exact text as it appears in the source document |
| `parent_anchor` | yes | One of the 15 backbone concepts |
| `accept` | yes | Always `true` for v2 (we annotate what should be extracted) |
| `rationale` | yes | One-line justification for the anchor choice |

---

## Annotation Process

1. Read the source document step by step.
2. For each step, identify every noun phrase that names a component, signal,
   state, fault, or other backbone-grounded entity.
3. Apply normalization rules 1–6 to produce the canonical label.
4. Assign the parent anchor using the anchor assignment rules.
5. Write a one-line rationale.
6. Do NOT look at pipeline outputs, model outputs, or experiment results.
7. After annotation, verify `_statistics` counts match the actual entries.
