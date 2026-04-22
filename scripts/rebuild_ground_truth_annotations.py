#!/usr/bin/env python3
"""Rebuild source-grounded annotation files under data/ground_truth.

This script enforces a conservative annotation policy:
- document-level gold files contain only task_dependency and structural relations
- communication / propagation / multi-hop / lifecycle are maintained separately
- all labels are derived from the raw O&M markdown, not from pipeline outputs
"""

from __future__ import annotations

import json
import re
import shutil
import textwrap
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH_DIR = ROOT / "data" / "ground_truth"
TEMPLATE_DIR = GROUND_TRUTH_DIR / "template"
DATE = "2026-04-21"
DOC_ANNOTATION_BASIS = (
    "Blind re-annotation from source O&M text only. The annotator did not consult "
    "pipeline outputs, evaluation results, or intermediate artifacts. Task labels "
    "follow the document step ids; concept labels prefer source wording when possible. "
    "Document-level gold relations are limited to step dependencies and explicit "
    "structural containment."
)
SUPPORT_ANNOTATION_BASIS = (
    "Blind support annotation from source O&M text only. Pairs, chains, questions, "
    "and lifecycle events were curated without consulting model outputs. When source "
    "support was weak, the item was omitted instead of guessed."
)
TIMESTAMP_POLICY = (
    "Synthetic relative timestamps encode manual procedure order only. They are not "
    "real-world event dates and must not be interpreted as operational history."
)
STEP_PATTERN = re.compile(r"^\|\s*(T\d+)\s*\|\s*(.*?)\s*\|\s*$")
LIFECYCLE_EVENT_TYPES = {
    "creation",
    "update",
    "deprecation",
    "replacement",
    "fault_occurrence",
    "maintenance",
}


@dataclass(frozen=True)
class DocSpec:
    filename: str
    domain_id: str
    doc_id: str
    source_relpath: str
    asset_label: str
    description: str
    components: list[str]
    signals: list[str]
    faults: list[str]
    negatives: list[str] = field(default_factory=list)
    negative_reason_overrides: dict[str, str] = field(default_factory=dict)
    structural_relations: list[tuple[str, str]] = field(default_factory=list)


DOC_SPECS: list[DocSpec] = [
    DocSpec(
        filename="battery_BATOM_001.json",
        domain_id="battery",
        doc_id="BATOM_001",
        source_relpath="data/battery_om_manual_en/BATOM_001.md",
        asset_label="Aurex BatteryHub-612 LR",
        description="Outlet leak mapping and repair verification",
        components=[
            "left-rear coolant-plate outlet",
            "aluminum outlet neck",
            "PA12 quick-connector shell",
            "green EPDM O-ring seat",
            "stainless retainer clip",
            "hose saddle bracket",
            "latch window",
            "tube bead",
        ],
        signals=[
            "seepage",
            "dried residue",
            "undertray drip",
            "as-found stain path",
            "applied pressure",
            "time to first wetting",
            "inlet and outlet temperatures",
            "local shell condition",
        ],
        faults=[
            "cracked connector shell",
            "saddle bracket side load",
            "retainer clip engagement",
        ],
        negatives=["pack serial"],
        negative_reason_overrides={
            "pack serial": "Recordkeeping metadata, not a stable domain concept for graph evaluation."
        },
        structural_relations=[
            ("Aurex BatteryHub-612 LR", "left-rear coolant-plate outlet"),
            ("left-rear coolant-plate outlet", "aluminum outlet neck"),
            ("left-rear coolant-plate outlet", "PA12 quick-connector shell"),
            ("left-rear coolant-plate outlet", "green EPDM O-ring seat"),
            ("left-rear coolant-plate outlet", "stainless retainer clip"),
            ("left-rear coolant-plate outlet", "hose saddle bracket"),
            ("PA12 quick-connector shell", "latch window"),
            ("aluminum outlet neck", "tube bead"),
        ],
    ),
    DocSpec(
        filename="battery_BATOM_002.json",
        domain_id="battery",
        doc_id="BATOM_002",
        source_relpath="data/battery_om_manual_en/BATOM_002.md",
        asset_label="Helion PackCore-544 AWD",
        description="Front manifold seal-boundary inspection and repair",
        components=[
            "front manifold face",
            "composite manifold body",
            "M6 retaining bolts",
            "steel inserts",
            "upper hose neck",
            "lower hose neck",
            "perimeter O-ring channel",
            "EPDM O-ring",
            "aluminum seal land",
            "header plate",
            "bolt stack",
            "NTC loom",
        ],
        signals=[
            "coolant odor",
            "slow level loss",
            "wetness after recent manifold removal",
            "manifold-side residue pattern",
            "bolt witness paint",
            "flange gap",
            "dried coolant crystals",
            "flange stand-off",
            "NTC temperature trend",
            "dry condition",
            "thermal behavior",
        ],
        faults=[
            "twisted perimeter O-ring",
            "warped composite flange",
            "insert pull-up",
            "overlength bolt stack",
            "hose-side preload",
        ],
        negatives=["service history"],
        negative_reason_overrides={
            "service history": "Context field for prior work, not a standalone graph concept."
        },
        structural_relations=[
            ("Helion PackCore-544 AWD", "front manifold face"),
            ("front manifold face", "composite manifold body"),
            ("front manifold face", "M6 retaining bolts"),
            ("front manifold face", "steel inserts"),
            ("front manifold face", "upper hose neck"),
            ("front manifold face", "lower hose neck"),
            ("front manifold face", "perimeter O-ring channel"),
            ("front manifold face", "aluminum seal land"),
            ("front manifold face", "header plate"),
            ("front manifold face", "bolt stack"),
            ("front manifold face", "NTC loom"),
            ("perimeter O-ring channel", "EPDM O-ring"),
        ],
    ),
    DocSpec(
        filename="battery_BATOM_003.json",
        domain_id="battery",
        doc_id="BATOM_003",
        source_relpath="data/battery_om_manual_en/BATOM_003.md",
        asset_label="Novaris ThermalPack-481",
        description="Chiller-inlet connector replacement and proof",
        components=[
            "chiller-inlet connector",
            "pack-to-chiller hose",
            "support clip",
            "tube neck",
            "quick-connector shell",
            "internal retainer",
            "green O-ring",
            "hose overmold",
            "case rib",
            "aluminum tube bead",
            "lead-in chamfer",
            "O-ring land",
        ],
        signals=[
            "as-found angle",
            "stress whitening",
            "latch-window distortion",
            "inner-retainer wear",
            "witness marks",
            "fresh wetting",
            "flow condition",
            "surface state",
            "incomplete insertion",
        ],
        faults=[
            "cracked shell",
            "broken latch ear",
            "recurring seepage",
            "bracket side load",
            "damaged neck",
        ],
        negatives=["exact operating state"],
        negative_reason_overrides={
            "exact operating state": "Operational context for reproduction, not a reusable domain node."
        },
        structural_relations=[
            ("Novaris ThermalPack-481", "chiller-inlet connector"),
            ("Novaris ThermalPack-481", "pack-to-chiller hose"),
            ("Novaris ThermalPack-481", "support clip"),
            ("Novaris ThermalPack-481", "case rib"),
            ("Novaris ThermalPack-481", "tube neck"),
            ("chiller-inlet connector", "quick-connector shell"),
            ("chiller-inlet connector", "internal retainer"),
            ("chiller-inlet connector", "green O-ring"),
            ("chiller-inlet connector", "hose overmold"),
            ("tube neck", "aluminum tube bead"),
            ("tube neck", "lead-in chamfer"),
            ("tube neck", "O-ring land"),
        ],
    ),
    DocSpec(
        filename="cnc_CNCOM_001.json",
        domain_id="cnc",
        doc_id="CNCOM_001",
        source_relpath="data/cnc_om_manual_en/CNCOM_001.md",
        asset_label="Kestrel VMC-850",
        description="Spindle chiller branch leak isolation",
        components=[
            "spindle-chiller supply hose",
            "return hose",
            "worm-drive clamps",
            "brass tube necks",
            "chiller manifold block",
            "P-clip on the rear column",
            "lower drip tray",
            "upper hose bead",
            "clamp screw housing",
            "molded hose bend",
            "upper outlet hose",
            "lower return hose",
            "column bracket",
        ],
        signals=[
            "coolant dripping from the rear column",
            "residue collecting on the lower cable tray",
            "coolant loss",
            "as-received coolant level",
            "first visible drip path",
            "static pressure result",
            "vibration load",
            "clamp position",
            "hose insertion depth",
            "wetting",
        ],
        faults=[
            "upper return-hose clamp leak",
            "clip-to-bracket side load",
            "side-loaded branch",
        ],
        negatives=["spindle speed window"],
        negative_reason_overrides={
            "spindle speed window": "Operating-condition context used for reproduction, not a stable graph node."
        },
        structural_relations=[
            ("Kestrel VMC-850", "spindle-chiller supply hose"),
            ("Kestrel VMC-850", "return hose"),
            ("Kestrel VMC-850", "worm-drive clamps"),
            ("Kestrel VMC-850", "chiller manifold block"),
            ("Kestrel VMC-850", "P-clip on the rear column"),
            ("Kestrel VMC-850", "lower drip tray"),
            ("Kestrel VMC-850", "upper outlet hose"),
            ("Kestrel VMC-850", "lower return hose"),
            ("Kestrel VMC-850", "column bracket"),
            ("chiller manifold block", "brass tube necks"),
            ("worm-drive clamps", "clamp screw housing"),
            ("upper outlet hose", "upper hose bead"),
            ("upper outlet hose", "molded hose bend"),
        ],
    ),
    DocSpec(
        filename="cnc_CNCOM_002.json",
        domain_id="cnc",
        doc_id="CNCOM_002",
        source_relpath="data/cnc_om_manual_en/CNCOM_002.md",
        asset_label="Arcline VTC-630",
        description="Drawbar clamp-stack force diagnosis and rebuild",
        components=[
            "CAT40 spindle",
            "drawbar clamp stack",
            "drawbar booster cylinder",
            "Belleville stack housing",
            "unclamp valve",
            "pressure transducer port",
            "spindle pull-force test point",
            "calibrated clamp-force gauge",
            "Belleville stack",
            "actuator linkage",
            "lower drawbar seat",
            "release-piston clearance",
        ],
        signals=[
            "tool pull-out during face milling",
            "weak unclamp feel",
            "drawbar alarm",
            "measured pull force",
            "cold and warmed values",
            "unclamp pressure",
            "drawbar movement",
            "Belleville stack height",
            "washer orientation",
            "release stroke",
            "pressure recovery",
            "holder retention",
            "fresh oil trace",
        ],
        faults=[
            "low clamp force",
            "inverted lower Belleville pair",
            "reduced stack height",
            "hydraulic short-stroke",
            "actuator-linkage misalignment",
        ],
        negatives=["cutting load"],
        negative_reason_overrides={
            "cutting load": "Job-context field used at intake, not a graph-worthy concept."
        },
        structural_relations=[
            ("Arcline VTC-630", "CAT40 spindle"),
            ("CAT40 spindle", "drawbar clamp stack"),
            ("drawbar clamp stack", "drawbar booster cylinder"),
            ("drawbar clamp stack", "Belleville stack housing"),
            ("drawbar clamp stack", "unclamp valve"),
            ("drawbar clamp stack", "pressure transducer port"),
            ("drawbar clamp stack", "spindle pull-force test point"),
            ("drawbar clamp stack", "actuator linkage"),
            ("drawbar clamp stack", "lower drawbar seat"),
            ("drawbar clamp stack", "release-piston clearance"),
            ("Belleville stack housing", "Belleville stack"),
        ],
    ),
    DocSpec(
        filename="cnc_CNCOM_003.json",
        domain_id="cnc",
        doc_id="CNCOM_003",
        source_relpath="data/cnc_om_manual_en/CNCOM_003.md",
        asset_label="Helion HMC-500",
        description="BT40 taper contamination and purge-path recovery",
        components=[
            "spindle nose",
            "BT40 taper mouth",
            "deeper taper zone",
            "drive dogs",
            "retention interface",
            "air-blast nozzle",
            "lower drain groove",
            "nozzle outlet",
            "clean master arbor",
        ],
        signals=[
            "chatter after roughing cast iron",
            "toolholder sticking at the spindle nose",
            "dark contact marks",
            "chip pack",
            "rust bloom",
            "fretting dust",
            "dried coolant",
            "holder witness",
            "air-blast pressure",
            "radial runout",
            "mouth contact pattern",
            "deeper taper contact",
        ],
        faults=[
            "chip-packed taper contamination",
            "blocked purge path",
            "purge failure",
            "taper damage",
            "retention damage",
        ],
        negatives=["coolant condition"],
        negative_reason_overrides={
            "coolant condition": "Operating-context note, not a durable graph concept."
        },
        structural_relations=[
            ("Helion HMC-500", "spindle nose"),
            ("spindle nose", "BT40 taper mouth"),
            ("BT40 taper mouth", "deeper taper zone"),
            ("BT40 taper mouth", "drive dogs"),
            ("BT40 taper mouth", "retention interface"),
            ("BT40 taper mouth", "air-blast nozzle"),
            ("BT40 taper mouth", "lower drain groove"),
            ("air-blast nozzle", "nozzle outlet"),
        ],
    ),
    DocSpec(
        filename="nev_EVMAN_001.json",
        domain_id="nev",
        doc_id="EVMAN_001",
        source_relpath="data/ev_om_manual_en/EVMAN_001.md",
        asset_label="Aurex E-Motion-412 LR",
        description="Battery coolant-plate outlet leak mapping",
        components=[
            "left coolant-plate outlet",
            "rear underbody shield",
            "left pack-side splash cover",
            "coolant-plate seam",
            "outlet hose",
            "quick-coupler lock window",
            "O-ring seat",
            "coolant-plate inlet",
            "coupler body",
            "support bracket",
            "aluminum plate edge",
            "green O-ring land",
            "hose end",
            "battery coolant-plate outlet quick connector",
            "connector shell",
        ],
        signals=[
            "battery coolant level",
            "residue color",
            "undertray wetness",
            "seepage",
            "fresh wetting",
            "clamp clocking",
            "connector latch height",
            "tube insertion depth",
            "dried coolant crystals",
            "plastic stress whitening",
            "metal staining",
        ],
        faults=[
            "plate-side crack",
            "connector leakage",
            "hose-routing condition",
            "O-ring interface leak",
        ],
        negatives=["recent thermal-system repair history"],
        negative_reason_overrides={
            "recent thermal-system repair history": "Context field for prior service, not a standalone graph node."
        },
        structural_relations=[
            ("Aurex E-Motion-412 LR", "left coolant-plate outlet"),
            ("Aurex E-Motion-412 LR", "rear underbody shield"),
            ("Aurex E-Motion-412 LR", "left pack-side splash cover"),
            ("Aurex E-Motion-412 LR", "battery coolant-plate outlet quick connector"),
            ("Aurex E-Motion-412 LR", "support bracket"),
            ("left coolant-plate outlet", "coolant-plate seam"),
            ("left coolant-plate outlet", "coolant-plate inlet"),
            ("battery coolant-plate outlet quick connector", "quick-coupler lock window"),
            ("battery coolant-plate outlet quick connector", "O-ring seat"),
            ("battery coolant-plate outlet quick connector", "coupler body"),
            ("battery coolant-plate outlet quick connector", "green O-ring land"),
            ("battery coolant-plate outlet quick connector", "hose end"),
            ("battery coolant-plate outlet quick connector", "connector shell"),
        ],
    ),
    DocSpec(
        filename="nev_EVMAN_002.json",
        domain_id="nev",
        doc_id="EVMAN_002",
        source_relpath="data/ev_om_manual_en/EVMAN_002.md",
        asset_label="Velorian PackLine-287 AWD",
        description="Service-disconnect seating correction",
        components=[
            "service disconnect",
            "service-disconnect cavity",
            "access lid",
            "disconnect plug",
            "blade set",
            "guide rail",
            "interlock pins",
            "latch window",
            "male blades",
            "female socket faces",
            "guide ribs",
            "CPA feature",
            "handle pivot",
            "latch hook",
            "orange handle",
            "service lid",
        ],
        signals=[
            "latch feel",
            "insertion force",
            "handle flushness",
            "HVIL warning",
            "orange handle sits proud",
            "snaps back after seating",
            "zero residual high-voltage potential",
            "seating depth",
            "latch travel",
            "blade exposure",
            "guide-rib alignment",
            "uneven insertion witness lines",
            "service-disconnect status",
            "ready-state permissive",
        ],
        faults=[
            "service-disconnect seating complaint",
            "misaligned guide feature",
            "minor burr",
            "displaced plastic",
        ],
        negatives=["known-good reference or spare"],
        negative_reason_overrides={
            "known-good reference or spare": "External comparison aid, not part of the serviced disconnect boundary."
        },
        structural_relations=[
            ("Velorian PackLine-287 AWD", "service disconnect"),
            ("Velorian PackLine-287 AWD", "service-disconnect cavity"),
            ("Velorian PackLine-287 AWD", "access lid"),
            ("Velorian PackLine-287 AWD", "service lid"),
            ("service disconnect", "disconnect plug"),
            ("service disconnect", "blade set"),
            ("service disconnect", "CPA feature"),
            ("service disconnect", "handle pivot"),
            ("service disconnect", "latch hook"),
            ("service disconnect", "orange handle"),
            ("service-disconnect cavity", "guide rail"),
            ("service-disconnect cavity", "interlock pins"),
            ("service-disconnect cavity", "latch window"),
            ("service-disconnect cavity", "female socket faces"),
            ("service-disconnect cavity", "guide ribs"),
            ("service disconnect", "male blades"),
        ],
    ),
    DocSpec(
        filename="nev_EVMAN_003.json",
        domain_id="nev",
        doc_id="EVMAN_003",
        source_relpath="data/ev_om_manual_en/EVMAN_003.md",
        asset_label="Helion E-Motion-536 Plus",
        description="HV output stud corrosion review",
        components=[
            "HV output stud pocket",
            "HV output boot",
            "HV output stud cover",
            "copper cable lug",
            "terminal nut",
            "washer stack",
            "plated stud thread",
            "insulating boot",
            "stud shoulder",
            "stud seating land",
            "first thread turns",
            "rubber boot lip",
            "cover edge",
            "harness support",
            "cable tray",
        ],
        signals=[
            "corrosion pattern",
            "pitting",
            "oxide buildup",
            "contact shadowing",
            "heat tint",
            "measured contact resistance",
            "corrosion severity",
            "as-found cable angle",
            "boot clocking",
        ],
        faults=[
            "trapped water",
            "galvanic attack",
            "reduced clamp load",
            "thread damage",
            "moisture trapped under the boot",
        ],
        negatives=["scheduled service"],
        negative_reason_overrides={
            "scheduled service": "Service trigger context, not a graph-worthy technical concept."
        },
        structural_relations=[
            ("Helion E-Motion-536 Plus", "HV output stud pocket"),
            ("Helion E-Motion-536 Plus", "HV output boot"),
            ("Helion E-Motion-536 Plus", "HV output stud cover"),
            ("Helion E-Motion-536 Plus", "harness support"),
            ("Helion E-Motion-536 Plus", "cable tray"),
            ("HV output stud pocket", "copper cable lug"),
            ("HV output stud pocket", "terminal nut"),
            ("HV output stud pocket", "washer stack"),
            ("HV output stud pocket", "plated stud thread"),
            ("HV output stud pocket", "insulating boot"),
            ("HV output stud pocket", "stud shoulder"),
            ("HV output stud pocket", "stud seating land"),
            ("HV output stud pocket", "first thread turns"),
            ("HV output stud pocket", "rubber boot lip"),
            ("HV output stud pocket", "cover edge"),
        ],
    ),
]


COMMUNICATION_INDICATORS = [
    {
        "pair_id": "CI_BAT_001",
        "domain": "battery",
        "source_doc": "BATOM_001",
        "signal": "undertray drip",
        "fault": "left-rear coolant-plate outlet leak boundary",
        "rationale": "The intake complaint is localized to the left-rear outlet branch before disassembly.",
    },
    {
        "pair_id": "CI_BAT_002",
        "domain": "battery",
        "source_doc": "BATOM_002",
        "signal": "flange gap",
        "fault": "warped composite flange",
        "rationale": "The manual explicitly separates local flange opening from other repair boundaries.",
    },
    {
        "pair_id": "CI_BAT_003",
        "domain": "battery",
        "source_doc": "BATOM_003",
        "signal": "stress whitening",
        "fault": "bracket side load",
        "rationale": "The removed shell inspection says one-sided polishing and whitening indicate side load.",
    },
    {
        "pair_id": "CI_BAT_004",
        "domain": "battery",
        "source_doc": "BATOM_003",
        "signal": "fresh wetting",
        "fault": "recurring seepage",
        "rationale": "Fresh wetting during proof indicates the leak has not been eliminated.",
    },
    {
        "pair_id": "CI_CNC_001",
        "domain": "cnc",
        "source_doc": "CNCOM_001",
        "signal": "coolant dripping from the rear column",
        "fault": "upper return-hose clamp leak",
        "rationale": "The complaint is traced back to the upper clamp or support path under the same speed window.",
    },
    {
        "pair_id": "CI_CNC_002",
        "domain": "cnc",
        "source_doc": "CNCOM_002",
        "signal": "drawbar alarm",
        "fault": "low clamp force",
        "rationale": "The intake note ties the alarm to the drawbar clamp stack rather than a generic spindle fault.",
    },
    {
        "pair_id": "CI_CNC_003",
        "domain": "cnc",
        "source_doc": "CNCOM_003",
        "signal": "dark contact marks",
        "fault": "chip-packed taper contamination",
        "rationale": "Contamination at the taper mouth is reviewed as the primary boundary before deeper spindle causes.",
    },
    {
        "pair_id": "CI_NEV_001",
        "domain": "nev",
        "source_doc": "EVMAN_001",
        "signal": "fresh wetting",
        "fault": "O-ring interface leak",
        "rationale": "The local pressure hold is used to determine whether wetting begins at the O-ring interface.",
    },
    {
        "pair_id": "CI_NEV_002",
        "domain": "nev",
        "source_doc": "EVMAN_002",
        "signal": "HVIL warning",
        "fault": "service-disconnect seating complaint",
        "rationale": "The complaint is defined by handle position together with the interlock response.",
    },
    {
        "pair_id": "CI_NEV_003",
        "domain": "nev",
        "source_doc": "EVMAN_003",
        "signal": "contact shadowing",
        "fault": "reduced clamp load",
        "rationale": "The pattern review distinguishes clamp-loss corrosion from moisture trapped under the boot.",
    },
]


PROPAGATION_CHAINS = [
    {
        "chain_id": "PC_BAT_001",
        "domain": "battery",
        "source_doc": "BATOM_001",
        "chain": ["saddle bracket side load", "cracked connector shell", "undertray drip"],
        "root_cause": "saddle bracket side load",
        "description": "Outlet-side support load can crack the connector shell and reappear as undertray dripping.",
    },
    {
        "chain_id": "PC_BAT_002",
        "domain": "battery",
        "source_doc": "BATOM_002",
        "chain": ["hose-side preload", "warped composite flange", "wetness after recent manifold removal"],
        "root_cause": "hose-side preload",
        "description": "Hose preload can distort flange compression and reopen the manifold-face leak.",
    },
    {
        "chain_id": "PC_BAT_003",
        "domain": "battery",
        "source_doc": "BATOM_003",
        "chain": ["bracket side load", "cracked shell", "recurring seepage"],
        "root_cause": "bracket side load",
        "description": "Side load on the connector support path can crack the shell and preserve seepage.",
    },
    {
        "chain_id": "PC_CNC_001",
        "domain": "cnc",
        "source_doc": "CNCOM_001",
        "chain": ["clip-to-bracket side load", "upper return-hose clamp leak", "coolant dripping from the rear column"],
        "root_cause": "clip-to-bracket side load",
        "description": "Rear-column support load can open the upper clamp leak only during the true vibration state.",
    },
    {
        "chain_id": "PC_CNC_002",
        "domain": "cnc",
        "source_doc": "CNCOM_002",
        "chain": ["inverted lower Belleville pair", "low clamp force", "tool pull-out during face milling"],
        "root_cause": "inverted lower Belleville pair",
        "description": "Washer-order error reduces clamp force and can surface as tool pull-out under load.",
    },
    {
        "chain_id": "PC_CNC_003",
        "domain": "cnc",
        "source_doc": "CNCOM_003",
        "chain": ["blocked purge path", "chip-packed taper contamination", "toolholder sticking at the spindle nose"],
        "root_cause": "blocked purge path",
        "description": "Weak purge can leave fines in the taper mouth and cause holder sticking.",
    },
    {
        "chain_id": "PC_NEV_001",
        "domain": "nev",
        "source_doc": "EVMAN_001",
        "chain": ["hose-routing condition", "connector leakage", "undertray wetness"],
        "root_cause": "hose-routing condition",
        "description": "A loaded hose path can push the connector off-axis and reappear as pack undertray wetness.",
    },
    {
        "chain_id": "PC_NEV_002",
        "domain": "nev",
        "source_doc": "EVMAN_002",
        "chain": ["misaligned guide feature", "service-disconnect seating complaint", "HVIL warning"],
        "root_cause": "misaligned guide feature",
        "description": "Guide-path misalignment can prevent full seating and trigger the interlock warning.",
    },
    {
        "chain_id": "PC_NEV_003",
        "domain": "nev",
        "source_doc": "EVMAN_003",
        "chain": ["trapped water", "oxide buildup", "measured contact resistance"],
        "root_cause": "trapped water",
        "description": "Moisture trapped in the stud pocket can create oxide growth and degrade measured resistance.",
    },
]


MULTI_HOP_QUESTIONS = [
    {
        "question_id": "MH_001",
        "domain": "battery",
        "source_doc": "BATOM_001",
        "hops": 3,
        "query": "From the battery pack, which connector feature sits inside the left-rear coolant-plate outlet path?",
        "gold_chain": ["Aurex BatteryHub-612 LR", "left-rear coolant-plate outlet", "PA12 quick-connector shell", "latch window"],
        "expected_answer": "latch window",
    },
    {
        "question_id": "MH_002",
        "domain": "battery",
        "source_doc": "BATOM_001",
        "hops": 2,
        "query": "What visible complaint can follow saddle bracket side load at the outlet branch?",
        "gold_chain": ["saddle bracket side load", "cracked connector shell", "undertray drip"],
        "expected_answer": "undertray drip",
    },
    {
        "question_id": "MH_003",
        "domain": "battery",
        "source_doc": "BATOM_002",
        "hops": 2,
        "query": "Inside the front manifold face, which seal element is held in the perimeter O-ring channel?",
        "gold_chain": ["front manifold face", "perimeter O-ring channel", "EPDM O-ring"],
        "expected_answer": "EPDM O-ring",
    },
    {
        "question_id": "MH_004",
        "domain": "battery",
        "source_doc": "BATOM_002",
        "hops": 2,
        "query": "What complaint can follow hose-side preload at the manifold face?",
        "gold_chain": ["hose-side preload", "warped composite flange", "wetness after recent manifold removal"],
        "expected_answer": "wetness after recent manifold removal",
    },
    {
        "question_id": "MH_005",
        "domain": "battery",
        "source_doc": "BATOM_003",
        "hops": 2,
        "query": "Which seal element belongs to the chiller-inlet connector assembly?",
        "gold_chain": ["Novaris ThermalPack-481", "chiller-inlet connector", "green O-ring"],
        "expected_answer": "green O-ring",
    },
    {
        "question_id": "MH_006",
        "domain": "battery",
        "source_doc": "BATOM_003",
        "hops": 2,
        "query": "What leak symptom can bracket side load lead to at the inlet connector?",
        "gold_chain": ["bracket side load", "cracked shell", "recurring seepage"],
        "expected_answer": "recurring seepage",
    },
    {
        "question_id": "MH_007",
        "domain": "cnc",
        "source_doc": "CNCOM_001",
        "hops": 2,
        "query": "On Kestrel VMC-850, which feature belongs to the upper outlet hose path?",
        "gold_chain": ["Kestrel VMC-850", "upper outlet hose", "upper hose bead"],
        "expected_answer": "upper hose bead",
    },
    {
        "question_id": "MH_008",
        "domain": "cnc",
        "source_doc": "CNCOM_001",
        "hops": 2,
        "query": "What complaint can clip-to-bracket side load produce on the chiller branch?",
        "gold_chain": ["clip-to-bracket side load", "upper return-hose clamp leak", "coolant dripping from the rear column"],
        "expected_answer": "coolant dripping from the rear column",
    },
    {
        "question_id": "MH_009",
        "domain": "cnc",
        "source_doc": "CNCOM_002",
        "hops": 3,
        "query": "Within the CAT40 spindle, which mechanism contains the Belleville stack?",
        "gold_chain": ["Arcline VTC-630", "CAT40 spindle", "drawbar clamp stack", "Belleville stack"],
        "expected_answer": "Belleville stack",
    },
    {
        "question_id": "MH_010",
        "domain": "cnc",
        "source_doc": "CNCOM_002",
        "hops": 2,
        "query": "What machining complaint can an inverted lower Belleville pair lead to?",
        "gold_chain": ["inverted lower Belleville pair", "low clamp force", "tool pull-out during face milling"],
        "expected_answer": "tool pull-out during face milling",
    },
    {
        "question_id": "MH_011",
        "domain": "cnc",
        "source_doc": "CNCOM_003",
        "hops": 3,
        "query": "At the spindle nose, which taper zone sits inside the BT40 taper mouth?",
        "gold_chain": ["Helion HMC-500", "spindle nose", "BT40 taper mouth", "deeper taper zone"],
        "expected_answer": "deeper taper zone",
    },
    {
        "question_id": "MH_012",
        "domain": "cnc",
        "source_doc": "CNCOM_003",
        "hops": 2,
        "query": "What holder complaint can follow a blocked purge path?",
        "gold_chain": ["blocked purge path", "chip-packed taper contamination", "toolholder sticking at the spindle nose"],
        "expected_answer": "toolholder sticking at the spindle nose",
    },
    {
        "question_id": "MH_013",
        "domain": "nev",
        "source_doc": "EVMAN_001",
        "hops": 2,
        "query": "Which seal feature belongs to the battery coolant-plate outlet quick connector?",
        "gold_chain": ["Aurex E-Motion-412 LR", "battery coolant-plate outlet quick connector", "O-ring seat"],
        "expected_answer": "O-ring seat",
    },
    {
        "question_id": "MH_014",
        "domain": "nev",
        "source_doc": "EVMAN_001",
        "hops": 2,
        "query": "What visible complaint can follow hose-routing condition at the outlet joint?",
        "gold_chain": ["hose-routing condition", "connector leakage", "undertray wetness"],
        "expected_answer": "undertray wetness",
    },
    {
        "question_id": "MH_015",
        "domain": "nev",
        "source_doc": "EVMAN_002",
        "hops": 2,
        "query": "Which latch feature belongs to the service disconnect assembly?",
        "gold_chain": ["Velorian PackLine-287 AWD", "service disconnect", "latch hook"],
        "expected_answer": "latch hook",
    },
    {
        "question_id": "MH_016",
        "domain": "nev",
        "source_doc": "EVMAN_002",
        "hops": 2,
        "query": "What warning can a misaligned guide feature cause?",
        "gold_chain": ["misaligned guide feature", "service-disconnect seating complaint", "HVIL warning"],
        "expected_answer": "HVIL warning",
    },
    {
        "question_id": "MH_017",
        "domain": "nev",
        "source_doc": "EVMAN_003",
        "hops": 2,
        "query": "Inside the HV output stud pocket, which conductive hardware sits at the joint stack?",
        "gold_chain": ["Helion E-Motion-536 Plus", "HV output stud pocket", "copper cable lug"],
        "expected_answer": "copper cable lug",
    },
    {
        "question_id": "MH_018",
        "domain": "nev",
        "source_doc": "EVMAN_003",
        "hops": 2,
        "query": "What measurement can rise along the trapped-water corrosion path?",
        "gold_chain": ["trapped water", "oxide buildup", "measured contact resistance"],
        "expected_answer": "measured contact resistance",
    },
]


LIFECYCLE_EVENTS_BY_DOMAIN = {
    "battery": [
        {
            "event_id": "BLE_001",
            "object_id": "battery::fault::BATOM_001_outlet_boundary",
            "event_type": "fault_occurrence",
            "timestamp": "2000-01-01T01:00:00Z",
            "description": "BATOM_001 records an active leak complaint at the left-rear coolant-plate outlet.",
        },
        {
            "event_id": "BLE_002",
            "object_id": "battery::component::BATOM_001_left-rear coolant-plate outlet",
            "event_type": "maintenance",
            "timestamp": "2000-01-01T06:00:00Z",
            "description": "BATOM_001 performs targeted correction and verification at the outlet-side boundary.",
        },
        {
            "event_id": "BLE_003",
            "object_id": "battery::fault::BATOM_002_front_manifold_boundary",
            "event_type": "fault_occurrence",
            "timestamp": "2000-01-02T01:00:00Z",
            "description": "BATOM_002 opens with a front-manifold-face complaint tied to seal compression or clamp load.",
        },
        {
            "event_id": "BLE_004",
            "object_id": "battery::component::BATOM_002_front manifold face",
            "event_type": "maintenance",
            "timestamp": "2000-01-02T07:00:00Z",
            "description": "BATOM_002 replaces or reseats only the failed manifold, seal, bolt stack, or hose support item.",
        },
        {
            "event_id": "BLE_005",
            "object_id": "battery::fault::BATOM_003_chiller_inlet_boundary",
            "event_type": "fault_occurrence",
            "timestamp": "2000-01-03T01:00:00Z",
            "description": "BATOM_003 documents a failed chiller-inlet connector boundary before replacement.",
        },
        {
            "event_id": "BLE_006",
            "object_id": "battery::component::BATOM_003_chiller-inlet connector",
            "event_type": "replacement",
            "timestamp": "2000-01-03T05:00:00Z",
            "description": "BATOM_003 installs and proves the replacement chiller-inlet connector stack.",
        },
    ],
    "cnc": [
        {
            "event_id": "CLE_001",
            "object_id": "cnc::fault::CNCOM_001_return_hose_boundary",
            "event_type": "fault_occurrence",
            "timestamp": "2000-01-01T01:00:00Z",
            "description": "CNCOM_001 opens with a spindle-chiller branch leak under the true circulation state.",
        },
        {
            "event_id": "CLE_002",
            "object_id": "cnc::component::CNCOM_001_upper return-hose clamp",
            "event_type": "maintenance",
            "timestamp": "2000-01-01T06:00:00Z",
            "description": "CNCOM_001 repositions the hose and clamp and restores the original clip path.",
        },
        {
            "event_id": "CLE_003",
            "object_id": "cnc::fault::CNCOM_002_drawbar_clamp_stack",
            "event_type": "fault_occurrence",
            "timestamp": "2000-01-02T01:00:00Z",
            "description": "CNCOM_002 records a drawbar clamp-stack fault tied to force, pressure, and stack geometry.",
        },
        {
            "event_id": "CLE_004",
            "object_id": "cnc::component::CNCOM_002_Belleville stack",
            "event_type": "maintenance",
            "timestamp": "2000-01-02T07:00:00Z",
            "description": "CNCOM_002 rebuilds the Belleville stack in the correct order and verifies the repair.",
        },
        {
            "event_id": "CLE_005",
            "object_id": "cnc::fault::CNCOM_003_taper_contamination",
            "event_type": "fault_occurrence",
            "timestamp": "2000-01-03T01:00:00Z",
            "description": "CNCOM_003 isolates the boundary to taper contamination and blocked purge rather than bearings.",
        },
        {
            "event_id": "CLE_006",
            "object_id": "cnc::component::CNCOM_003_BT40 taper mouth",
            "event_type": "maintenance",
            "timestamp": "2000-01-03T05:00:00Z",
            "description": "CNCOM_003 accepts the spindle only after cleaning and purge recovery restore contact and runout.",
        },
    ],
    "nev": [
        {
            "event_id": "NLE_001",
            "object_id": "nev::fault::EVMAN_001_left_coolant_plate_outlet_boundary",
            "event_type": "fault_occurrence",
            "timestamp": "2000-01-01T01:00:00Z",
            "description": "EVMAN_001 maps a leak boundary at the left coolant-plate outlet without performing downstream repair.",
        },
        {
            "event_id": "NLE_002",
            "object_id": "nev::fault::EVMAN_002_service_disconnect_seating",
            "event_type": "fault_occurrence",
            "timestamp": "2000-01-02T01:00:00Z",
            "description": "EVMAN_002 opens with a service-disconnect seating complaint defined by handle position and HVIL response.",
        },
        {
            "event_id": "NLE_003",
            "object_id": "nev::component::EVMAN_002_service disconnect",
            "event_type": "maintenance",
            "timestamp": "2000-01-02T05:00:00Z",
            "description": "EVMAN_002 corrects the seat condition and verifies stable seating after trim is restored.",
        },
        {
            "event_id": "NLE_004",
            "object_id": "nev::fault::EVMAN_003_HV_output_corrosion",
            "event_type": "fault_occurrence",
            "timestamp": "2000-01-03T01:00:00Z",
            "description": "EVMAN_003 reviews corrosion at the HV output stud stack and separates moisture path from clamp-loss evidence.",
        },
        {
            "event_id": "NLE_005",
            "object_id": "nev::component::EVMAN_003_HV output stud pocket",
            "event_type": "maintenance",
            "timestamp": "2000-01-03T06:00:00Z",
            "description": "EVMAN_003 restores the documented hardware order and closes the stud pocket with the moisture path recorded.",
        },
    ],
}


TEMPLATE_TEXTS = {
    "README.md": """
    # Ground Truth Annotation Templates

    这个目录是 `data/ground_truth/` 的标注操作手册。新开窗口时，先按下面顺序阅读：

    1. `README.md`
    2. `document_gold.annotation_spec.md`
    3. 你当前要改的那一类 `*.annotation_spec.md`
    4. 对应的 `*.template.json`

    ## 总原则

    - 只能根据原始源文档标注，禁止参考模型输出、中间结果、评测报表、错误样例。
    - 文档级 gold 只保留三类内容：
      - 逐步 `Task`
      - 明确的 `Asset / Component / Signal / Fault`
      - `task_dependency` 和 `structural` 两类关系
    - `communication`、`propagation`、`multi-hop`、`lifecycle` 单独放在各自的 support 文件中，不要混进文档级 gold。
    - 标签优先使用源文档原词；只有在必须消歧时，才做最小幅度的人工规范化。
    - 负样本要少而准，只保留明显属于记录字段、上下文描述或外部参考的信息。

    ## 文件说明

    - `document_gold.*`
      - 单文档 gold 文件模板和规范。
    - `dependency_chains.*`
      - 记录文档内的完整步骤依赖链。
    - `communication_indicators.*`
      - 记录“可观察信号 -> 故障边界”的强支撑配对。
    - `propagation_chains.*`
      - 记录“根因 -> 中间故障 -> 外显症状”的强支撑链。
    - `multi_hop_questions.*`
      - 记录由已确认标签和链路推出来的 2-4 hop 问题。
    - `lifecycle_events.*`
      - 记录保守的生命周期事件。注意这里的时间戳是相对顺序，不是真实日期。

    ## 关键约束

    - 文档级 gold 中，`relation_ground_truth` 只允许：
      - `triggers` / `task_dependency`
      - `contains` / `structural`
    - `_statistics` 必须由文件内容自动反算，不能手填。
    - 如果某条 support 标注证据不足，就删掉，不要为了“每篇都有”而硬补。
    """,
    "document_gold.annotation_spec.md": """
    # Document Gold 标注规范

    ## 1. 目标

    每个源文档对应一个 gold JSON。这个文件服务于主评测，因此必须保守、稳定、可复核。

    ## 2. 文件范围

    一个文件只标一个源文档：

    - `battery_BATOM_001.json`
    - `cnc_CNCOM_002.json`
    - `nev_EVMAN_003.json`

    其中：

    - `documents[0].doc_id` 必须与文件名里的文档编号一致
    - `concept_ground_truth[*].evidence_id` 与 `relation_ground_truth[*].evidence_id` 也必须一致

    ## 3. 概念标注规则

    允许的 `expected_anchor`：

    - `Task`
    - `Asset`
    - `Component`
    - `Signal`
    - `Fault`

    标注顺序：

    1. 先把 markdown 表里的所有 `T1...Tn` 逐步抄进来，`surface_form` 必须保留原句。
    2. 再补命名平台、硬件、接口、局部特征。
    3. 再补明确的投诉、测量量、观察量。
    4. 最后补明确命名的故障边界或失败模式。

    不应入图的典型内容：

    - 序列号
    - 纯上下文字段，如“最近维修史”“工况说明”
    - 外部参考件、备件、对照样本
    - 纯修辞性状态词，不能稳定指向对象的不要留

    ## 4. 关系标注规则

    文档级 gold 只允许两类关系：

    - 步骤链：`head=T_i, relation=triggers, tail=T_{i+1}, family=task_dependency`
    - 结构链：`head=装配或平台, relation=contains, tail=局部部件或特征, family=structural`

    不要在这里标：

    - `indicates`
    - `causes`
    - 生命周期相关关系

    这些内容去 support 文件里标。

    ## 5. 文本一致性要求

    - 标签优先用源文档原词。
    - 只有在必须消歧时，才加最小规范化前缀或后缀。
    - 同一文档内同一对象只能保留一个主标签。

    ## 6. 统计字段

    `_statistics` 必须满足：

    - `total_concepts == len(concept_ground_truth)`
    - `positive_concepts == should_be_in_graph == true` 的数量
    - `negative_concepts == should_be_in_graph == false` 的数量
    - `total_relations == len(relation_ground_truth)`
    - `valid_relations == valid == true` 的数量

    ## 7. 盲标注要求

    - 禁止查看预测图、错误分析、模型中间输出。
    - 禁止根据“模型错在哪里”去倒推标签。
    - 只允许看原始 markdown 和本目录模板。
    """,
    "dependency_chains.annotation_spec.md": """
    # Dependency Chains 标注规范

    ## 1. 目标

    记录每篇文档内部的完整步骤依赖主链，用于评估顺序推理是否覆盖了真实操作链路。

    ## 2. 规则

    - `chain` 必须按 `T1 -> T2 -> ...` 的自然顺序填写。
    - 默认应覆盖整篇文档的全部主步骤，不要随意截断。
    - 如果源文档确实存在条件分支，但主表是线性步骤，仍按主表顺序标注。
    - `source_doc` 必须对应真实文档编号。

    ## 3. 不要做的事

    - 不要把 support 推理链写进来。
    - 不要跳步。
    - 不要凭主观判断改写步骤编号。
    """,
    "communication_indicators.annotation_spec.md": """
    # Communication Indicators 标注规范

    ## 1. 目标

    记录“可观察信号 -> 故障边界”的强支撑配对。

    ## 2. 信号定义

    `signal` 必须是源文档中明确可观察、可记录、可测量的内容，例如：

    - 投诉词
    - 视觉痕迹
    - 仪表报警
    - 压力、阻值、温度等测量项

    ## 3. 故障定义

    `fault` 必须是文档明确指向的故障边界、失败模式或诊断结论。

    ## 4. 收录门槛

    只有以下情况才收录：

    - 文档明确说某信号“提示/区分/定位/指向”某故障
    - 或人工从同一句中可以做出极小幅度、无歧义的归纳

    如果需要跨多句、大幅度推理，说明它不该放在本文件里。

    ## 5. 稳定性原则

    - 宁缺毋滥。
    - 不要求每篇文档都必须有指标对。
    - `rationale` 要写成一句短的证据说明。
    """,
    "propagation_chains.annotation_spec.md": """
    # Propagation Chains 标注规范

    ## 1. 目标

    记录“根因 -> 中间故障 -> 外显症状”的传播链。

    ## 2. 规则

    - `chain[0]` 必须是 `root_cause`。
    - 最后一项通常是最终可见症状、报警或失效表现。
    - 中间节点必须按因果方向排列。
    - 链尽量短，优先 3 节点；只有源文档非常明确时才写 4 节点以上。

    ## 3. 收录门槛

    以下任一情况可以收录：

    - 文档显式给出因果关系
    - 文档给出非常接近的诊断语义，人工只做极小幅度连线

    以下情况不要收录：

    - 需要结合模型运行结果才能成立
    - 只是常识上“可能有关”，但文档没支持
    - 一个链里混入多个竞争性假设
    """,
    "multi_hop_questions.annotation_spec.md": """
    # Multi-hop Questions 标注规范

    ## 1. 目标

    根据已经确认的标签和链路，构造 2-4 hop 的可复核问题。

    ## 2. 规则

    - `gold_chain` 必须是问题的标准路径。
    - `hops == len(gold_chain) - 1`
    - `expected_answer` 默认写 `gold_chain` 最后一项。
    - 问题必须能由 document gold + support 标注中的标签支撑。

    ## 3. 问题类型建议

    - 平台 -> 组件 -> 局部特征
    - 根因 -> 中间故障 -> 外显症状
    - 组件 -> 故障边界 -> 可见信号

    ## 4. 不要做的事

    - 不要写开放式问答
    - 不要写需要外部知识的题
    - 不要写多个答案都对的问题
    """,
    "lifecycle_events.annotation_spec.md": """
    # Lifecycle Events 标注规范

    ## 1. 目标

    为时序评测提供极保守的生命周期事件标注。

    ## 2. 重要说明

    O&M 手册通常没有真实历史时间，因此这里的 `timestamp` 只是“相对顺序编码”，不是现实中的维护日期。

    ## 3. 允许的 `event_type`

    - `creation`
    - `update`
    - `deprecation`
    - `replacement`
    - `fault_occurrence`
    - `maintenance`

    ## 4. 标注原则

    - 手册没有明确对象历史时，不要滥标 `creation`
    - 优先标两类：
      - `fault_occurrence`
      - `maintenance` / `replacement`
    - 条件语句如果不构成稳定事件，不要写进去

    ## 5. `object_id` 约定

    推荐写法：

    - `battery::fault::BATOM_001_outlet_boundary`
    - `cnc::component::CNCOM_002_Belleville stack`
    - `nev::component::EVMAN_003_HV output stud pocket`

    目的不是建本体，而是保证不同窗口下命名稳定、可复核。
    """,
}


TEMPLATE_JSONS = {
    "document_gold.template.json": {
        "schema_version": "human_gold.v2",
        "domain_id": "<battery|cnc|nev>",
        "label_tier": "human_annotation_v2",
        "annotation_status": "human_annotated",
        "annotator_id": "<annotator_id>",
        "annotation_date": "YYYY-MM-DD",
        "annotation_basis": "Blind annotation from source O&M text only.",
        "documents": [
            {
                "doc_id": "<DOC_ID>",
                "doc_type": "om_manual",
            }
        ],
        "concept_ground_truth": [
            {
                "evidence_id": "<DOC_ID>",
                "label": "T1",
                "step_id": "T1",
                "surface_form": "<copy the full source sentence here>",
                "should_be_in_graph": True,
                "expected_anchor": "Task",
                "reason": "O&M step T1 retained verbatim from the source document.",
            },
            {
                "evidence_id": "<DOC_ID>",
                "label": "<named component>",
                "should_be_in_graph": True,
                "expected_anchor": "Component",
                "reason": "Explicitly named hardware, interface, or local feature in the source document.",
            },
            {
                "evidence_id": "<DOC_ID>",
                "label": "<context field>",
                "should_be_in_graph": False,
                "expected_anchor": None,
                "reason": "Context or recordkeeping field, not a stable graph concept.",
            },
        ],
        "relation_ground_truth": [
            {
                "evidence_id": "<DOC_ID>",
                "head": "T1",
                "relation": "triggers",
                "tail": "T2",
                "family": "task_dependency",
                "valid": True,
                "reason": "The source procedure order places T1 before T2.",
            },
            {
                "evidence_id": "<DOC_ID>",
                "head": "<asset or assembly>",
                "relation": "contains",
                "tail": "<component or feature>",
                "family": "structural",
                "valid": True,
                "reason": "The source document presents the tail as part of the local service boundary.",
            },
        ],
        "_statistics": {
            "total_concepts": 0,
            "positive_concepts": 0,
            "negative_concepts": 0,
            "total_relations": 0,
            "valid_relations": 0,
        },
    },
    "dependency_chains.template.json": {
        "schema_version": "dependency_gold.v2",
        "annotation_date": "YYYY-MM-DD",
        "annotation_basis": "Blind support annotation from source O&M text only.",
        "dependency_chains": [
            {
                "chain_id": "DC_<DOMAIN>_<NNN>",
                "domain": "<battery|cnc|nev>",
                "source_doc": "<DOC_ID>",
                "chain": ["T1", "T2", "T3"],
                "description": "<full ordered step chain description>",
            }
        ],
    },
    "communication_indicators.template.json": {
        "schema_version": "communication_gold.v2",
        "annotation_date": "YYYY-MM-DD",
        "annotation_basis": "Blind support annotation from source O&M text only.",
        "indicator_pairs": [
            {
                "pair_id": "CI_<DOMAIN>_<NNN>",
                "domain": "<battery|cnc|nev>",
                "source_doc": "<DOC_ID>",
                "signal": "<observable signal>",
                "fault": "<fault boundary>",
                "rationale": "<one-sentence grounding note>",
            }
        ],
    },
    "propagation_chains.template.json": {
        "schema_version": "propagation_gold.v2",
        "annotation_date": "YYYY-MM-DD",
        "annotation_basis": "Blind support annotation from source O&M text only.",
        "propagation_chains": [
            {
                "chain_id": "PC_<DOMAIN>_<NNN>",
                "domain": "<battery|cnc|nev>",
                "source_doc": "<DOC_ID>",
                "chain": ["<root cause>", "<intermediate fault>", "<visible symptom>"],
                "root_cause": "<root cause>",
                "description": "<one-sentence chain summary>",
            }
        ],
    },
    "multi_hop_questions.template.json": {
        "schema_version": "multi_hop_gold.v2",
        "annotation_date": "YYYY-MM-DD",
        "annotation_basis": "Blind support annotation from source O&M text only.",
        "questions": [
            {
                "question_id": "MH_<NNN>",
                "domain": "<battery|cnc|nev>",
                "source_doc": "<DOC_ID>",
                "hops": 2,
                "query": "<question text>",
                "gold_chain": ["<node1>", "<node2>", "<node3>"],
                "expected_answer": "<node3>",
            }
        ],
    },
    "lifecycle_events.template.json": {
        "schema_version": "lifecycle_gold.v2",
        "domain_id": "<battery|cnc|nev>",
        "annotation_date": "YYYY-MM-DD",
        "annotation_basis": "Blind support annotation from source O&M text only.",
        "timestamp_policy": "Synthetic relative timestamps encode manual step order only.",
        "lifecycle_events": [
            {
                "event_id": "<PREFIX>_001",
                "object_id": "<domain>::<kind>::<stable_object_name>",
                "event_type": "fault_occurrence",
                "timestamp": "2000-01-01T01:00:00Z",
                "description": "<one-sentence grounded event description>",
            }
        ],
    },
}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def read_steps(md_path: Path) -> list[tuple[str, str]]:
    steps: list[tuple[str, str]] = []
    for raw_line in md_path.read_text(encoding="utf-8").splitlines():
        match = STEP_PATTERN.match(raw_line.strip())
        if match:
            steps.append((match.group(1), match.group(2).strip()))
    if not steps:
        raise ValueError(f"no steps found in {md_path}")
    return steps


def concept_reason(anchor: str) -> str:
    if anchor == "Asset":
        return "Named platform, vehicle, or machine under service in the source document."
    if anchor == "Component":
        return "Explicitly named hardware, interface, or local feature in the source document."
    if anchor == "Signal":
        return "Observable complaint, measurement, or inspection cue explicitly mentioned in the source document."
    if anchor == "Fault":
        return "Diagnosed fault boundary or failure mode explicitly named in the source document."
    raise ValueError(f"unsupported anchor: {anchor}")


def build_document_gold(spec: DocSpec) -> dict:
    source_path = ROOT / spec.source_relpath
    steps = read_steps(source_path)
    concepts: list[dict] = []
    labels_seen: set[str] = set()

    for step_id, text in steps:
        labels_seen.add(step_id)
        concepts.append(
            {
                "evidence_id": spec.doc_id,
                "label": step_id,
                "step_id": step_id,
                "surface_form": text,
                "should_be_in_graph": True,
                "expected_anchor": "Task",
                "reason": f"O&M step {step_id}, retained verbatim from the source document.",
            }
        )

    for anchor, items in (
        ("Asset", [spec.asset_label]),
        ("Component", spec.components),
        ("Signal", spec.signals),
        ("Fault", spec.faults),
    ):
        for label in items:
            if label in labels_seen:
                raise ValueError(f"duplicate concept label in {spec.doc_id}: {label}")
            labels_seen.add(label)
            concepts.append(
                {
                    "evidence_id": spec.doc_id,
                    "label": label,
                    "should_be_in_graph": True,
                    "expected_anchor": anchor,
                    "reason": concept_reason(anchor),
                }
            )

    for label in spec.negatives:
        if label in labels_seen:
            raise ValueError(f"negative concept collides with positive label in {spec.doc_id}: {label}")
        labels_seen.add(label)
        concepts.append(
            {
                "evidence_id": spec.doc_id,
                "label": label,
                "should_be_in_graph": False,
                "expected_anchor": None,
                "reason": spec.negative_reason_overrides.get(
                    label,
                    "Context or recordkeeping field, not a stable graph concept for gold evaluation.",
                ),
            }
        )

    relations: list[dict] = []
    for index in range(len(steps) - 1):
        head, _ = steps[index]
        tail, _ = steps[index + 1]
        relations.append(
            {
                "evidence_id": spec.doc_id,
                "head": head,
                "relation": "triggers",
                "tail": tail,
                "family": "task_dependency",
                "valid": True,
                "reason": f"The source procedure order places {head} before {tail}.",
            }
        )

    positive_labels = {
        item["label"]
        for item in concepts
        if item.get("should_be_in_graph", False)
    }
    for head, tail in spec.structural_relations:
        if head not in positive_labels or tail not in positive_labels:
            raise ValueError(f"structural edge endpoint missing in {spec.doc_id}: {head} -> {tail}")
        if head == spec.asset_label:
            reason = f"{tail} belongs to the named service target {head} in the source document."
        else:
            reason = f"{tail} is presented as a local part or feature of {head} in the source document."
        relations.append(
            {
                "evidence_id": spec.doc_id,
                "head": head,
                "relation": "contains",
                "tail": tail,
                "family": "structural",
                "valid": True,
                "reason": reason,
            }
        )

    payload = {
        "schema_version": "human_gold.v2",
        "domain_id": spec.domain_id,
        "label_tier": "human_annotation_v2",
        "annotation_status": "human_annotated",
        "annotator_id": "codex_blind_reannotation_01",
        "annotation_date": DATE,
        "annotation_basis": DOC_ANNOTATION_BASIS,
        "documents": [{"doc_id": spec.doc_id, "doc_type": "om_manual"}],
        "concept_ground_truth": concepts,
        "relation_ground_truth": relations,
        "_statistics": {
            "total_concepts": len(concepts),
            "positive_concepts": sum(1 for item in concepts if item["should_be_in_graph"]),
            "negative_concepts": sum(1 for item in concepts if not item["should_be_in_graph"]),
            "total_relations": len(relations),
            "valid_relations": sum(1 for item in relations if item["valid"]),
        },
    }
    return payload


def build_dependency_payload(spec_to_steps: dict[str, list[tuple[str, str]]]) -> dict:
    chains = []
    for index, spec in enumerate(DOC_SPECS, start=1):
        chain = [step_id for step_id, _ in spec_to_steps[spec.doc_id]]
        chains.append(
            {
                "chain_id": f"DC_{spec.domain_id.upper()}_{index:03d}",
                "domain": spec.domain_id,
                "source_doc": spec.doc_id,
                "chain": chain,
                "description": spec.description,
            }
        )
    return {
        "schema_version": "dependency_gold.v2",
        "annotation_date": DATE,
        "annotation_basis": SUPPORT_ANNOTATION_BASIS,
        "dependency_chains": chains,
    }


def build_support_payload(schema_version: str, key: str, items: list[dict]) -> dict:
    return {
        "schema_version": schema_version,
        "annotation_date": DATE,
        "annotation_basis": SUPPORT_ANNOTATION_BASIS,
        key: items,
    }


def build_lifecycle_payloads() -> dict[str, dict]:
    payloads: dict[str, dict] = {}
    for domain_id, events in LIFECYCLE_EVENTS_BY_DOMAIN.items():
        payloads[domain_id] = {
            "schema_version": "lifecycle_gold.v2",
            "domain_id": domain_id,
            "annotation_date": DATE,
            "annotation_basis": SUPPORT_ANNOTATION_BASIS,
            "timestamp_policy": TIMESTAMP_POLICY,
            "lifecycle_events": events,
        }
    return payloads


def validate_document_payload(spec: DocSpec, payload: dict, steps: list[tuple[str, str]]) -> None:
    documents = payload.get("documents", [])
    if len(documents) != 1 or documents[0].get("doc_id") != spec.doc_id:
        raise ValueError(f"document metadata mismatch in {spec.filename}")
    concept_items = payload.get("concept_ground_truth", [])
    relation_items = payload.get("relation_ground_truth", [])
    positive_labels = {item["label"] for item in concept_items if item.get("should_be_in_graph")}
    step_ids = {step_id for step_id, _ in steps}
    task_labels = {item["label"] for item in concept_items if item.get("expected_anchor") == "Task"}
    if task_labels != step_ids:
        raise ValueError(f"step coverage mismatch in {spec.filename}: expected {sorted(step_ids)}, got {sorted(task_labels)}")
    stats = payload.get("_statistics", {})
    expected_stats = {
        "total_concepts": len(concept_items),
        "positive_concepts": sum(1 for item in concept_items if item.get("should_be_in_graph")),
        "negative_concepts": sum(1 for item in concept_items if not item.get("should_be_in_graph")),
        "total_relations": len(relation_items),
        "valid_relations": sum(1 for item in relation_items if item.get("valid")),
    }
    if stats != expected_stats:
        raise ValueError(f"statistics mismatch in {spec.filename}: {stats} != {expected_stats}")
    for relation in relation_items:
        if relation["head"] not in positive_labels and relation["head"] not in step_ids:
            raise ValueError(f"unknown relation head in {spec.filename}: {relation['head']}")
        if relation["tail"] not in positive_labels and relation["tail"] not in step_ids:
            raise ValueError(f"unknown relation tail in {spec.filename}: {relation['tail']}")
        if relation["family"] not in {"task_dependency", "structural"}:
            raise ValueError(f"unexpected relation family in {spec.filename}: {relation['family']}")


def validate_support_payloads(spec_to_steps: dict[str, list[tuple[str, str]]]) -> None:
    valid_docs = {spec.doc_id for spec in DOC_SPECS}

    for item in COMMUNICATION_INDICATORS:
        if item["source_doc"] not in valid_docs:
            raise ValueError(f"communication indicator references unknown doc: {item}")

    for item in PROPAGATION_CHAINS:
        if item["source_doc"] not in valid_docs:
            raise ValueError(f"propagation chain references unknown doc: {item}")
        if not item["chain"] or item["chain"][0] != item["root_cause"]:
            raise ValueError(f"propagation chain root mismatch: {item}")

    for item in MULTI_HOP_QUESTIONS:
        if item["source_doc"] not in valid_docs:
            raise ValueError(f"multi-hop question references unknown doc: {item}")
        if item["hops"] != len(item["gold_chain"]) - 1:
            raise ValueError(f"multi-hop hop count mismatch: {item}")
        if item["expected_answer"] != item["gold_chain"][-1]:
            raise ValueError(f"multi-hop expected answer mismatch: {item}")

    for domain_id, events in LIFECYCLE_EVENTS_BY_DOMAIN.items():
        if domain_id not in {"battery", "cnc", "nev"}:
            raise ValueError(f"unexpected lifecycle domain: {domain_id}")
        seen_event_ids: set[str] = set()
        for event in events:
            if event["event_type"] not in LIFECYCLE_EVENT_TYPES:
                raise ValueError(f"unexpected lifecycle event type: {event}")
            if event["event_id"] in seen_event_ids:
                raise ValueError(f"duplicate lifecycle event id: {event['event_id']}")
            seen_event_ids.add(event["event_id"])

    for spec in DOC_SPECS:
        chain = [step_id for step_id, _ in spec_to_steps[spec.doc_id]]
        if not chain:
            raise ValueError(f"empty dependency chain for {spec.doc_id}")


def sync_subset001_files() -> None:
    subset_dir = ROOT / "artifacts" / "subset001_full_suite_20260421_120043" / "gold_subset"
    if not subset_dir.exists():
        return
    for filename in ("battery_BATOM_001.json", "cnc_CNCOM_001.json", "nev_EVMAN_001.json"):
        src = GROUND_TRUTH_DIR / filename
        dst = subset_dir / filename
        if src.exists():
            shutil.copyfile(src, dst)


def rebuild() -> None:
    spec_to_steps = {
        spec.doc_id: read_steps(ROOT / spec.source_relpath)
        for spec in DOC_SPECS
    }
    validate_support_payloads(spec_to_steps)

    for spec in DOC_SPECS:
        payload = build_document_gold(spec)
        validate_document_payload(spec, payload, spec_to_steps[spec.doc_id])
        write_json(GROUND_TRUTH_DIR / spec.filename, payload)

    write_json(GROUND_TRUTH_DIR / "dependency_chains.json", build_dependency_payload(spec_to_steps))
    write_json(
        GROUND_TRUTH_DIR / "communication_indicators.json",
        build_support_payload("communication_gold.v2", "indicator_pairs", COMMUNICATION_INDICATORS),
    )
    write_json(
        GROUND_TRUTH_DIR / "propagation_chains.json",
        build_support_payload("propagation_gold.v2", "propagation_chains", PROPAGATION_CHAINS),
    )
    write_json(
        GROUND_TRUTH_DIR / "multi_hop_questions.json",
        build_support_payload("multi_hop_gold.v2", "questions", MULTI_HOP_QUESTIONS),
    )

    lifecycle_payloads = build_lifecycle_payloads()
    write_json(GROUND_TRUTH_DIR / "temporal" / "battery_lifecycle_events.json", lifecycle_payloads["battery"])
    write_json(GROUND_TRUTH_DIR / "temporal" / "cnc_lifecycle_events.json", lifecycle_payloads["cnc"])
    write_json(GROUND_TRUTH_DIR / "temporal" / "nev_lifecycle_events.json", lifecycle_payloads["nev"])

    for relative_path, content in TEMPLATE_TEXTS.items():
        write_text(TEMPLATE_DIR / relative_path, content)
    for relative_path, payload in TEMPLATE_JSONS.items():
        write_json(TEMPLATE_DIR / relative_path, payload)

    sync_subset001_files()

    print("Rebuilt document gold files:", len(DOC_SPECS))
    print("Rebuilt support files:", 7)
    print("Wrote template files:", len(TEMPLATE_TEXTS) + len(TEMPLATE_JSONS))


if __name__ == "__main__":
    rebuild()
