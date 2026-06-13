from typing import Dict, Optional, Any


def evaluate_condition(
    condition: Optional[Dict[str, Any]],
    reponses: Dict[int, str],
    secteur: Optional[str],
    taille: Optional[str],
    maturity: Optional[str] = None,
) -> bool:
    """Return True if the question should be shown given the current context."""
    if not condition:
        return True

    rule_type = condition.get("type")

    if rule_type == "response_equals":
        q_id = int(condition["question_id"])
        expected = str(condition["value"]).lower()
        return str(reponses.get(q_id, "")).lower() == expected

    if rule_type == "response_not_equals":
        q_id = int(condition["question_id"])
        expected = str(condition["value"]).lower()
        return str(reponses.get(q_id, "")).lower() != expected

    if rule_type == "response_in":
        q_id = int(condition["question_id"])
        values = [str(v).lower() for v in condition.get("values", [])]
        return str(reponses.get(q_id, "")).lower() in values

    if rule_type == "secteur_in":
        values = [str(v).lower() for v in condition.get("values", [])]
        return (secteur or "").lower() in values

    if rule_type == "taille_in":
        values = [str(v).lower() for v in condition.get("values", [])]
        return (taille or "").lower() in values

    if rule_type == "maturity_in":
        # Affiche la question seulement si la maturité calculée est dans la liste
        # Exemple : {"type":"maturity_in","values":["avance","expert"]}
        values = [str(v).lower() for v in condition.get("values", [])]
        return (maturity or "inconnu").lower() in values

    if rule_type == "maturity_min":
        # Affiche si maturité >= niveau_min
        # Exemple : {"type":"maturity_min","level":"intermediaire"}
        order = ["inconnu", "debutant", "intermediaire", "avance", "expert"]
        min_level = str(condition.get("level", "inconnu")).lower()
        current = (maturity or "inconnu").lower()
        return order.index(current) >= order.index(min_level) if min_level in order else True

    if rule_type == "AND":
        return all(
            evaluate_condition(r, reponses, secteur, taille, maturity)
            for r in condition.get("rules", [])
        )

    if rule_type == "OR":
        return any(
            evaluate_condition(r, reponses, secteur, taille, maturity)
            for r in condition.get("rules", [])
        )

    return True  # règle inconnue → afficher par défaut


def build_context_hint(condition: Optional[Dict[str, Any]], secteur: str, taille: str) -> Optional[str]:
    """Generate a human-readable hint explaining why this question appears."""
    if not condition:
        return None

    rule_type = condition.get("type")

    if rule_type == "secteur_in":
        values = condition.get("values", [])
        return f"Secteur : {', '.join(values)}"

    if rule_type == "taille_in":
        values = condition.get("values", [])
        return f"Taille : {', '.join(values)}"

    if rule_type == "maturity_in":
        values = condition.get("values", [])
        labels = {"debutant": "Débutant", "intermediaire": "Intermédiaire",
                  "avance": "Avancé", "expert": "Expert"}
        readable = [labels.get(v, v) for v in values]
        return f"Niveau : {', '.join(readable)}"

    if rule_type == "maturity_min":
        labels = {"debutant": "Débutant", "intermediaire": "Intermédiaire",
                  "avance": "Avancé", "expert": "Expert"}
        level = condition.get("level", "")
        return f"À partir du niveau {labels.get(level, level)}"

    if rule_type == "response_equals":
        return "Suite à votre réponse précédente"

    if rule_type == "response_not_equals":
        return "Approfondissement de votre réponse"

    if rule_type == "response_in":
        return "En fonction de vos choix"

    if rule_type == "AND":
        hints = [
            h for r in condition.get("rules", [])
            if (h := build_context_hint(r, secteur, taille))
        ]
        return " · ".join(hints) if hints else None

    if rule_type == "OR":
        hints = [
            h for r in condition.get("rules", [])
            if (h := build_context_hint(r, secteur, taille))
        ]
        return hints[0] if hints else None

    return None


def compute_maturity(reponses: Dict[int, str], questions) -> str:
    """Compute cyber maturity level from current partial answers."""
    total_score = 0.0
    total_poids = 0

    for q in questions:
        val = reponses.get(q.id_question)
        if val is None:
            continue
        if q.type == "boolean":
            raw = 1.0 if str(val).lower() in ("oui", "true", "1", "yes") else 0.0
            s = (1.0 - raw) if q.inverse else raw
        elif q.type == "scale":
            try:
                s = float(val) / 5.0
            except (ValueError, ZeroDivisionError):
                s = 0.5
        else:
            s = 0.5
        total_score += s * q.poids
        total_poids += q.poids

    if total_poids == 0:
        return "inconnu"

    score = (total_score / total_poids) * 100
    if score < 30:
        return "debutant"
    if score < 55:
        return "intermediaire"
    if score < 75:
        return "avance"
    return "expert"


def build_visibility_map(questions, reponses: Dict[int, str], secteur: str, taille: str) -> Dict[int, bool]:
    """Return {question_id: bool} visibility — maturity computed from current answers."""
    maturity = compute_maturity(reponses, questions)
    return {
        q.id_question: evaluate_condition(q.condition, reponses, secteur, taille, maturity)
        for q in questions
    }
