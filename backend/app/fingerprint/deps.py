"""Parse dependency files into package names, and map known packages to skills.

Packages are returned as "npm:<name>" or "pypi:<name>" so B3 ("in my
dependencies") can resolve them to GitHub repos later.
"""

import json
import re
import tomllib

# Packages worth showing as skills. Everything else is still kept as a dependency.
KNOWN: dict[str, tuple[str, str]] = {
    # npm → (tech, kind)
    "npm:react": ("react", "framework"),
    "npm:next": ("nextjs", "framework"),
    "npm:vue": ("vue", "framework"),
    "npm:svelte": ("svelte", "framework"),
    "npm:@angular/core": ("angular", "framework"),
    "npm:express": ("express", "framework"),
    "npm:fastify": ("fastify", "framework"),
    "npm:@nestjs/core": ("nestjs", "framework"),
    "npm:jest": ("jest", "library"),
    "npm:vitest": ("vitest", "library"),
    "npm:mocha": ("mocha", "library"),
    "npm:@playwright/test": ("playwright", "library"),
    "npm:cypress": ("cypress", "library"),
    "npm:tailwindcss": ("tailwind", "library"),
    "npm:redux": ("redux", "library"),
    "npm:@reduxjs/toolkit": ("redux", "library"),
    "npm:graphql": ("graphql", "library"),
    "npm:prisma": ("prisma", "library"),
    "npm:typescript": ("typescript", "language"),
    "npm:webpack": ("webpack", "tool"),
    "npm:vite": ("vite", "tool"),
    "npm:eslint": ("eslint", "tool"),
    # pypi
    "pypi:django": ("django", "framework"),
    "pypi:flask": ("flask", "framework"),
    "pypi:fastapi": ("fastapi", "framework"),
    "pypi:pytest": ("pytest", "library"),
    "pypi:pandas": ("pandas", "library"),
    "pypi:numpy": ("numpy", "library"),
    "pypi:scikit-learn": ("scikit-learn", "library"),
    "pypi:torch": ("pytorch", "library"),
    "pypi:tensorflow": ("tensorflow", "library"),
    "pypi:pydantic": ("pydantic", "library"),
    "pypi:sqlalchemy": ("sqlalchemy", "library"),
    "pypi:requests": ("requests", "library"),
    "pypi:httpx": ("httpx", "library"),
    "pypi:celery": ("celery", "library"),
    "pypi:langchain": ("langchain", "library"),
    "pypi:langgraph": ("langgraph", "library"),
}

_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _pypi(name: str) -> str:
    # PEP 503 normalisation: Django, django_rest == django-rest
    return "pypi:" + re.sub(r"[-_.]+", "-", name).lower()


def parse_package_json(text: str) -> set[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return set()
    names = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    return {f"npm:{n}" for n in names}


def _requirement_names(lines: list[str]) -> set[str]:
    out = set()
    for line in lines:
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        if match := _REQ_NAME.match(line):
            out.add(_pypi(match.group(1)))
    return out


def parse_requirements(text: str) -> set[str]:
    return _requirement_names(text.splitlines())


def parse_pyproject(text: str) -> set[str]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return set()
    project = data.get("project", {})
    lines = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        lines += group
    for group in data.get("dependency-groups", {}).values():
        lines += [g for g in group if isinstance(g, str)]
    poetry = data.get("tool", {}).get("poetry", {})
    lines += [n for n in poetry.get("dependencies", {}) if n.lower() != "python"]
    return _requirement_names(lines)


PARSERS = {
    "packageJson": parse_package_json,
    "requirements": parse_requirements,
    "pyproject": parse_pyproject,
}
