"""Small helpers shared by the application."""


def build_search_query(city: str, niche: str) -> str:
    return f"{niche.strip()} in {city.strip()}"
