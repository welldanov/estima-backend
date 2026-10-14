from pathlib import Path

ROOT_DIR = Path("../data/raw/avito/almetyevsk")

OLD_NAME = "almetevsk"
NEW_NAME = "almetyevsk"


def rename_files(root_dir: Path, dry_run: bool = True) -> None:
    for path in root_dir.rglob("*"):
        if not path.is_file() or OLD_NAME not in path.name:
            continue

        new_path = path.with_name(path.name.replace(OLD_NAME, NEW_NAME))

        print(f"{path} -> {new_path}")

        if not dry_run:
            path.rename(new_path)


if __name__ == "__main__":
    rename_files(ROOT_DIR, dry_run=True)
