from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _assert_paths_exist(relative_paths: list[str]) -> None:
    missing = [path for path in relative_paths if not (ROOT / path).exists()]
    assert missing == []


def _assert_thin_route_shell(
    relative_path: str,
    *,
    view_import: str,
    rendered_view: str,
) -> None:
    path = ROOT / relative_path
    assert path.exists()

    content = path.read_text(encoding="utf-8")
    assert view_import in content
    assert rendered_view in content
    assert '"use client"' not in content
    assert "'use client'" not in content
    assert "export default function " in content

    for forbidden in (
        "use(",
        "usePlan(",
        "usePlans(",
        "@/features/",
        "@/components/",
        "@/shared/ui/",
        "@/shared/layout/",
        "Skeleton",
        "Breadcrumbs",
        "PageHeader",
    ):
        assert forbidden not in content

    default_export_count = content.count("export default function ")
    assert default_export_count == 1
    assert content.count("function ") - default_export_count == 0


def _eslint_override_objects(content: str) -> list[str]:
    objects: list[str] = []
    depth = 0
    start: int | None = None
    in_string: str | None = None
    escape = False

    for index, char in enumerate(content):
        if in_string is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
            continue

        if char in ("'", '"', "`"):
            in_string = char
            continue

        if char == "{":
            if depth == 0:
                start = index
            depth += 1
            continue

        if char == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(content[start : index + 1])
                start = None

    return objects


def _ts_real_statements(content: str) -> list[str]:
    lines = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//") or line.startswith("/*") or line.startswith("*") or line.startswith("*/"):
            continue
        lines.append(line)

    joined = " ".join(lines)
    statements = [statement.strip() for statement in joined.split(";") if statement.strip()]
    return statements


def _python_real_statements(content: str) -> list[str]:
    return [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _assert_eslint_layer_guardrail(
    content: str,
    *,
    files_glob: str,
    restricted_patterns: tuple[str, ...],
) -> None:
    matching_blocks = [
        block
        for block in _eslint_override_objects(content)
        if files_glob in block and "no-restricted-imports" in block
    ]
    assert matching_blocks != []

    for block in matching_blocks:
        if "rules" not in block or "patterns" not in block:
            continue
        if all(pattern in block for pattern in restricted_patterns):
            return

    assert False


def _assert_deprecated_ts_reexport(relative_path: str, target: str) -> None:
    path = ROOT / relative_path
    assert path.exists()

    content = path.read_text(encoding="utf-8")
    statements = _ts_real_statements(content)

    assert "@deprecated" in content
    assert len(statements) == 1

    statement = statements[0]
    has_export_all = f'export * from "{target}"' in statement or f"export * from '{target}'" in statement
    has_named_reexport = (
        (f'from "{target}"' in statement or f"from '{target}'" in statement) and "export {" in statement
    )
    assert has_export_all or has_named_reexport

    for forbidden in (
        "function ",
        "class ",
        "const ",
        "let ",
        "return ",
        "=>",
        "useState(",
        "useEffect(",
        "useMemo(",
        "useCallback(",
        "<",
        "document.",
        "window.",
    ):
        assert forbidden not in content


def _assert_deprecated_python_reexport(relative_path: str, target: str) -> None:
    path = ROOT / relative_path
    assert path.exists()

    content = path.read_text(encoding="utf-8")
    statements = _python_real_statements(content)

    assert "@deprecated" in content
    assert len(statements) == 2
    assert statements[0].startswith(f"from {target} import ")
    assert statements[1].startswith("__all__ =")

    for forbidden in (
        "class ",
        "def ",
        "if ",
        "for ",
        "while ",
        "try:",
        "try {",
        "with ",
        "match ",
        "return ",
        "print(",
        "raise ",
    ):
        assert forbidden not in content


def test_repo_boundaries_shared_layer_paths() -> None:
    _assert_paths_exist(
        [
            "src/shared/ui/badge.tsx",
            "src/shared/ui/button.tsx",
            "src/shared/ui/card.tsx",
            "src/shared/ui/scroll-area.tsx",
            "src/shared/ui/skeleton.tsx",
            "src/shared/layout/breadcrumbs.tsx",
            "src/shared/layout/page-header.tsx",
        ]
    )

    _assert_deprecated_ts_reexport("src/components/ui/badge.tsx", "@/shared/ui/badge")
    _assert_deprecated_ts_reexport("src/components/ui/button.tsx", "@/shared/ui/button")
    _assert_deprecated_ts_reexport("src/components/ui/card.tsx", "@/shared/ui/card")
    _assert_deprecated_ts_reexport(
        "src/components/ui/scroll-area.tsx",
        "@/shared/ui/scroll-area",
    )
    _assert_deprecated_ts_reexport("src/components/ui/skeleton.tsx", "@/shared/ui/skeleton")
    _assert_deprecated_ts_reexport(
        "src/components/layout/breadcrumbs.tsx",
        "@/shared/layout/breadcrumbs",
    )
    _assert_deprecated_ts_reexport(
        "src/components/layout/page-header.tsx",
        "@/shared/layout/page-header",
    )


def test_repo_boundaries_plans_feature_paths() -> None:
    _assert_paths_exist(
        [
            "src/features/plans/components/plan-panel.tsx",
            "src/features/plans/components/plan-viewer.tsx",
            "src/features/plans/hooks/use-plans.ts",
        ]
    )

    _assert_deprecated_ts_reexport(
        "src/components/plans/plan-panel.tsx",
        "@/features/plans/components/plan-panel",
    )
    _assert_deprecated_ts_reexport(
        "src/components/plans/plan-viewer.tsx",
        "@/features/plans/components/plan-viewer",
    )
    _assert_deprecated_ts_reexport(
        "src/hooks/use-plans.ts",
        "@/features/plans/hooks/use-plans",
    )


def test_repo_boundaries_plans_route_shells() -> None:
    _assert_paths_exist(
        [
            "src/views/plans/plans-index-view.tsx",
            "src/views/plans/plan-detail-view.tsx",
        ]
    )

    _assert_thin_route_shell(
        "src/app/plans/page.tsx",
        view_import='@/views/plans/plans-index-view',
        rendered_view="<PlansIndexView",
    )
    _assert_thin_route_shell(
        "src/app/plans/[slug]/page.tsx",
        view_import='@/views/plans/plan-detail-view',
        rendered_view="<PlanDetailView",
    )


def test_repo_boundaries_architecture_note_and_lint() -> None:
    architecture_note = ROOT / "docs/architecture/repo-layers.mdx"
    assert architecture_note.exists()

    content = architecture_note.read_text(encoding="utf-8").lower()
    for required_term in (
        "src/app",
        "src/views",
        "src/features",
        "src/shared",
        "router",
        "application",
        "domain",
        "contracts",
        "ports",
        "adapters",
    ):
        assert required_term in content

    lint_config = _read("eslint.config.mjs")
    _assert_eslint_layer_guardrail(
        lint_config,
        files_glob="src/views/**/*.ts?(x)",
        restricted_patterns=("@/app/*",),
    )
    _assert_eslint_layer_guardrail(
        lint_config,
        files_glob="src/features/**/*.ts?(x)",
        restricted_patterns=("@/app/*", "@/views/*"),
    )
    _assert_eslint_layer_guardrail(
        lint_config,
        files_glob="src/shared/**/*.ts?(x)",
        restricted_patterns=("@/app/*", "@/views/*", "@/features/*"),
    )


def test_repo_boundaries_backend_plans_layers() -> None:
    _assert_paths_exist(
        [
            "python/helaicopter_api/contracts/plans.py",
            "python/helaicopter_api/domain/plans.py",
        ]
    )

    _assert_deprecated_python_reexport(
        "python/helaicopter_api/schema/plans.py",
        "helaicopter_api.contracts.plans",
    )
