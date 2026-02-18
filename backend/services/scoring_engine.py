import os
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

# Configuration
TAMPER_THRESHOLD = int(os.getenv("VERIDOC_TAMPER_THRESHOLD", "70"))

def calculate_final_score(
    pipeline_type: str,
    local_report: Dict[str, Any],
    ai_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministic Intelligent Scoring Calculator (Universal Dynamic Engine).
    Uses Boolean-Masked Weighted Averaging to exclude invalid components.
    
    Formula: S_total = Sum(Si * Wi * Bi) / Sum(Wi * Bi)
    """
    
    # --- HELPER FUNCTION ---
    def weighted_average(components: List[tuple]) -> float:
        """
        Calculates dynamic weighted average.
        components: List of tuples (Score, Weight, IsValid)
        """
        numerator = 0.0
        denominator = 0.0
        
        for score, weight, is_valid in components:
            if is_valid:
                numerator += score * weight
                denominator += weight
        
        if denominator == 0:
            return 100.0 # Default clean if everything invalid
        
        return numerator / denominator

    # 1. Extract Inputs
    ai_dry_score = ai_result.get("authenticity_score", 50)
    validation_map = ai_result.get("validation_map", {})
    details = local_report.get("details", {})
    
    # Defensive initialization of flags
    has_visual = False
    has_struct = False
    has_crypto = False
    
    score_components = {}

    # --- PART A: VISUAL SCORING (Dynamic) ---
    visual_score = 100.0
    
    analyzed_images = details.get('analyzed_images', [])
    if pipeline_type == "visual" and not analyzed_images:
        # Implicit single image context
        analyzed_images = [{"visual_report": local_report}]
        
    if analyzed_images:
        has_visual = True
        img_scores = []
        
        for img in analyzed_images:
            idx = img.get("index", 0)
            v_rep = img.get("visual_report", {}).get("details", {}) or img.get("visual_report", {}) # specific or top
            
            # --- SOFT GATING HELPER ---
            def get_gate(component_key_base, specific_idx=None):
                """
                Returns a Multiplier (0.0 to 1.0).
                1.0 = Fully Valid (AI says 0% Invalid).
                0.0 = Fully Invalid (AI says 100% Invalid).
                """
                # Try specific key first (e.g., segformer_img_0), then generic (segformer)
                keys_to_try = []
                if specific_idx is not None:
                    keys_to_try.append(f"{component_key_base}_img_{specific_idx}")
                keys_to_try.append(component_key_base)
                
                for k in keys_to_try:
                    if k in validation_map:
                        entry = validation_map[k]
                        # Fallback for old prompt format if key missing
                        raw_conf = entry.get("invalidation_confidence", 0)
                        
                        # ROBUST PARSING: Handle "80%", "80", 80, None
                        try:
                            if raw_conf is None:
                                inv_conf = 0.0
                            elif isinstance(raw_conf, (int, float)):
                                inv_conf = float(raw_conf)
                            else:
                                # Clean string
                                clean_s = str(raw_conf).replace('%', '').strip()
                                inv_conf = float(clean_s) if clean_s else 0.0
                        except Exception:
                            inv_conf = 0.0 # Default to valid if parsing fails

                        # Backward compatibility: if "Invalid" but no confidence, assume 100%
                        if entry.get("verdict", "").upper() == "INVALID" and "invalidation_confidence" not in entry:
                             inv_conf = 100.0
                             
                        return max(0.0, 1.0 - (inv_conf / 100.0))
                
                return 1.0 # Default to fully valid if AI didn't mention it
            
            # 1. SegFormer
            sf_conf = v_rep.get("semantic_segmentation", {}).get("confidence_score", 0.0)
            sf_score = max(0, 100 - (sf_conf * 100))
            sf_gate = get_gate("segformer", idx)
            
            # 2. TruFor
            tf_data = v_rep.get("trufor", {})
            tf_score = tf_data.get("trust_score", 1.0) * 100
            tf_gate = get_gate("trufor", idx)
            
            # 3. ELA
            ela_val = v_rep.get("ela", {}).get("max_difference", 0.0)
            ela_score = max(0, 100 - float(ela_val))
            ela_gate = get_gate("ela", idx)
            
            # 4. Noise
            var_val = float(v_rep.get("noise_analysis", {}).get("average_diff", 0.0))
            var_score = max(0, 100 - (var_val * 10))
            noise_gate = get_gate("noise", idx) # AI usually doesn't judge noise, but we allow it
            
            # Calculate Dynamic Visual Score
            # Weights: SegFormer 0.35, TruFor 0.30, ELA 0.15, Noise 0.10, DCT 0.10
            # Note: We apply the GATE to the WEIGHT.
            
            v_components = [
                (sf_score, 0.35 * sf_gate, True),
                (tf_score, 0.30 * tf_gate, True),
                (ela_score, 0.15 * ela_gate, True),
                (var_score, 0.20 * noise_gate, True)
            ]
            
            img_scores.append(weighted_average(v_components))
            
        visual_score = min(img_scores) if img_scores else 100.0
        score_components["Visual Forensics"] = round(visual_score, 1) if has_visual else "N/A"

    # --- PART B: STRUCTURAL SCORING (Dynamic) ---
    # Risk-based inversion
    struct_risk = local_report.get("score", 0.0)
    struct_score = max(0, 100 - (struct_risk * 100))
    
    # Soft Gate for Metadata
    # If AI says "Metadata Invalid" (e.g. Producer is weird but harmless), we dampen it.
    # DISABLED: Ensuring structural analysis always hits the final score for now.
    meta_gate = 1.0
         
    # We don't separate struct components easily here (it's one aggregate score).
    # We apply the gate to the whole structural score "Validation".
    
    # Structural Validity: Does it exist in the report?
    struct_breakdown = local_report.get("breakdown", [])
    has_struct = len(struct_breakdown) > 0 or "metadata" in details or "eof_markers_found" in details
    
    score_components["Structural"] = round(struct_score, 1) if has_struct else "N/A"
    
    # --- PART C: CRYPTO SCORING (Dynamic) ---
    crypto_score = 100.0
    has_crypto = False
    
    # CRITICAL: Crypto Gate is ALWAYS 1.0 (No AI filtering for deterministic crypto checks)
    # The crypto_score itself already encodes the failure (0.0 = broken, 100.0 = valid)
    # Unlike visual tools (SegFormer/TruFor) which have false positives, crypto is binary.
    sig_gate = 1.0

    if "signatures" in details and details["signatures"]:
        has_crypto = True
        sigs = details["signatures"]
        
        # Custom Scoring Logic for Hybrid Trust
        # Rule:
        # - Broken (Hash mismatch) = 0.0 (FAIL)
        # - Revoked = 10.0 (FAIL)
        # - Trusted & Intact = 1.0 (PASS)
        # - Untrusted but Intact = 0.8 (PASS with Warning) - This matches "Integrity Verified"
        # - Policy Error (Weak Key) = 0.9 (PASS with Warning)
        
        score_accum = 0.0
        
        for s in sigs:
            if not s.get('intact', False):
                score_accum += 0.0 # Document hacked
            elif s.get('revoked', False):
                score_accum += 0.1 # Revoked (technically valid sig at time? No, usually bad)
            elif s.get('valid', False) and s.get('trusted', False):
                score_accum += 1.0 # Gold Standard
            elif s.get('intact', False) and not s.get('trusted', False):
                score_accum += 0.8 # Silver Standard (Integrity OK, Identity Unknown)
            elif s.get('weak_key', False) or s.get('weak_hash', False):
                 score_accum += 0.9 # Bronze (Old but valid)
            else:
                 score_accum += 0.5 # Unknown state
                 
        crypto_score = (score_accum / len(sigs)) * 100
    
    score_components["Crypto"] = round(crypto_score, 1) if has_crypto else "N/A"

    # --- SAFETY CHECK: PIPELINE CONSISTENCY ---
    # If the pipeline detected signatures (Cryptographic Type) but the analysis 
    # failed to extract/score them (e.g. library mismatch or crash without fallback),
    # we MUST NOT default to 100. We must fail safe (Score 0).
    if pipeline_type == "cryptographic" and not has_crypto:
        if "signatures" not in details or not details["signatures"]:
            # This implies the file WAS detected as crypto, but analysis found nothing.
            # Suspicious structural tamper (removed sigs?) or library failure.
            score_components["Crypto"] = 0.0
            crypto_score = 0.0
            has_crypto = True
            # Also define the gate effectively to 1.0 so it counts
            sig_gate = 1.0


    # --- FINAL DYNAMIC PIPELINE BLENDING ---
    
    # Revised Weights for Universal Dynamic (Loaded from Env):
    w_crypto = float(os.getenv("SCORING_WEIGHT_CRYPTO", 0.35))
    w_struct = float(os.getenv("SCORING_WEIGHT_STRUCTURAL", 0.35))
    w_visual = float(os.getenv("SCORING_WEIGHT_VISUAL", 0.30))

    final_components = [
        (crypto_score, w_crypto * sig_gate, has_crypto),
        (struct_score, w_struct * meta_gate, has_struct),
        (visual_score, w_visual, has_visual) # Visual gates already applied to sub-components
    ]
    
    weighted_tech = weighted_average(final_components)
    
    tech_weight = float(os.getenv("SCORING_WEIGHT_TECH", 0.8))
    ai_weight = float(os.getenv("SCORING_WEIGHT_AI", 0.2))
    
    # STRICT FORMULA: No Safety Valves, No Dissent Resolution.
    # The score is exactly what the weights say it is.
    final_score = (weighted_tech * tech_weight) + (ai_dry_score * ai_weight)
    
    verdict = "Authentic" if final_score >= TAMPER_THRESHOLD else "Tampered"
    
    return {
        "authenticity_score": round(final_score),
        "verdict": verdict,
        "breakdown": score_components,
        "precise_scores": {
            "visual": visual_score,
            "structural": struct_score,
            "crypto": crypto_score,
            "tech_agg": weighted_tech,
            "final_score": final_score
        },
        "structural_breakdown_list": local_report.get("breakdown", []),
        "weights": {
            "visual": w_visual,
            "structural": w_struct,
            "crypto": w_crypto,
            "tech_agg": tech_weight,
            "ai_agg": ai_weight,
            "vis_segformer": 0.35,
            "vis_trufor": 0.30,
            "vis_ela": 0.15,
            "vis_noise": 0.20
        },
        "threshold": TAMPER_THRESHOLD,
        "ai_dry_score": ai_dry_score,
        "weighted_tech": weighted_tech
    }
