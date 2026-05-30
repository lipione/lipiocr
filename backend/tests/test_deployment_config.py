from pathlib import Path


def test_on_prem_deployment_pack_contains_required_files():
    required = [
        "deploy/compose/README.md",
        "deploy/compose/nginx-lipiocr.conf",
        "deploy/helm/lipiocr/Chart.yaml",
        "deploy/helm/lipiocr/values.yaml",
        "deploy/scripts/validate-env.sh",
        "deploy/scripts/backup.sh",
        "deploy/scripts/restore.sh",
        "deploy/scripts/health-check.sh",
    ]

    for item in required:
        assert Path("../" + item).exists(), item


def test_validate_env_script_rejects_placeholder_secrets(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LIPIOCR_API_AUTH_ENABLED=true",
                "LIPIOCR_API_KEYS=replace-maker-key:maker",
                "LIPIOCR_PREVIEW_TOKEN_SECRET=replace-with-secret",
                "POSTGRES_PASSWORD=replace-with-db-password",
                "MINIO_ROOT_PASSWORD=replace-with-minio-password",
                "NEXT_PUBLIC_API_BASE_URL=auto",
            ]
        ),
        encoding="utf-8",
    )

    import subprocess

    result = subprocess.run(
        ["../deploy/scripts/validate-env.sh", str(env_file)],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "placeholder" in result.stderr
