#!/usr/bin/env python3
"""CLI wrapper for generating repo-local OpenAPI artifacts."""

from __future__ import annotations

from helaicopter_api.server.openapi_artifacts import generate_openapi_artifacts


def main() -> None:
    outputs = generate_openapi_artifacts()
    print(f"Wrote {outputs.json_path}")
    print(f"Wrote {outputs.yaml_path}")


if __name__ == "__main__":
    main()
