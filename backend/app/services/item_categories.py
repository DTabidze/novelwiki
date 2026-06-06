ITEM_CATEGORIES = (
    "Manual",
    "Weapon",
    "Artifact",
    "Pill",
    "Treasure",
    "Resource",
    "Medicine",
    "Scroll",
    "Quest Item",
    "Other",
)

ITEM_CATEGORY_LOOKUP = {
    category.lower(): category
    for category in ITEM_CATEGORIES
}


def normalize_item_category(value):
    if value in (None, ""):
        return None

    normalized_value = " ".join(str(value).strip().split()).lower().replace("_", " ")
    return ITEM_CATEGORY_LOOKUP.get(normalized_value)
