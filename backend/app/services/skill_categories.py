SKILL_CATEGORIES = (
    "Technique",
    "Cultivation Method",
    "Divine Ability",
    "Spell",
    "Martial Art",
    "Combat Move",
    "Movement Skill",
    "Body Refinement",
    "Soul Skill",
    "Alchemy",
    "Formation",
    "Utility",
    "Other",
)

SKILL_CATEGORY_LOOKUP = {
    category.lower(): category
    for category in SKILL_CATEGORIES
}


def normalize_skill_category(value):
    if value in (None, ""):
        return None

    normalized_value = " ".join(str(value).strip().split()).lower()
    return SKILL_CATEGORY_LOOKUP.get(normalized_value)
