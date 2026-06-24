import asyncio
import json
from pathlib import Path


async def load_profile(path: str) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _read_json, path)


def _read_json(path: str) -> dict:
    file = Path(path)
    if not file.exists():
        raise FileNotFoundError(f"Profile not found: {path}")
    with open(file) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in {path}: {e.msg}", e.doc, e.pos)


def display_profile(profile: dict) -> None:
    print("=" * 40)
    print("       USER PROFILE")
    print("=" * 40)
    print(f"  Name      : {profile.get('name', 'N/A')}")
    print(f"  Email     : {profile.get('email', 'N/A')}")
    print(f"  Phone     : {profile.get('phone', 'N/A')}")

    addr = profile.get("address", {})
    if addr:
        print(f"  Address   : {addr.get('street')}, {addr.get('city')}")
        print(f"              {addr.get('state')} - {addr.get('pincode')}, {addr.get('country')}")

    print(f"  College   : {profile.get('college', 'N/A')}")
    print(f"  Degree    : {profile.get('degree', 'N/A')} ({profile.get('graduation_year', 'N/A')})")

    skills = profile.get("skills", [])
    if skills:
        print(f"  Skills    : {', '.join(skills)}")

    print(f"  LinkedIn  : {profile.get('linkedin', 'N/A')}")
    print(f"  GitHub    : {profile.get('github', 'N/A')}")
    print("=" * 40)


async def main():
    profile_path = Path(__file__).parent.parent / "data" / "user_profile.json"
    profile = await load_profile(str(profile_path))
    display_profile(profile)


if __name__ == "__main__":
    asyncio.run(main())
