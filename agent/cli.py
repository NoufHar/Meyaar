"""CLI runner for the Error Analysis Agent.

Examples (from repository root):

    # against the team Postgres (needs meyaar_db + rule engine run present)
    python -m agent.cli analyze 8f3a...-uuid

    # offline demo against an in-memory store seeded from a fixture file
    python -m agent.cli analyze 8f3a...-uuid --demo agent/tests/fixtures/sample_run.json
"""
from __future__ import annotations

import argparse
import json
import sys


def _uuid_candidate(value: str) -> str:
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agent.cli",
                                     description="Meyaar Error Analysis Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="Run error analysis for a run_id")
    p_analyze.add_argument("run_id", help="validation run UUID")
    p_analyze.add_argument("--demo", default="",
                           help="Path to a JSON fixture of validation_results; "
                                "use an in-memory repo instead of Postgres")
    p_analyze.add_argument("--out", default="", help="Write result JSON to a file")
    p_analyze.add_argument("--pretty", action="store_true")

    p_chat = sub.add_parser("chat", help="Chat about a run's engine results (needs LLM key)")
    p_chat.add_argument("run_id", help="validation run UUID")
    p_chat.add_argument("--ask", default="",
                        help="Single question (non-interactive); omit for a REPL")
    p_chat.add_argument("--speak", action="store_true",
                        help="Read each answer aloud via TTS (macOS 'say')")
    args = parser.parse_args(argv)

    if args.command == "analyze":
        return _cmd_analyze(args)
    if args.command == "chat":
        return _cmd_chat(args)
    return 2


def _cmd_chat(args) -> int:
    import uuid

    from agent.chat import answer_question
    from agent.core.llm import get_llm
    from agent.db.postgres import PostgresRepository

    # run_id must be a validation-run UUID (not a rule id like RD001/RD002)
    try:
        uuid.UUID(args.run_id)
    except ValueError:
        print(f"error: '{args.run_id}' is not a valid run UUID.\n"
              "chat expects a run_id from public.validation_results "
              "(a UUID like 8f0a1b2c-...), NOT a rule id such as RD001.\n"
              "Run an analysis first to get one:\n"
              "  python -m src.pipeline  # or  bash agent/scripts/live_test.sh", file=sys.stderr)
        return 2

    repo = PostgresRepository()
    llm = get_llm()
    if llm is None:
        print("chat requires an LLM key.\n"
              "Fix: edit agent/.env -> MEYAAR_LLM_API_KEY=<your openrouter key>\n"
              "and make sure MEYAAR_ALLOW_LLM is NOT 'false' in this shell "
              "(run: unset MEYAAR_ALLOW_LLM).\n"
              "Check: agent/.venv/bin/python -c "
              "\"from agent.core.config import settings; "
              "print(settings.llm_enabled, len(settings.llm_api_key))\"",
              file=sys.stderr)
        return 2

    if args.ask:
        pass  # single-shot mode
    else:
        print("Chatting about run", args.run_id, "- type 'exit' to quit.\n")

    while True:
        if not args.ask:
            try:
                q = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not q:
                continue
            if q.lower() in {"exit", "quit", "q"}:
                break
        else:
            q = args.ask
        try:
            out = answer_question(repo, args.run_id, q, llm=llm)
        except Exception as exc:
            print(f"error: {exc}")
            if args.ask:
                return 1
            continue
        print(f"agent> {out['answer']}")
        if out.get("sources"):
            print(f"       (sources: {', '.join(out['sources'])})")
        if args.speak:
            try:
                from agent.voice import text_to_speech
                text_to_speech(out["answer"])
            except Exception as exc:
                print(f"       (tts skipped: {exc})")
        print()
        if args.ask:
            break
    return 0


def _cmd_analyze(args) -> int:
    repo = None
    if args.demo:
        from agent.db.memory import InMemoryRepository, load_fixture_results
        results = load_fixture_results(args.demo)
        repo = InMemoryRepository(results=results)
        print(f"[cli] demo mode: {len(results)} seeded validation result(s)")

    from agent.graph.builder import run_analysis
    try:
        out = run_analysis(args.run_id, repository=repo)
    except Exception as exc:
        print(f"error: analysis failed: {exc}", file=sys.stderr)
        return 1

    summary = out.get("summary") or {}
    analyses = out.get("analyses", [])
    print(f"run_id      : {args.run_id}")
    print(f"results     : {out.get('results_loaded', 0)}  analyzed: {len(analyses)}")
    if summary:
        print(f"total errors: {summary.get('total_errors')} "
              f"(critical {summary.get('critical_errors')}, "
              f"high {summary.get('high_errors')}, medium {summary.get('medium_errors')})")
        print(f"most common : {summary.get('most_common_error')}")
        print("priority    :")
        for a in summary.get("priority_actions", []):
            print(f"  - {a}")
    for a in analyses:
        mark = "REVIEW" if a.get("human_review_required") else "ok"
        print(f"  [{mark:>6}] {a.get('rule_id')} {a.get('severity', ''):>8} "
              f"{a.get('status', ''):>20}  "
              f"{a.get('layer_name')}/{a.get('feature_id') or '-'}: "
              f"{a.get('explanation', '')[:110]}")
    if out.get("errors"):
        print("errors      :")
        for e in out["errors"]:
            print(f"  - {e}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(f"\nresult written to {args.out}")
    elif args.pretty:
        print("\n" + json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
