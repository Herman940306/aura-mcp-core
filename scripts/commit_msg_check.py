import re
import sys

PATTERN = re.compile(
    r"^(feat|fix|docs|chore|refactor|test|perf|ci)(!:)?\([^()]+\): .+",
    re.IGNORECASE,
)


def main():
    msg_file = sys.argv[1]
    with open(msg_file, encoding="utf-8") as f:
        content = f.read().strip().splitlines()[0]
    if not PATTERN.match(content):
        print(
            "ERROR: Commit message must follow conventional format: type(scope): summary"
        )
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
