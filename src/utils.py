from pathlib import Path


def path(end_point: str) -> Path:
    """Go back to certain directory from the current file"""
    root_path = Path(__file__).resolve()
    while root_path.name != end_point and root_path.parent != root_path:
        root_path = root_path.parent

    if root_path.parent == root_path:
        raise ValueError(f"Directory not found: {end_point}")

    return root_path


def get_root(root_name: str = "trading-system") -> Path:
    return path(root_name)
