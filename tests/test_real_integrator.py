"""The Factory against a real git Repo Host and the real Integrator, with a tiny real `make test`."""
from test_runs import TASK_EVENT, agent_runs, prompts

PROJECT = {
    "README": "base\n",
    "Makefile": ("test:\n\t@fail=0; for t in specs/*.sh; do if sh $$t; then echo \"ok $$t\"; "
                 "else echo \"FAIL $$t\"; fail=1; fi; done; exit $$fail\n"),
    "specs/base.sh": "true\n",
}
GREETING_SPEC = "grep -q hello src/greeting.txt\n"
IMPLEMENTED = {"src/greeting.txt": "hello\n"}
SCENARIO = {"tasks": {"t1": "add a greeting"}, "events": [TASK_EVENT]}


def factory(run_factory, agent=None, **extra):
    scenario = {**SCENARIO, "agent": {"implementor": [{"edits": IMPLEMENTED}],
                                      "acceptance-writer": [{"edits": {"specs/greeting.sh": GREETING_SPEC}}]},
                **extra}
    scenario["agent"].update(agent or {})
    return run_factory(scenario, real_git=PROJECT)


def test_green_run_lands_a_merge_of_both_branches_on_real_main(run_factory):
    out = factory(run_factory)

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "done"], out.events("task/t1", "infrastructure-error")
    assert out.git_main("src/greeting.txt") == "hello\n"
    assert out.git_main("specs/greeting.sh") == GREETING_SPEC
    assert any(s.startswith("Integrate") or s.startswith("Merge") for s in out.git_log_main())


def test_vacuous_specs_are_rejected_and_the_writer_retriggered(run_factory):
    out = factory(run_factory, agent={"acceptance-writer": [
        {"edits": {"specs/vacuous.sh": "true\n"}},
        {"edits": {"specs/vacuous.sh": GREETING_SPEC}}]})

    assert agent_runs(out).count("acceptance-writer") == 2
    assert agent_runs(out).count("implementor") == 1
    assert "ok specs/vacuous.sh" in prompts(out, "acceptance-writer")[1]
    assert out.git_main("specs/vacuous.sh") == GREETING_SPEC
    assert out.status("t1") == ["running", "done"]


def test_a_red_suite_sends_the_acceptance_report_to_the_implementor(run_factory):
    out = factory(run_factory, agent={"implementor": [
        {"edits": {"src/greeting.txt": "goodbye\n"}}, {"edits": IMPLEMENTED}]})

    assert "FAIL specs/greeting.sh" in prompts(out, "implementor")[1]
    assert out.git_main("src/greeting.txt") == "hello\n"
    assert out.status("t1") == ["running", "running", "done"]


def test_a_persisting_merge_conflict_blocks_the_task_and_leaves_main_untouched(run_factory):
    out = factory(run_factory, agent={
        "implementor": [{"edits": {**IMPLEMENTED, "README": "implementor\n"}}] * 2,
        "acceptance-writer": [{"edits": {"specs/greeting.sh": GREETING_SPEC, "README": "writer\n"}}]})

    assert out.status("t1") == ["running", "running", "blocked"]
    assert "CONFLICT" in prompts(out, "implementor")[1]
    assert out.git_main("README") == "base\n"
    assert out.git_main("src/greeting.txt") is None
    assert "CONFLICT" in str(out.state["status_body"]["t1"][-1]["history"])


def test_a_human_push_between_verdict_and_push_means_a_fresh_integrator_run(run_factory):
    out = factory(run_factory, main_moves_after_integrator=[1])

    assert len(out.state["integrator_runs"]) == 2
    assert out.git_main("human.txt") == "pushed by a human"
    assert out.git_main("src/greeting.txt") == "hello\n"
    assert out.status("t1") == ["running", "done"]
