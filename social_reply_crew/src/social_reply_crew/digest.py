from __future__ import annotations

from social_reply_crew.models import ReplyDigest, SelectedReply


def present_digest_and_collect_choices(digest: ReplyDigest) -> list[SelectedReply]:
    print("\n" + "=" * 88)
    print("SOCIAL REPLY DIGEST")
    print("=" * 88)
    print(digest.global_guidance.strip())

    selections: list[SelectedReply] = []
    for index, recommendation in enumerate(digest.recommendations, start=1):
        print("\n" + "-" * 88)
        print(f"Post {index}: {recommendation.author}")
        print(f"Link: {recommendation.post_url}")
        print("Original:")
        print(recommendation.original_text.strip())
        print("\nOption 1")
        print(recommendation.options[0].reply_text.strip())
        print(f"Why: {recommendation.options[0].rationale.strip()}")
        print("\nOption 2")
        print(recommendation.options[1].reply_text.strip())
        print(f"Why: {recommendation.options[1].rationale.strip()}")

        selection = _prompt_for_choice()
        chosen_option = None if selection == "s" else recommendation.options[int(selection) - 1]
        selections.append(
            SelectedReply(
                recommendation=recommendation,
                chosen_option=chosen_option,
            )
        )

    return selections


def _prompt_for_choice() -> str:
    while True:
        try:
            raw_value = input("\nChoose 1, 2, or s to skip: ").strip().lower()
        except EOFError:
            return "s"
        if raw_value in {"1", "2", "s", "skip"}:
            return "s" if raw_value in {"s", "skip"} else raw_value
        print("Please enter 1, 2, or s.")
