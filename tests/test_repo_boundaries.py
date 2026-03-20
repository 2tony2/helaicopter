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
    significant_lines = [line.strip() for line in content.splitlines() if line.strip()]

    assert view_import in content
    assert rendered_view in content
    assert len(significant_lines) <= 12
    assert '"use client"' not in content

    for forbidden in (
        "@/components/plans",
        "@/features/plans/hooks/use-plans",
        "@/shared/",
        "@/components/ui/",
        "@/components/layout/",
        "usePlan(",
        "usePlans(",
        "Skeleton",
        "Breadcrumbs",
        "PageHeader",
    ):
        assert forbidden not in content


def _assert_deprecated_ts_reexport(relative_path: str, target: str) -> None:
    path = ROOT / relative_path
    assert path.exists()

    content = path.read_text(encoding="utf-8")
    significant_lines = [line.strip() for line in content.splitlines() if line.strip()]

    assert "@deprecated" in content
    assert (
        f'export * from "{target}";' in content
        or f"export * from '{target}';" in content
    )
    assert len(significant_lines) <= 2


def _assert_deprecated_python_reexport(relative_path: str, target: str) -> None:
    path = ROOT / relative_path
    assert path.exists()

    content = path.read_text(encoding="utf-8")
    significant_lines = [line.strip() for line in content.splitlines() if line.strip()]

    assert "class " not in content
    assert f"from {target} import " in content
    assert "__all__" in content
    assert len(significant_lines) <= 4


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
        rendered_view="<PlansIndexView />",
    )
    _assert_thin_route_shell(
        "src/app/plans/[slug]/page.tsx",
        view_import='@/views/plans/plan-detail-view',
        rendered_view="<PlanDetailView params={params} />",
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
    for required_snippet in (
        "no-restricted-imports",
        "src/views/**/*.ts?(x)",
        "src/features/**/*.ts?(x)",
        "src/shared/**/*.ts?(x)",
        "@/app/*",
        "@/views/*",
        "@/features/*",
    ):
        assert required_snippet in lint_config


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
