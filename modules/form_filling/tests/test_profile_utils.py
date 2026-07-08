from modules.form_filling.profile_utils import flatten_profile


def _full_profile() -> dict:
    return {
        "name": "Arjun Mehta",
        "email": "arjun.mehta@example.com",
        "phone": "+91-9876543210",
        "address": {
            "street": "42 Bandra West",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400050",
            "country": "India",
        },
        "college": "IIT Bombay",
        "degree": "B.Tech Computer Science",
        "graduation_year": 2024,
        "skills": ["Python", "JavaScript", "React"],
        "resume_path": "/tmp/resume.pdf",
        "linkedin": "https://linkedin.com/in/arjun-mehta",
        "github": "https://github.com/arjunmehta",
    }


def test_flatten_profile_full():
    flat = flatten_profile(_full_profile())

    assert flat["name"] == "Arjun Mehta"
    assert flat["email"] == "arjun.mehta@example.com"
    assert flat["address_city"] == "Mumbai"
    assert flat["address_full"] == "42 Bandra West, Mumbai, Maharashtra, 400050, India"
    assert flat["skills"] == "Python, JavaScript, React"
    assert flat["skills_list"] == ["Python", "JavaScript", "React"]
    assert flat["graduation_year"] == "2024"


def test_flatten_profile_missing_address_subfields():
    profile = _full_profile()
    profile["address"] = {"city": "Mumbai"}

    flat = flatten_profile(profile)

    assert flat["address_city"] == "Mumbai"
    assert flat["address_street"] == ""
    assert flat["address_full"] == "Mumbai"


def test_flatten_profile_empty_skills():
    profile = _full_profile()
    profile["skills"] = []

    flat = flatten_profile(profile)

    assert flat["skills"] == ""
    assert flat["skills_list"] == []


def test_flatten_profile_missing_address_entirely():
    profile = _full_profile()
    del profile["address"]

    flat = flatten_profile(profile)

    assert flat["address_full"] == ""
    assert flat["address_city"] == ""
