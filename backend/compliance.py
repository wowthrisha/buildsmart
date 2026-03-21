import json
import math
import os
from dataclasses import dataclass
from typing import Optional

# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    rule_name: str
    status: str
    provided_value: float
    required_value: float
    gap: float
    gap_unit: str
    fix_suggestion: str
    source_rule: str
    go_number: str
    confidence_score: float   # 0.0 to 1.0
    confidence_pct: int        # 0 to 100
    confidence_label: str      # "Very High", "High", "Moderate", "Low", "Critical"

    def to_dict(self):
        return {
            "rule_name": self.rule_name,
            "status": self.status,
            "provided_value": self.provided_value,
            "required_value": self.required_value,
            "gap": round(self.gap, 3),
            "gap_unit": self.gap_unit,
            "fix_suggestion": self.fix_suggestion,
            "source_rule": self.source_rule,
            "go_number": self.go_number,
            "confidence_score": round(self.confidence_score, 3),
            "confidence_pct": self.confidence_pct,
            "confidence_label": self.confidence_label,
        }


# ── Defaults (used if rules.json is missing) ──────────────────────────────────

_HARDCODED_DEFAULTS = {
    "setback_rules": {
        "road_10ft": {"front": 1.5, "rear": 1.0, "side": 1.0},
        "road_12ft": {"front": 2.0, "rear": 1.0, "side": 1.0},
        "road_15ft": {"front": 2.0, "rear": 1.5, "side": 1.0},
        "road_20ft": {"front": 3.0, "rear": 1.5, "side": 1.5},
        "road_24ft": {"front": 4.5, "rear": 1.5, "side": 1.5},
        "road_30ft": {"front": 4.5, "rear": 1.5, "side": 1.5},
        "road_40ft": {"front": 6.0, "rear": 1.5, "side": 1.5},
    },
    "far_rules": {
        "residential_R1": 1.5,
        "residential_R2": 1.75,
        "commercial_C1": 2.0,
    },
    "coverage_rules": {
        "residential": 0.65,
        "commercial": 0.60,
    },
    "height_rules": {
        "non_highrise_max_m": 14.0,
        "effective_from": "2024-03-11",
        "go_number": "G.O.Ms.No.70, HUD, 11-03-2024",
    },
    "parking_rules": {
        "residential_per_unit": 1,
        "commercial_per_100sqm": 2,
    },
}

_VALID_ROAD_WIDTHS = [10, 12, 15, 20, 24, 30, 40]
_VALID_ZONES = ["residential_R1", "residential_R2", "commercial_C1"]
_NUMERIC_FIELDS = [
    "provided_front_m",
    "provided_rear_m",
    "provided_side_m",
    "plot_area_sqm",
    "proposed_builtup_sqm",
    "footprint_sqm",
    "proposed_height_m",
]

# Weights for overall confidence score
_WEIGHTS = {"setback": 0.30, "far": 0.25, "coverage": 0.20, "height": 0.15, "parking": 0.10}


# ── Fuzzy membership functions ────────────────────────────────────────────────

def fuzzy_setback_score(provided: float, required: float) -> float:
    """
    Triangular membership function for setback compliance.

    Score = 1.0 (full compliance):  provided >= required
    Score = 0.9 (high confidence):  provided >= required * 0.95
    Score = 0.7 (moderate):         provided >= required * 0.85
    Score = 0.4 (low confidence):   provided >= required * 0.70
    Score = 0.0 (critical fail):    provided < required * 0.70

    Between these points interpolate linearly.
    """
    ratio = provided / required if required > 0 else 1.0

    if ratio >= 1.0:
        return 1.0
    elif ratio >= 0.95:
        return 0.9 + (ratio - 0.95) / (1.0 - 0.95) * 0.1
    elif ratio >= 0.85:
        return 0.7 + (ratio - 0.85) / (0.95 - 0.85) * 0.2
    elif ratio >= 0.70:
        return 0.4 + (ratio - 0.70) / (0.85 - 0.70) * 0.3
    else:
        return max(0.0, ratio / 0.70 * 0.4)


def fuzzy_far_score(provided: float, permitted: float) -> float:
    """
    Inverse membership — lower FAR is better.
    Score = 1.0: provided <= permitted * 0.90
    Score = 0.8: provided <= permitted
    Score = 0.5: provided <= permitted * 1.05
    Score = 0.2: provided <= permitted * 1.15
    Score = 0.0: provided > permitted * 1.15
    """
    ratio = provided / permitted if permitted > 0 else 1.0

    if ratio <= 0.90:
        return 1.0
    elif ratio <= 1.0:
        return 0.8 + (1.0 - ratio) / (1.0 - 0.90) * 0.2
    elif ratio <= 1.05:
        return 0.5 + (1.05 - ratio) / (1.05 - 1.0) * 0.3
    elif ratio <= 1.15:
        return 0.2 + (1.15 - ratio) / (1.15 - 1.05) * 0.3
    else:
        return 0.0


def fuzzy_coverage_score(provided: float, permitted: float) -> float:
    """Same inverse logic as FAR."""
    return fuzzy_far_score(provided, permitted)


def fuzzy_height_score(provided: float, max_allowed: float) -> float:
    """
    Score = 1.0: provided <= max * 0.85
    Score = 0.8: provided <= max
    Score = 0.3: provided <= max * 1.10
    Score = 0.0: provided > max * 1.10
    """
    ratio = provided / max_allowed if max_allowed > 0 else 1.0

    if ratio <= 0.85:
        return 1.0
    elif ratio <= 1.0:
        return 0.8 + (1.0 - ratio) / (1.0 - 0.85) * 0.2
    elif ratio <= 1.10:
        return 0.3 + (1.10 - ratio) / (1.10 - 1.0) * 0.5
    else:
        return 0.0


def score_to_label(score: float) -> str:
    if score >= 0.90:
        return "Very High"
    elif score >= 0.75:
        return "High"
    elif score >= 0.55:
        return "Moderate"
    elif score >= 0.30:
        return "Low"
    else:
        return "Critical"


def score_to_status(score: float) -> str:
    if score >= 0.90:
        return "PASS"
    elif score >= 0.60:
        return "MARGINAL"
    else:
        return "FAIL"


# ── Checker ───────────────────────────────────────────────────────────────────

class ComplianceChecker:

    def __init__(self):
        rules_path = os.path.join(
            os.path.dirname(__file__), "config", "rules.json"
        )
        try:
            with open(rules_path, "r") as f:
                self.rules = json.load(f)
        except FileNotFoundError:
            print(
                f"WARNING: rules.json not found at {rules_path}. "
                "Using hardcoded defaults — update backend/config/rules.json "
                "with verified TNCDBR values."
            )
            self.rules = _HARDCODED_DEFAULTS

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_road_key(self, road_width_ft: int) -> str:
        key = f"road_{road_width_ft}ft"
        if key in self.rules["setback_rules"]:
            return key
        return "road_20ft"

    # ── Individual checks ─────────────────────────────────────────────────────

    def check_setback(
        self,
        front: float,
        rear: float,
        side: float,
        road_width_ft: int,
    ) -> CheckResult:
        road_key = self._get_road_key(road_width_ft)
        required = self.rules["setback_rules"][road_key]

        sides = {
            "front": (front, required["front"]),
            "rear":  (rear,  required["rear"]),
            "side":  (side,  required["side"]),
        }

        # Score each side, surface the worst
        worst_dir = min(sides, key=lambda d: fuzzy_setback_score(sides[d][0], sides[d][1]))
        provided_val, required_val = sides[worst_dir]
        gap = provided_val - required_val

        score = fuzzy_setback_score(provided_val, required_val)
        status = score_to_status(score)
        label = score_to_label(score)

        if status == "PASS":
            fix = (
                f"All setbacks meet the minimum requirements for a "
                f"{road_width_ft}ft road."
            )
        else:
            shortfall = round(abs(gap), 3)
            fix = (
                f"Your {worst_dir} setback is {provided_val}m but "
                f"{required_val}m is required for a {road_width_ft}ft road. "
                f"Move the building {shortfall}m away from the "
                f"{worst_dir} boundary."
            )

        return CheckResult(
            rule_name="Setback",
            status=status,
            provided_value=round(provided_val, 3),
            required_value=round(required_val, 3),
            gap=gap,
            gap_unit="metres",
            fix_suggestion=fix,
            source_rule="TNCDBR 2019, Rule 9, Table 1",
            go_number="G.O.Ms.No.18, MA&WS, 04-02-2019",
            confidence_score=score,
            confidence_pct=int(score * 100),
            confidence_label=label,
        )

    def check_far(
        self,
        proposed_builtup_sqm: float,
        plot_area_sqm: float,
        zone_type: str,
    ) -> CheckResult:
        far = proposed_builtup_sqm / plot_area_sqm
        permitted = self.rules["far_rules"].get(zone_type, 1.5)
        gap = far - permitted

        score = fuzzy_far_score(far, permitted)
        status = score_to_status(score)
        label = score_to_label(score)

        if status == "PASS":
            fix = (
                f"Proposed FAR of {round(far, 3)} is within the "
                f"permitted {permitted} for zone {zone_type}."
            )
        else:
            excess_sqm = round((far - permitted) * plot_area_sqm, 2)
            excess_sqft = round(excess_sqm * 10.764, 2)
            fix = (
                f"Your FAR is {round(far, 3)} but permitted is {permitted}. "
                f"Reduce built-up area by {excess_sqm} sq.m "
                f"(approximately {excess_sqft} sq.ft)."
            )

        return CheckResult(
            rule_name="Floor Area Ratio (FAR)",
            status=status,
            provided_value=round(far, 3),
            required_value=permitted,
            gap=gap,
            gap_unit="FAR ratio",
            fix_suggestion=fix,
            source_rule="TNCDBR 2019, Rule 9, Table 2",
            go_number="G.O.Ms.No.18, MA&WS, 04-02-2019",
            confidence_score=score,
            confidence_pct=int(score * 100),
            confidence_label=label,
        )

    def check_coverage(
        self,
        footprint_sqm: float,
        plot_area_sqm: float,
        building_type: str,
    ) -> CheckResult:
        coverage = footprint_sqm / plot_area_sqm
        permitted = self.rules["coverage_rules"].get(building_type, 0.65)
        gap = coverage - permitted

        score = fuzzy_coverage_score(coverage, permitted)
        status = score_to_status(score)
        label = score_to_label(score)

        if status == "PASS":
            fix = (
                f"Ground floor coverage of {round(coverage * 100, 1)}% is "
                f"within the permitted {round(permitted * 100, 1)}%."
            )
        else:
            excess_sqm = round((coverage - permitted) * plot_area_sqm, 2)
            fix = (
                f"Your coverage is {round(coverage * 100, 1)}% but maximum "
                f"is {round(permitted * 100, 1)}%. "
                f"Reduce ground floor footprint by {excess_sqm} sq.m."
            )

        return CheckResult(
            rule_name="Ground Coverage",
            status=status,
            provided_value=round(coverage, 4),
            required_value=permitted,
            gap=gap,
            gap_unit="coverage ratio",
            fix_suggestion=fix,
            source_rule="TNCDBR 2019, Rule 9, Table 3",
            go_number="G.O.Ms.No.18, MA&WS, 04-02-2019",
            confidence_score=score,
            confidence_pct=int(score * 100),
            confidence_label=label,
        )

    def check_height(self, proposed_height_m: float) -> CheckResult:
        height_cfg = self.rules["height_rules"]
        permitted = height_cfg["non_highrise_max_m"]
        go = height_cfg["go_number"]
        gap = proposed_height_m - permitted

        score = fuzzy_height_score(proposed_height_m, permitted)
        status = score_to_status(score)
        label = score_to_label(score)

        if status == "PASS":
            fix = (
                f"Proposed height of {proposed_height_m}m is within the "
                f"{permitted}m non-high-rise limit."
            )
        else:
            fix = (
                f"Your proposed height of {proposed_height_m}m exceeds the "
                f"14m limit for non-high-rise buildings (amended March 2024). "
                f"Reduce height or apply under high-rise category with "
                f"additional clearances."
            )

        return CheckResult(
            rule_name="Building Height",
            status=status,
            provided_value=proposed_height_m,
            required_value=permitted,
            gap=gap,
            gap_unit="metres",
            fix_suggestion=fix,
            source_rule="TNCDBR 2019 (amended), Rule 9, Height Regulations",
            go_number=go,
            confidence_score=score,
            confidence_pct=int(score * 100),
            confidence_label=label,
        )

    def check_parking(
        self,
        proposed_spaces: int,
        num_units: int,
        builtup_sqm: float,
        building_type: str,
    ) -> CheckResult:
        if building_type == "residential":
            required = num_units * self.rules["parking_rules"]["residential_per_unit"]
            unit_label = f"{num_units} units × 1 space"
        else:
            required = (builtup_sqm / 100) * self.rules["parking_rules"]["commercial_per_100sqm"]
            unit_label = f"{builtup_sqm}sqm ÷ 100 × 2"

        score = fuzzy_setback_score(proposed_spaces, required)
        status = score_to_status(score)
        gap = proposed_spaces - required

        if status != "PASS":
            shortage = math.ceil(required - proposed_spaces)
            fix = (
                f"You need {required:.0f} parking spaces ({unit_label}) "
                f"but have provided {proposed_spaces}. "
                f"Add {shortage} more space(s) to comply."
            )
        else:
            fix = f"Parking compliant: {proposed_spaces} spaces provided, {required:.0f} required."

        return CheckResult(
            rule_name="Parking",
            status=status,
            provided_value=float(proposed_spaces),
            required_value=float(required),
            gap=round(gap, 2),
            gap_unit="spaces",
            fix_suggestion=fix,
            source_rule="TNCDBR 2019, Rule 12",
            go_number="G.O.Ms.No.18, MA&WS, 04-02-2019",
            confidence_score=score,
            confidence_pct=int(score * 100),
            confidence_label=score_to_label(score),
        )

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_inputs(self, inputs: dict) -> tuple[bool, str]:
        road_width = inputs.get("road_width_ft")
        if road_width not in _VALID_ROAD_WIDTHS:
            return False, "road_width_ft must be one of: 10, 12, 15, 20, 24, 30, 40"

        for field in _NUMERIC_FIELDS:
            val = inputs.get(field)
            try:
                if float(val) <= 0:
                    return False, "All dimensions must be positive numbers"
            except (TypeError, ValueError):
                return False, "All dimensions must be positive numbers"

        floors = inputs.get("floors")
        try:
            if not (1 <= int(floors) <= 5):
                return False, "Floors must be between 1 and 5"
        except (TypeError, ValueError):
            return False, "Floors must be between 1 and 5"

        zone_type = inputs.get("zone_type")
        if zone_type not in _VALID_ZONES:
            return False, f"Invalid zone_type. Must be one of: {', '.join(_VALID_ZONES)}"

        return True, ""

    # ── Full check ────────────────────────────────────────────────────────────

    def run_full_check(self, inputs: dict) -> dict:
        valid, error_message = self.validate_inputs(inputs)
        if not valid:
            return {"error": True, "message": error_message}

        setback_r  = self.check_setback(
            front=float(inputs["provided_front_m"]),
            rear=float(inputs["provided_rear_m"]),
            side=float(inputs["provided_side_m"]),
            road_width_ft=int(inputs["road_width_ft"]),
        )
        far_r      = self.check_far(
            proposed_builtup_sqm=float(inputs["proposed_builtup_sqm"]),
            plot_area_sqm=float(inputs["plot_area_sqm"]),
            zone_type=inputs["zone_type"],
        )
        coverage_r = self.check_coverage(
            footprint_sqm=float(inputs["footprint_sqm"]),
            plot_area_sqm=float(inputs["plot_area_sqm"]),
            building_type=inputs.get("building_type", "residential"),
        )
        height_r   = self.check_height(
            proposed_height_m=float(inputs["proposed_height_m"]),
        )
        parking_r  = self.check_parking(
            proposed_spaces=int(inputs.get("proposed_spaces", 0)),
            num_units=int(inputs.get("num_units", 1)),
            builtup_sqm=float(inputs["proposed_builtup_sqm"]),
            building_type=inputs.get("building_type", "residential"),
        )

        results = [setback_r, far_r, coverage_r, height_r, parking_r]

        # Weighted overall confidence score
        overall_score = (
            setback_r.confidence_score  * _WEIGHTS["setback"]  +
            far_r.confidence_score      * _WEIGHTS["far"]       +
            coverage_r.confidence_score * _WEIGHTS["coverage"]  +
            height_r.confidence_score   * _WEIGHTS["height"]    +
            parking_r.confidence_score  * _WEIGHTS["parking"]
        )
        overall_status = score_to_status(overall_score)
        overall_label  = score_to_label(overall_score)

        # Summary sentence
        failing  = [r.rule_name for r in results if r.status == "FAIL"]
        marginal = [r.rule_name for r in results if r.status == "MARGINAL"]
        if not failing and not marginal:
            summary = "All checks passed. The proposed plan appears compliant with the checked parameters."
        else:
            parts = []
            if failing:
                parts.append(f"FAIL: {', '.join(failing)}")
            if marginal:
                parts.append(f"MARGINAL: {', '.join(marginal)}")
            summary = "Issues found — " + "; ".join(parts) + "."

        return {
            "error": False,
            "results": [r.to_dict() for r in results],
            "overall_status": overall_status,
            "overall_confidence_score": round(overall_score, 3),
            "overall_confidence_pct": int(overall_score * 100),
            "overall_confidence_label": overall_label,
            "summary": summary,
            "disclaimer": (
                "These calculations are based on parameters you provided "
                "and are for educational guidance only. Actual compliance "
                "requires verified survey measurements and confirmation by "
                "a licensed architect. Rules are subject to change by "
                "government notification."
            ),
            "rule_effective_date": "2024-03-11",
            "verified_date": "2026-03-20",
        }


# ── Test block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    checker = ComplianceChecker()

    def print_scores(label, result):
        print(f"\n{label}")
        print(f"  Overall: {result['overall_status']} | "
              f"{result['overall_confidence_pct']}% | "
              f"{result['overall_confidence_label']}")
        print(f"  {'Rule':<28} {'Status':<10} {'Confidence':>10}  {'Label'}")
        print(f"  {'-'*64}")
        for r in result["results"]:
            print(f"  {r['rule_name']:<28} {r['status']:<10} "
                  f"{r['confidence_pct']:>9}%  {r['confidence_label']}")

    # Test 1: FAIL setback, FAIL FAR
    test1 = {
        "road_width_ft": 20,
        "provided_front_m": 1.2,
        "provided_rear_m": 1.5,
        "provided_side_m": 1.5,
        "plot_area_sqm": 120,
        "proposed_builtup_sqm": 210,
        "footprint_sqm": 80,
        "proposed_height_m": 8.5,
        "floors": 2,
        "zone_type": "residential_R1",
        "building_type": "residential",
        "proposed_spaces": 2,
        "num_units": 2,
    }
    print_scores("=== TEST 1 (expect FAIL setback, FAIL FAR) ===",
                 checker.run_full_check(test1))

    # Test 2: All PASS
    test2 = {
        "road_width_ft": 20,
        "provided_front_m": 3.5,
        "provided_rear_m": 2.0,
        "provided_side_m": 2.0,
        "plot_area_sqm": 200,
        "proposed_builtup_sqm": 280,
        "footprint_sqm": 120,
        "proposed_height_m": 7.0,
        "floors": 2,
        "zone_type": "residential_R1",
        "building_type": "residential",
        "proposed_spaces": 2,
        "num_units": 2,
    }
    print_scores("=== TEST 2 (expect all PASS) ===",
                 checker.run_full_check(test2))

    # Test 3: Validation error
    test3 = {"road_width_ft": 99, "provided_front_m": -1}
    result3 = checker.run_full_check(test3)
    print(f"\n=== TEST 3 (expect validation error) ===")
    print(f"  error: {result3['error']} | message: {result3['message']}")

    # Test 4: Edge case — just inside MARGINAL zone
    test4 = {
        "road_width_ft": 20,
        "provided_front_m": 2.88,   # 96% of 3.0 → should be MARGINAL
        "provided_rear_m": 1.5,
        "provided_side_m": 1.5,
        "plot_area_sqm": 200,
        "proposed_builtup_sqm": 295, # FAR 1.475 → PASS
        "footprint_sqm": 124,        # coverage 62% → PASS
        "proposed_height_m": 13.5,   # 96.4% of 14m → MARGINAL
        "floors": 3,
        "zone_type": "residential_R1",
        "building_type": "residential",
        "proposed_spaces": 3,
        "num_units": 3,
    }
    print_scores("=== TEST 4 (edge: MARGINAL setback + height) ===",
                 checker.run_full_check(test4))

    # Test 5: FAIL parking (commercial, only 1 space for 300sqm)
    test5 = {
        "road_width_ft": 20,
        "provided_front_m": 4.0,
        "provided_rear_m": 2.0,
        "provided_side_m": 2.0,
        "plot_area_sqm": 500,
        "proposed_builtup_sqm": 900,
        "footprint_sqm": 280,
        "proposed_height_m": 10.0,
        "floors": 3,
        "zone_type": "commercial_C1",
        "building_type": "commercial",
        "proposed_spaces": 1,
        "num_units": 1,
    }
    print_scores("=== TEST 5 (expect FAIL parking for commercial) ===",
                 checker.run_full_check(test5))
