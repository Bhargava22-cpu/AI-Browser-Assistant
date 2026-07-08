def flatten_profile(profile: dict) -> dict:
    """Turn the canonical nested profile (address dict, skills list) into a flat
    dict of string values for LLM prompting and heuristic keyword matching."""
    address = profile.get("address") or {}
    skills_list = profile.get("skills") or []

    address_parts = [
        address.get("street", ""),
        address.get("city", ""),
        address.get("state", ""),
        address.get("pincode", ""),
        address.get("country", ""),
    ]
    address_full = ", ".join(part for part in address_parts if part)

    flat = {
        "name": profile.get("name", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "address_street": address.get("street", ""),
        "address_city": address.get("city", ""),
        "address_state": address.get("state", ""),
        "address_pincode": address.get("pincode", ""),
        "address_country": address.get("country", ""),
        "address_full": address_full,
        "college": profile.get("college", ""),
        "degree": profile.get("degree", ""),
        "graduation_year": str(profile.get("graduation_year", "")),
        "skills": ", ".join(skills_list),
        "skills_list": skills_list,
        "resume_path": profile.get("resume_path", ""),
        "linkedin": profile.get("linkedin", ""),
        "github": profile.get("github", ""),
    }
    return flat
