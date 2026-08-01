"""Module name mapping and import resolution for common Python layouts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from app.analysis.parser import ImportInfo


@dataclass(slots=True)
class ResolvedImport:
    source_path: str
    imported_module: str
    imported_names: list[str]
    line_number: int
    target_path: str | None
    is_internal: bool
    confidence: str
    unresolved_reason: str | None = None


@dataclass(slots=True)
class ModuleMap:
    path_to_module: dict[str, str] = field(default_factory=dict)
    module_to_path: dict[str, str] = field(default_factory=dict)
    package_roots: list[str] = field(default_factory=list)

    def resolve_module(self, module_name: str) -> str | None:
        if module_name in self.module_to_path:
            return self.module_to_path[module_name]
        # package import → __init__.py
        init_key = f"{module_name}.__init__"
        if init_key in self.module_to_path:
            return self.module_to_path[init_key]
        return None


def build_module_map(python_paths: list[str]) -> ModuleMap:
    module_map = ModuleMap()
    has_src = any(path.startswith("src/") for path in python_paths)
    if has_src:
        module_map.package_roots.append("src")

    for path in python_paths:
        module = path_to_module_name(path)
        if not module:
            continue
        module_map.path_to_module[path] = module
        # Prefer non-__init__ collisions by first-writer; explicit init mapping too
        module_map.module_to_path.setdefault(module, path)
        if path.endswith("__init__.py"):
            pkg = module
            module_map.module_to_path.setdefault(pkg, path)

    return module_map


def path_to_module_name(path: str) -> str | None:
    pure = PurePosixPath(path)
    if pure.suffix != ".py":
        return None
    parts = list(pure.parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if not parts:
        return None
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    if not parts:
        return None
    return ".".join(parts)


def resolve_import(
    source_path: str,
    import_info: ImportInfo,
    module_map: ModuleMap,
) -> list[ResolvedImport]:
    """Resolve one import statement into zero or more resolved targets."""
    results: list[ResolvedImport] = []
    source_module = module_map.path_to_module.get(source_path)

    if import_info.level and import_info.level > 0:
        if not source_module:
            results.append(
                ResolvedImport(
                    source_path=source_path,
                    imported_module=import_info.module or "",
                    imported_names=import_info.names,
                    line_number=import_info.line_number,
                    target_path=None,
                    is_internal=False,
                    confidence="low",
                    unresolved_reason="relative_import_without_source_module",
                )
            )
            return results
        base_parts = source_module.split(".")
        # Relative imports are relative to the package containing the module
        if not source_path.endswith("__init__.py"):
            base_parts = base_parts[:-1]
        if import_info.level > len(base_parts) + 1:
            results.append(
                ResolvedImport(
                    source_path=source_path,
                    imported_module=import_info.module or "",
                    imported_names=import_info.names,
                    line_number=import_info.line_number,
                    target_path=None,
                    is_internal=False,
                    confidence="low",
                    unresolved_reason="relative_level_too_high",
                )
            )
            return results
        package_parts = base_parts[: len(base_parts) - (import_info.level - 1)]
        if import_info.module:
            absolute = ".".join([*package_parts, *import_info.module.split(".")])
            target = module_map.resolve_module(absolute)
            results.append(
                _make_resolved(
                    source_path,
                    absolute,
                    import_info,
                    target,
                )
            )
        else:
            # from . import sibling
            for name in import_info.names:
                absolute = ".".join([*package_parts, name])
                target = module_map.resolve_module(absolute)
                results.append(
                    _make_resolved(source_path, absolute, import_info, target, names=[name])
                )
        return results

    # Absolute import
    if not import_info.is_from:
        module_name = import_info.module or ""
        target = module_map.resolve_module(module_name)
        results.append(_make_resolved(source_path, module_name, import_info, target))
        return results

    # from package.module import name  OR from package import module
    base = import_info.module or ""
    target = module_map.resolve_module(base) if base else None
    if target:
        results.append(_make_resolved(source_path, base, import_info, target))
        return results

    # Try each imported name as a submodule
    matched_any = False
    for name in import_info.names:
        candidate = f"{base}.{name}" if base else name
        target = module_map.resolve_module(candidate)
        if target:
            matched_any = True
            results.append(
                _make_resolved(source_path, candidate, import_info, target, names=[name])
            )
    if not matched_any:
        results.append(_make_resolved(source_path, base, import_info, None))
    return results


def _make_resolved(
    source_path: str,
    module_name: str,
    import_info: ImportInfo,
    target: str | None,
    names: list[str] | None = None,
) -> ResolvedImport:
    is_internal = target is not None
    return ResolvedImport(
        source_path=source_path,
        imported_module=module_name,
        imported_names=names if names is not None else list(import_info.names),
        line_number=import_info.line_number,
        target_path=target,
        is_internal=is_internal,
        confidence="high" if is_internal else "low",
        unresolved_reason=None if is_internal else "external_or_unresolved",
    )


def detect_src_layout(root: Path) -> bool:
    return (root / "src").is_dir()
