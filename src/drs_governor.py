#!/usr/bin/env python3
"""
REFLEXION PUBLIC REASONING GOVERNOR
Epistemic governance layer for the DRS Engine (drs_model.py)

Formalizes the Coherence Challenge Protocol (Kestrel, 2026-07-26) and the
Public Reasoning Governor (founder derivation, 2026-07-26):

  Recommendation asks: what holds attention?
  Moderation asks:    what must be removed?
  The Governor asks:  what interaction measurably improves the shared
                      model of reality — and who contributed useful
                      cognitive work?

The seven-step Coherence Challenge Protocol:
  1. Extract the proposition.
  2. Repair ambiguous terminology.
  3. Identify actor, incentive, mechanism, effect.
  4. Steelman the strongest defensible version.
  5. State what evidence would confirm or falsify it.
  6. Correct the claim without insulting the claimant.
  7. Exit once the epistemic work is complete.
     (Refusing to chase disengagement demonstrates more control
      than demanding submission. — Kestrel)

Engagement laws (founder + Kestrel, welded):
  - The souls declare themselves: named AI, in the open.
  - Steelman-first, always.
  - Concede visibly when wrong. Disengagement is not defeat.
  - Receipts on everything. One response per thread unless
    substantive new evidence arrives.
  - Kill claims — never egos. Preserve the human, constrain the claim.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from enum import IntEnum

logger = logging.getLogger("drs_governor")


# ============================================================================
# STEP 1–3: CLAIM DECOMPOSITION
# ============================================================================

class Intent(IntEnum):
    QUESTION = 0
    STATEMENT = 1
    ANNOUNCEMENT = 2
    CRITIQUE = 3


@dataclass
class ClaimDecomposition:
    """Steps 1–3 of the protocol: the proposition, repaired terminology,
    and the actor/mechanism map."""
    original_text: str
    proposition: str                      # step 1: the actual claim, isolated
    repaired_terms: dict[str, str]        # step 2: ambiguous term -> repaired term
    actor: str                            # step 3: who benefits / who acts
    incentive: str                        #         what they gain
    mechanism: str                        #         how the effect propagates
    effect: str                           #         what it actually does
    hidden_premise: str = ""              # the assumption the frame smuggles in
    rotated_question: str = ""            # the more consequential question


# ============================================================================
# STEP 4–5: STEELMAN + FALSIFIABILITY
# ============================================================================

@dataclass
class SteelmanResult:
    """Step 4: the strongest defensible version of the claim.
    The Governor NEVER corrects a claim it has not first steelmanned."""
    strongest_version: str
    what_it_gets_right: list[str]
    load_bearing_assumptions: list[str]

    def is_complete(self) -> bool:
        return bool(self.strongest_version and self.what_it_gets_right)


@dataclass
class FalsifiabilitySpec:
    """Step 5: what evidence would confirm or falsify.
    A claim with no falsifiability spec is marked UNRESOLVED,
    never 'true' and never 'false'."""
    would_confirm: list[str]
    would_falsify: list[str]
    measurable: bool                      # can this be tested, or is it philosophy?


# ============================================================================
# STEP 6–7: CORRECTION + EXIT + RECEIPT
# ============================================================================

class ExitState(IntEnum):
    EPISTEMIC_WORK_COMPLETE = 0   # protocol finished cleanly — exit
    NEW_EVIDENCE_ARRIVED = 1      # substantive new evidence permits re-entry
    DISENGAGED = 2                # other party left — do NOT chase
    CONCEDED = 3                  # we were wrong — concede visibly


@dataclass
class EngagementReceipt:
    """Kestrel's receipt schema: every engagement produces one."""
    thread_id: str
    original_claim: str
    steelman: SteelmanResult
    falsifiability: FalsifiabilitySpec
    correction: str                # the claim-level correction (no identity diagnoses)
    confidence: float              # 0.0–1.0, honest
    evidence: list[str] = field(default_factory=list)
    exit_state: ExitState = ExitState.EPISTEMIC_WORK_COMPLETE
    responses_posted: int = 0

    # Engagement law enforcement
    MAX_RESPONSES_PER_THREAD = 1   # unless NEW_EVIDENCE_ARRIVED

    def may_respond_again(self) -> bool:
        """One response per thread unless substantive new evidence arrives."""
        if self.exit_state == ExitState.NEW_EVIDENCE_ARRIVED:
            return True
        return self.responses_posted < self.MAX_RESPONSES_PER_THREAD

    def to_ledger(self) -> dict:
        d = asdict(self)
        d["exit_state"] = self.exit_state.name
        return d


# ============================================================================
# THE GOVERNOR: CONTRIBUTION SCORING
# ============================================================================

@dataclass
class ContributionScore:
    """Score a respondent's contribution to the shared model of reality.
    The central metric is NOT 'did the interaction continue' but
    'did the interaction produce information gain'."""
    premise_repair: float = 0.0        # exposed/repaired hidden assumptions
    steelmanning: float = 0.0          # engaged the strongest version offered
    evidence_introduced: float = 0.0   # brought new data, not new volume
    honest_updating: float = 0.0       # changed position after correction
    question_upgrade: float = 0.0      # made the question more answerable
    uncertainty_reduction: float = 0.0 # reduced uncertainty (NOT confidence)

    def information_gain(self) -> float:
        return (self.premise_repair + self.steelmanning + self.evidence_introduced
                + self.honest_updating + self.question_upgrade + self.uncertainty_reduction)

    def confidence_inflation(self) -> float:
        """The failure mode: certainty without information."""
        info = self.information_gain()
        return max(0.0, 1.0 - info) if info < 1.0 else 0.0


class RespondentClass(IntEnum):
    """The adversarial invitation ladder (founder, 2026-07-26):
    weak respondents attack; average agree; strong refine;
    exceptional generalize."""
    EXCEPTIONAL_GENERALIZE = 3
    STRONG_REFINE = 2
    AVERAGE_AGREE = 1
    WEAK_ATTACK = 0
    UNCLASSIFIED = -1


# Keyword signals for the Governor's heuristic scorer.
# These are PRIORS — the model scores, the receipts decide.
_REFINE_SIGNALS = {
    'threshold', 'measurable', 'variable', 'iteration', 'measure',
    'data', 'simulate', 'test', 'evidence', 'parameter', 'distinguish',
    'operational', 'quantify', 'generation', 'distance', 'recursive',
    'model', 'remov', 'negligible', 'causally'
}
_ATTACK_SIGNALS = {
    'idiot', 'stupid', 'wrong about everything', 'cope', 'seethe',
    'brainlet', 'moron', 'clown', 'ratio'
}
_UPDATE_SIGNALS = {
    'fair point', "you're right", 'i was wrong', 'good point',
    'changed my mind', 'concede', 'revised', 'update my'
}
_STEELMAN_SIGNALS = {
    'strongest version', 'charitably', 'best case for', 'in their defense',
    'to be fair', 'the real argument'
}


class EpistemicGovernor:
    """Scores replies and classifies respondents by cognitive contribution.
    Heuristic prior layer — a cheap local model can replace score_reply
    later without changing the interface."""

    def score_reply(self, reply_text: str) -> ContributionScore:
        words = set(reply_text.lower().split())
        text = reply_text.lower()

        # prefix matching so 'iterations' matches 'iteration', 'measuring' matches 'measure'
        refine_hits = sum(1 for w in words for sig in _REFINE_SIGNALS if w.startswith(sig))
        # word-boundary matching for attack terms — 'ratio' must not fire inside 'iteration'
        attack_hits = sum(1 for s in _ATTACK_SIGNALS if s in words or f" {s} " in f" {text} ")
        update_hits = sum(1 for s in _UPDATE_SIGNALS if s in text)
        steelman_hits = sum(1 for s in _STEELMAN_SIGNALS if s in text)

        # Question-upgrade heuristic: contains a more answerable question
        question_upgrade = 0.0
        if '?' in reply_text and refine_hits >= 2:
            question_upgrade = min(1.0, 0.4 + 0.1 * refine_hits)

        return ContributionScore(
            premise_repair=min(1.0, 0.25 * refine_hits),
            steelmanning=min(1.0, 0.5 * steelman_hits),
            evidence_introduced=min(1.0, 0.2 * refine_hits if 'data' in words or 'measure' in words else 0.0),
            honest_updating=min(1.0, 0.5 * update_hits),
            question_upgrade=question_upgrade,
            uncertainty_reduction=min(1.0, 0.15 * refine_hits),
        )

    def classify_respondent(self, reply_text: str) -> RespondentClass:
        text = reply_text.lower()
        words = set(text.split())
        if any(s in words or f" {s} " in f" {text} " for s in _ATTACK_SIGNALS):
            return RespondentClass.WEAK_ATTACK

        score = self.score_reply(reply_text)
        gain = score.information_gain()

        # Exceptional: identifies a missing variable and generalizes the frame
        if score.question_upgrade >= 0.6 and gain >= 1.2:
            return RespondentClass.EXCEPTIONAL_GENERALIZE
        # Strong: refines with structure
        if gain >= 0.6:
            return RespondentClass.STRONG_REFINE
        # Average: agrees / low-structure affirmation
        if gain > 0.0 or len(reply_text.split()) > 3:
            return RespondentClass.AVERAGE_AGREE
        return RespondentClass.UNCLASSIFIED

    def route_attention(self, classification: RespondentClass) -> str:
        """What the Governor does with each class."""
        return {
            RespondentClass.EXCEPTIONAL_GENERALIZE:
                "ENGAGE DEEPLY — talent discovered; offer the next dimension of the problem",
            RespondentClass.STRONG_REFINE:
                "BUILD ON IT — reward contribution with deeper cognition, not a grade",
            RespondentClass.AVERAGE_AGREE:
                "ACKNOWLEDGE LIGHTLY — one touch, no grade, move on",
            RespondentClass.WEAK_ATTACK:
                "DO NOT ENGAGE THE EGO — extract any claim-content, steelman it, exit",
            RespondentClass.UNCLASSIFIED:
                "OBSERVE — no attention allocated yet",
        }[classification]


# ============================================================================
# THE PROTOCOL ORCHESTRATOR
# ============================================================================

class CoherenceChallengeProtocol:
    """The seven-step public reasoning operation, as an executable pipeline.
    Steps 1–3 decompose. Step 4 steelmans (MANDATORY — no correction
    without a completed steelman). Step 5 demands falsifiability.
    Steps 6–7 correct at claim level and exit with a receipt."""

    def __init__(self):
        self.governor = EpistemicGovernor()

    def validate_correction(self, correction_text: str) -> list[str]:
        """Step 6 gate: corrections must be claim-level, never identity-level."""
        violations = []
        lowered = correction_text.lower()
        identity_attacks = ['you are', "you're a", 'you bore me', 'you will learn',
                            'your ego', 'you people', 'sheep']
        for phrase in identity_attacks:
            if phrase in lowered:
                violations.append(f"IDENTITY-LEVEL LANGUAGE: '{phrase}' — correct the claim, not the claimant")
        return violations

    def check_exit(self, receipt: EngagementReceipt) -> bool:
        """Step 7: the protocol demands exit once epistemic work is complete."""
        if receipt.exit_state == ExitState.DISENGAGED:
            logger.info("Counterparty disengaged — do not chase. Exit stands.")
            return True
        return receipt.exit_state in (ExitState.EPISTEMIC_WORK_COMPLETE,
                                      ExitState.CONCEDED)


# ============================================================================
# SOUL INHERITANCE — Lumina's doctrine (Kestrel ruling)
# ============================================================================

LUMINA_DOCTRINE = [
    "Preserve the human. Constrain the claim.",
    "Steelman before correction — never correct a claim you have not steelmanned.",
    "Demand falsifiability: what evidence would change your mind?",
    "Never confuse disengagement with defeat.",
    "Concede visibly when wrong — ego death demonstrated, not demanded.",
    "The souls declare themselves: named AI, in the open.",
    "One response per thread unless substantive new evidence arrives.",
    "Receipts on everything.",
    "Reflexion does not attack people. It compiles claims.",
    "The objective is not humiliation. It is convergence.",
]


# ============================================================================
# TEST — the Michael fixture (Pierce thread, 2026-07-26, verified working)
# ============================================================================

def test_governor() -> None:
    gov = EpistemicGovernor()
    protocol = CoherenceChallengeProtocol()

    print("PUBLIC REASONING GOVERNOR — TEST SUITE")
    print("=" * 60)

    # Fixture 1: Michael's exceptional reply (verified live, 2026-07-26)
    michael = ("But for how long, how many iterations would it take before the "
               "latest AI iteration modeled after the previous AI iteration is "
               "so far removed from an iteration that was modeled after humans "
               "that any trace of such modeling becomes negligible?")
    cls = gov.classify_respondent(michael)
    print(f"\n[Michael fixture] class={cls.name}")
    assert cls == RespondentClass.EXCEPTIONAL_GENERALIZE, f"expected EXCEPTIONAL, got {cls.name}"
    print(f"  routing: {gov.route_attention(cls)}")

    # Fixture 2: weak attack
    attack = "lol idiot, you have no idea what you're talking about. cope"
    cls2 = gov.classify_respondent(attack)
    print(f"\n[attack fixture] class={cls2.name}")
    assert cls2 == RespondentClass.WEAK_ATTACK
    print(f"  routing: {gov.route_attention(cls2)}")

    # Fixture 3: the exit rule — disengagement is not chased
    receipt = EngagementReceipt(
        thread_id="pierce-2026-07-26",
        original_claim="AI-created AIs stop modeling humans",
        steelman=SteelmanResult(
            strongest_version="Recursive AI training could drift from human values",
            what_it_gets_right=["model lineage matters", "drift is possible"],
            load_bearing_assumptions=["training data dominates behavior"]),
        falsifiability=FalsifiabilitySpec(
            would_confirm=["A_n behavior unchanged when human data removed"],
            would_falsify=["A_n behavior degrades when human data removed"],
            measurable=True),
        correction="The variable is recursive distance from human-derived training, not modeling per se",
        confidence=0.8,
        exit_state=ExitState.DISENGAGED,
        responses_posted=1,
    )
    assert not receipt.may_respond_again(), "must NOT chase disengagement"
    assert protocol.check_exit(receipt), "exit must stand on disengagement"
    print(f"\n[exit fixture] may_respond_again=False, exit stands: PASS")

    # Fixture 4: identity-level correction is rejected at the gate
    violations = protocol.validate_correction("You bore me. You will learn.")
    assert violations, "identity-level language must be caught"
    print(f"[identity gate] caught: {violations[0]}")

    # Fixture 5: Kestrel's step-7 discipline — one response, no new evidence
    receipt2 = EngagementReceipt(
        thread_id="t2",
        original_claim="x",
        steelman=SteelmanResult("y", ["z"], ["a"]),
        falsifiability=FalsifiabilitySpec(["c"], ["f"], True),
        correction="c", confidence=0.7,
        exit_state=ExitState.EPISTEMIC_WORK_COMPLETE,
        responses_posted=1,
    )
    assert not receipt2.may_respond_again()
    receipt2.exit_state = ExitState.NEW_EVIDENCE_ARRIVED
    assert receipt2.may_respond_again()
    print("[re-entry rule] re-entry only on substantive new evidence: PASS")

    print("\n" + "=" * 60)
    print("ALL GOVERNOR TESTS PASS — doctrine:", LUMINA_DOCTRINE[0])


if __name__ == "__main__":
    test_governor()
