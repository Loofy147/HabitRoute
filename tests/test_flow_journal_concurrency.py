from __future__ import annotations

import multiprocessing
from pathlib import Path
import tempfile
import unittest

from habitroute.flows import FlowEvent, FlowEventKind, JsonlFlowJournal


def _append_flow_event(
    root: str,
    run_id: str,
    event_id: str,
    first_loaded,
    second_loaded,
    release_first,
    started,
    results,
    is_first: bool,
) -> None:
    journal = JsonlFlowJournal(root)
    method_name = "_load_unlocked" if hasattr(journal, "_load_unlocked") else "load"
    original_load = getattr(journal, method_name)

    def gated_load(selected_run_id: str):
        events = original_load(selected_run_id)
        if is_first:
            first_loaded.set()
            if not release_first.wait(15):
                raise TimeoutError("first journal writer was not released")
        else:
            second_loaded.set()
        return events

    setattr(journal, method_name, gated_load)
    started.set()
    event = FlowEvent(
        run_id=run_id,
        sequence=1,
        event_id=event_id,
        kind=FlowEventKind.STARTED,
        node_id="start",
        payload=(("worker", event_id),),
    )
    try:
        journal.append(event)
        results.put(("ok", event_id))
    except BaseException as exc:
        results.put(("error", f"{event_id}:{type(exc).__name__}:{exc}"))


def _hold_flow_lock(root: str, run_id: str, acquired, release) -> None:
    journal = JsonlFlowJournal(root)
    with journal._run_lock(run_id):
        acquired.set()
        release.wait(30)


class FlowJournalConcurrencyTests(unittest.TestCase):
    def test_two_processes_cannot_commit_the_same_run_sequence(self):
        context = multiprocessing.get_context("spawn")
        first_loaded = context.Event()
        second_loaded = context.Event()
        release_first = context.Event()
        first_started = context.Event()
        second_started = context.Event()
        results = context.Queue()

        with tempfile.TemporaryDirectory() as temporary:
            root = str(Path(temporary))
            first = context.Process(
                target=_append_flow_event,
                args=(
                    root, "run-race", "event-first", first_loaded, second_loaded,
                    release_first, first_started, results, True,
                ),
            )
            second = context.Process(
                target=_append_flow_event,
                args=(
                    root, "run-race", "event-second", first_loaded, second_loaded,
                    release_first, second_started, results, False,
                ),
            )

            first.start()
            self.assertTrue(first_loaded.wait(5), "first process did not reach its read phase")
            second.start()
            self.assertTrue(second_started.wait(5), "second process did not start")
            try:
                second_entered_before_release = second_loaded.wait(1)
            finally:
                release_first.set()

            first.join(10)
            second.join(10)
            self.assertFalse(first.is_alive(), "first writer did not exit")
            self.assertFalse(second.is_alive(), "second writer did not exit")
            self.assertEqual(first.exitcode, 0)
            self.assertEqual(second.exitcode, 0)

            outcomes = sorted((results.get(timeout=2), results.get(timeout=2)))
            events = JsonlFlowJournal(root).load("run-race")

            self.assertFalse(
                second_entered_before_release,
                "second process read the same sequence before the first append committed",
            )
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].sequence, 1)
            self.assertEqual(sorted(status for status, _ in outcomes), ["error", "ok"])

    def test_process_termination_releases_per_run_lock(self):
        context = multiprocessing.get_context("spawn")
        acquired = context.Event()
        release = context.Event()

        with tempfile.TemporaryDirectory() as temporary:
            root = str(Path(temporary))
            holder = context.Process(
                target=_hold_flow_lock,
                args=(root, "run-crash", acquired, release),
            )
            holder.start()
            self.assertTrue(acquired.wait(5), "child did not acquire flow lock")
            holder.terminate()
            holder.join(5)
            self.assertFalse(holder.is_alive())

            event = FlowEvent(
                run_id="run-crash",
                sequence=1,
                event_id="after-process-death",
                kind=FlowEventKind.STARTED,
                node_id="start",
            )
            JsonlFlowJournal(root).append(event)
            persisted = JsonlFlowJournal(root).load("run-crash")
            self.assertEqual([item.event_id for item in persisted], ["after-process-death"])


if __name__ == "__main__":
    unittest.main()
