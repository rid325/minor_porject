"""Apply per-scheme answers consistently for results and notifications."""

from copy import deepcopy


def profile_for_scheme(profile, scheme_id):
    values = deepcopy(profile)
    answers = values.pop("scheme_answers", {}) or {}
    for path, answer in answers.get(scheme_id, {}).items():
        parts = path.split(".")
        if len(parts) > 3 or not all(parts):
            continue
        target = values
        for segment in parts[:-1]:
            target = target.setdefault(segment, {})
            if not isinstance(target, dict):
                break
        else:
            target[parts[-1]] = answer
    return values
