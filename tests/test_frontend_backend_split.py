from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_next_api_surface_is_removed_from_src() -> None:
    api_dir = ROOT / "src" / "app" / "api"
    route_files = sorted(path.relative_to(ROOT) for path in api_dir.rglob("route.ts")) if api_dir.exists() else []

    assert route_files == []


def test_route_only_node_backend_modules_are_removed() -> None:
    removed_paths = [
        "src/lib/analytics-query-backend.ts",
        "src/lib/conversation-dag.ts",
        "src/lib/conversation-summary-query-backend.ts",
        "src/lib/database-refresh.ts",
        "src/lib/evaluations.ts",
        "src/lib/orchestration-data.ts",
        "src/lib/subscription-settings.ts",
    ]

    present = [path for path in removed_paths if (ROOT / path).exists()]

    assert present == []


def test_readme_documents_fastapi_split_and_retained_compatibility_shim() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "src/app/api" not in readme
    assert "Compatibility shim" in readme
    assert "src/lib/client/normalize.ts" in readme


def test_docs_capture_local_fastapi_workflow_and_migration_validation() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    migration_doc = ROOT / "docs" / "fastapi-backend-rollout.md"

    assert "npm run api:dev" in readme
    assert "NEXT_PUBLIC_API_BASE_URL" in readme
    assert "python/helaicopter_api/" in readme
    assert "docs/fastapi-backend-rollout.md" in readme

    assert migration_doc.exists()

    content = migration_doc.read_text(encoding="utf-8")
    assert "npm run dev" in content
    assert "npm run api:dev" in content
    assert "npm run lint" in content
    assert "npm run build" in content
    assert "uv run --group dev pytest -q" in content


def test_src_tree_has_no_node_backend_runtime_imports() -> None:
    disallowed = (
        'from "fs"',
        'from "fs/promises"',
        'from "path"',
        'from "os"',
        'from "child_process"',
        'from "better-sqlite3"',
    )

    offenders: list[str] = []
    for path in sorted((ROOT / "src").rglob("*.ts")):
        if path.name.endswith(".test.ts"):
            continue

        content = path.read_text(encoding="utf-8")
        if any(token in content for token in disallowed):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []
