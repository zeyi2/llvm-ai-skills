#!/usr/bin/env python3
"""Post a pending review to a GitHub PR.

Usage: post_review.py <repo> <pr_number> <review_json_file>

Example:
    post_review.py llvm/llvm-project 182543 /tmp/pr_182543_review.json

The JSON file should contain:
{
  "body": "Review summary text",
  "comments": [
    {
      "path": "path/to/file.cpp",
      "line": 42,
      "side": "RIGHT",
      "body": "Comment text here."
    }
  ]
}

The script automatically:
  - Fetches the latest commit SHA from the PR
  - Forces event to PENDING (never publishes)
  - Validates the JSON structure before posting

The review is created as PENDING — publish manually from GitHub.
"""

import json
import subprocess
import sys


def run_gh(*args):
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def get_latest_commit_sha(repo, pr_number):
    output = run_gh(
        "api", f"repos/{repo}/pulls/{pr_number}/commits", "--jq", ".[-1].sha"
    )
    if not output:
        raise RuntimeError("Could not fetch commit SHA")
    return output


def validate_review(review):
    if "body" not in review:
        raise ValueError("Missing 'body' field in review JSON")
    comments = review.get("comments", [])
    for i, c in enumerate(comments):
        for field in ("path", "line", "body"):
            if field not in c:
                raise ValueError(f"Comment {i}: missing '{field}'")
        c.setdefault("side", "RIGHT")


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <repo> <pr_number> <review_json_file>")
        print(f"Example: {sys.argv[0]} llvm/llvm-project 182543 /tmp/review.json")
        sys.exit(1)

    repo, pr_number, review_file = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(review_file) as f:
        review = json.load(f)

    validate_review(review)

    print(f"Fetching latest commit SHA for PR #{pr_number}...")
    commit_sha = get_latest_commit_sha(repo, pr_number)
    print(f"Commit: {commit_sha}")

    review["commit_id"] = commit_sha
    review["event"] = "PENDING"

    # Remove any accidentally set publish events
    for bad_event in ("APPROVE", "REQUEST_CHANGES", "COMMENT"):
        if review.get("event") == bad_event:
            review["event"] = "PENDING"

    comment_count = len(review.get("comments", []))

    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        json.dump(review, tmp)
        tmp_path = tmp.name

    try:
        print(f"Posting pending review with {comment_count} comments...")
        output = run_gh(
            "api", f"repos/{repo}/pulls/{pr_number}/reviews",
            "--input", tmp_path
        )
        print(output)
    finally:
        import os
        os.unlink(tmp_path)

    print()
    print(f"Pending review created with {comment_count} inline comments.")
    print(f"Go to the PR page to review and publish:")
    print(f"  https://github.com/{repo}/pull/{pr_number}")


if __name__ == "__main__":
    main()
