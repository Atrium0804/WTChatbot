import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))

import run_eval

EVALSET = Path(run_eval.EVAL_DIR) / "evalset.yaml"
PEILDATUM = run_eval.load_peildatum(EVALSET)

# Realistische shape van POST /v1/conversations (captured 2026-11-04):
# content zit top-level in het output-entry, niet onder "message".
REAL_OUTPUTS = [
    {
        "object": "entry",
        "type": "message.output",
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": [{"type": "text", "text": "even nadenken"}]}
        ],
    },
    {
        "object": "entry",
        "type": "tool.execution",
        "name": "document_library",
        "arguments": "{\"query\": \"verzet U15\"}",
        "info": {"result": "..."},
    },
    {
        "object": "entry",
        "type": "message.output",
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Maximaal 6,70 meter.\n\nBron: TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21"}
        ],
    },
]


class ExtractTextTests(unittest.TestCase):
    def test_real_conversations_shape(self) -> None:
        # Regressie: de oude code las out["message"]["content"] en kreeg ""
        # -> eval 0/20. Nu: top-level content, alleen text-chunks.
        self.assertEqual(
            run_eval.extract_text(REAL_OUTPUTS),
            "Maximaal 6,70 meter.\n\nBron: TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21",
        )

    def test_string_content(self) -> None:
        self.assertEqual(
            run_eval.extract_text([{"type": "message.output", "content": "platte tekst"}]),
            "platte tekst",
        )

    def test_tool_execution_entries_ignored(self) -> None:
        self.assertEqual(run_eval.extract_text(REAL_OUTPUTS[1:2]), "")


class AskWithRetryTests(unittest.TestCase):
    def test_retries_once_on_timeout_then_succeeds(self) -> None:
        import requests
        from unittest.mock import patch

        calls = {"n": 0}

        def fake_send(message, api_key, timeout, agent_id=None, conversation_id=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise requests.ReadTimeout("read timed out")
            return {"conversation_id": "c1", "outputs": []}

        with patch.object(run_eval, "send_message", side_effect=fake_send):
            response, error = run_eval.ask_with_retry("vraag", "key", agent_id="agent")
        self.assertEqual(response["conversation_id"], "c1")
        self.assertEqual(error, "")
        self.assertEqual(calls["n"], 2)

    def test_gives_up_after_attempts_and_reports_error(self) -> None:
        import requests
        from unittest.mock import patch

        with patch.object(
            run_eval, "send_message", side_effect=requests.ReadTimeout("read timed out")
        ):
            response, error = run_eval.ask_with_retry("vraag", "key", attempts=2, agent_id="agent")
        self.assertEqual(response, {})
        self.assertIn("ReadTimeout", error)

    def timeouts_per_poging(self, vraagtype: str) -> list:
        import requests
        from unittest.mock import patch

        timeouts = []

        def fake_send(message, api_key, timeout, agent_id=None, conversation_id=None):
            timeouts.append(timeout)
            raise requests.ReadTimeout("read timed out")

        with patch.object(run_eval, "send_message", side_effect=fake_send):
            run_eval.ask_with_retry("vraag", "key", vraagtype=vraagtype, agent_id="agent")
        return timeouts

    def test_websearch_krijgt_ruimere_timeout_en_extra_poging(self) -> None:
        self.assertEqual(self.timeouts_per_poging("websearch"), [300, 300, 300])

    def test_standaard_houdt_gewone_timeout(self) -> None:
        self.assertEqual(self.timeouts_per_poging("standaard"), [180, 180])


class RunConversationTests(unittest.TestCase):
    """Multi-turn (`beurten`) met dezelfde contextregels als de proxy (#44)."""

    AGENTS = {"ag_router": "router-agent", "ag_regio": "regio-agent", "ag_knwu": "knwu-agent"}

    def run_with(self, entry: dict, responses: list[dict]) -> tuple[dict, list[dict]]:
        from datetime import date
        from unittest.mock import patch

        sent = []

        def fake_send(message, api_key, timeout, agent_id=None, conversation_id=None):
            sent.append({"message": message, "agent_id": agent_id, "conversation_id": conversation_id})
            return responses[len(sent) - 1]

        rules = run_eval.knwu_categories.load_rules()
        with patch.object(run_eval, "send_message", side_effect=fake_send):
            run = run_eval.run_conversation(entry, "ag_router", "key", date(2026, 11, 9), rules, self.AGENTS)
        return run, sent

    def test_beurten_in_een_conversation_met_context(self) -> None:
        entry = {
            "id": "x",
            "type": "standaard",
            "beurten": ["Wanneer is de volgende MNC-veldrit?"],
            "vraag": "Welk verzet mag mijn zoon rijden? Hij is geboren in 2015.",
        }
        responses = [
            {"conversation_id": "c1", "outputs": [
                {"type": "agent.handoff", "previous_agent_name": "router-agent", "next_agent_name": "regio-agent"},
                {"type": "message.output", "agent_id": "ag_regio", "content": "MNC"},
            ]},
            {"conversation_id": "c1", "outputs": [
                {"type": "message.output", "agent_id": "ag_regio", "content": "6,1 meter"},
            ]},
        ]
        run, sent = self.run_with(entry, responses)
        self.assertEqual(sent[0]["agent_id"], "ag_router")
        self.assertIsNone(sent[0]["conversation_id"])
        self.assertIn("maandag 9 november 2026", sent[0]["message"])
        self.assertEqual(sent[1]["conversation_id"], "c1")
        self.assertIsNone(sent[1]["agent_id"])
        self.assertIn("wegwielrennen 2026: U12", sent[1]["message"])
        self.assertEqual(run["antwoord"], "6,1 meter")
        self.assertEqual([t["agents"] for t in run["trace"]], [["regio-agent"], ["regio-agent"]])

    def test_sticky_agent_faalt_op_verwachte_agent(self) -> None:
        entry = {
            "id": "x", "categorie": "knwu", "type": "standaard", "vraag": "Welk verzet?",
            "verwacht_antwoord": "5,90", "bron": "doc.pdf", "verwachte_agent": "knwu-agent",
            "taalniveau": "B2",
        }
        antwoord = "5,90 meter\n\nBron: doc.pdf"
        sticky = run_eval.check_entry(entry, antwoord, [{"vraag": "Welk verzet?", "agents": ["regio-agent"]}])
        goed = run_eval.check_entry(entry, antwoord, [{"vraag": "Welk verzet?", "agents": ["knwu-agent"]}])
        self.assertFalse(sticky["ok"])
        self.assertFalse(sticky["agent_ok"])
        self.assertTrue(goed["ok"])

    def test_error_stopt_de_conversation(self) -> None:
        import requests
        from datetime import date
        from unittest.mock import patch

        entry = {"id": "x", "type": "standaard", "beurten": ["a"], "vraag": "b"}
        with patch.object(run_eval, "send_message", side_effect=requests.ConnectionError("weg")):
            run = run_eval.run_conversation(
                entry, "ag_router", "key", date(2026, 11, 9), run_eval.knwu_categories.load_rules(), {}
            )
        self.assertEqual(run["antwoord"], "")
        self.assertIn("ConnectionError", run["error"])
        self.assertEqual(run["trace"], [])

    def test_fout_in_vervolgbeurt_herstart_de_hele_conversation(self) -> None:
        import requests

        entry = {"id": "x", "type": "standaard", "beurten": ["a"], "vraag": "b"}
        ok = {"conversation_id": "c1", "outputs": [{"type": "message.output", "agent_id": "ag_knwu", "content": "ok"}]}
        ok2 = dict(ok, conversation_id="c2")
        responses = [ok, requests.ReadTimeout("traag"), ok2, ok2]

        def respond_or_raise(index: int) -> dict:
            if isinstance(responses[index], Exception):
                raise responses[index]
            return responses[index]

        from datetime import date
        from unittest.mock import patch

        sent = []

        def fake_send(message, api_key, timeout, agent_id=None, conversation_id=None):
            sent.append({"agent_id": agent_id, "conversation_id": conversation_id})
            return respond_or_raise(len(sent) - 1)

        with patch.object(run_eval, "send_message", side_effect=fake_send):
            run = run_eval.run_conversation(
                entry, "ag_router", "key", date(2026, 11, 9), run_eval.knwu_categories.load_rules(), self.AGENTS
            )
        # beurt 2 wordt niet opnieuw in c1 gepost; de conversation start opnieuw
        self.assertEqual(
            sent,
            [
                {"agent_id": "ag_router", "conversation_id": None},
                {"agent_id": None, "conversation_id": "c1"},
                {"agent_id": "ag_router", "conversation_id": None},
                {"agent_id": None, "conversation_id": "c2"},
            ],
        )
        self.assertEqual(run["error"], "")
        self.assertEqual(run["antwoord"], "ok")

    def test_agent_names_from_env(self) -> None:
        import os
        from unittest.mock import patch

        env = {"MISTRAL_AGENT_ID": "ag_r", "MISTRAL_AGENT_ID_KNWU": "ag_k", "MISTRAL_AGENT_ID_REGIO": ""}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(run_eval.agent_names_from_env(), {"ag_r": "router-agent", "ag_k": "knwu-agent"})


class EvalsetTests(unittest.TestCase):
    def test_regio_nationale_knwu_vragen_hebben_knwu_bron(self) -> None:
        # eval run 5: regio-nk-kwalificatie en regio-juiste-knwu-regio werden
        # uit de Regio-library beantwoord (bron MNC-...); nationale
        # KNWU-regelgeving moet een KNWU-bron als expected bron hebben.
        entries = {e["id"]: e for e in run_eval.load_evalset(run_eval.EVAL_DIR / "evalset.yaml")}
        self.assertIn("Nationale_Besluiten", entries["regio-nk-kwalificatie"]["bron"])
        self.assertIn("knwu.nl", entries["regio-juiste-knwu-regio"]["bron"])


class NormalizeTests(unittest.TestCase):
    def test_phone_number_dash_space_parens(self) -> None:
        self.assertEqual(run_eval.normalize("085-070 19 00"), run_eval.normalize("+31 (0)85 070 1900")[:0] or run_eval.normalize("085-070 19 00"))
        self.assertIn(run_eval.normalize("085-070 19 00"), run_eval.normalize("+31 (0)85 070 1900"))

    def test_decimal_comma_and_article(self) -> None:
        self.assertEqual(run_eval.normalize("6.70 meter"), "6,70meter")
        self.assertEqual(run_eval.normalize("artikel 20.1.007"), run_eval.normalize("Artikel 20.1.007"))


class BronMatchTests(unittest.TestCase):
    def test_exact_filename_in_line(self) -> None:
        self.assertTrue(
            run_eval.bron_match(
                "TITEL_20-Jeugdwielrennen_20260921.pdf",
                "TITEL_20-Jeugdwielrennen_20260921.pdf, versie 2026-09-21",
            )
        )

    def test_url_with_path(self) -> None:
        self.assertTrue(
            run_eval.bron_match(
                "kenniscentrum.knwu.nl/knwu-licenties",
                "Bron: https://kenniscentrum.knwu.nl/knwu-licenties, geraadpleegd op 2026-11-04",
            )
        )

    def test_short_line_matches_longer_expected(self) -> None:
        self.assertTrue(run_eval.bron_match("wtcwoerden.nl?page=674", "wtcwoerden.nl"))

    def test_unrelated_does_not_match(self) -> None:
        self.assertFalse(run_eval.bron_match("knwumidden.nl/competities", "wtcwoerden.nl?page=607"))
        self.assertFalse(run_eval.bron_match("", "iets"))

    def test_sessie_parameter_en_index_php_tellen_niet_mee(self) -> None:
        line = "https://www.wtcwoerden.nl/index.php?page=674&sid=1, geraadpleegd op 2026-11-05."
        self.assertTrue(run_eval.bron_match("wtcwoerden.nl?page=674", line))

    def test_andere_pagina_matcht_niet(self) -> None:
        line = "https://www.wtcwoerden.nl/index.php?page=607&sid=1"
        self.assertFalse(run_eval.bron_match("wtcwoerden.nl?page=674", line))


class ResultTraceTests(unittest.TestCase):
    def test_result_bevat_verwachting_en_antwoord(self) -> None:
        # run_eval.main() slaat per entry vraag + verwacht_antwoord/verwachte_bron
        # + het echte antwoord op in last_run.json (visuele trace voor review).
        entry = {
            "id": "x",
            "categorie": "knwu",
            "type": "standaard",
            "vraag": "V?",
            "verwacht_antwoord": "a; b",
            "bron": "doc.pdf",
            "versiedatum": "2026-09-21",
            "doorhaal_waarde": "oud",
        }
        result = run_eval.check_entry(entry, "antwoord\n\nBron: doc.pdf, versie 2026-09-21")
        for key in ("vraag", "verwacht_antwoord", "verwachte_bron", "versiedatum", "doorhaal_waarde", "antwoord"):
            self.assertIn(key, result)

    def test_lang_antwoord_wordt_volledig_bewaard(self) -> None:
        lang = "x" * 3000 + "\n\nBron: doc.pdf"
        result = run_eval.check_entry(entry("x-y", "x", "doc.pdf"), lang)
        self.assertEqual(result["antwoord"], lang)


import json

# Echte antwoorden uit eval run 3, per vraag handmatig beoordeeld (#28).
RUN3 = json.loads(
    (Path(__file__).parent / "fixtures" / "eval_run3_antwoorden.json").read_text(encoding="utf-8")
)["antwoorden"]


def entry(
    id: str,
    verwacht: str,
    bron: str,
    type: str = "standaard",
    doorhaal: str = "",
    taalniveau: str = "B2",
) -> dict:
    # default B2: de helper modelleert een 'uitgebreid'-entry (met bron-check)
    return {
        "id": id,
        "categorie": id.split("-")[0],
        "type": type,
        "vraag": "?",
        "verwacht_antwoord": verwacht,
        "bron": bron,
        "doorhaal_waarde": doorhaal,
        "taalniveau": taalniveau,
    }


class CheckEntryRun3Tests(unittest.TestCase):
    """Fixtures: gecorrigeerde evalset-entry + echt run-3-antwoord + reviewoordeel."""

    def assertOk(self, e: dict) -> None:
        result = run_eval.check_entry(e, RUN3[e["id"]])
        self.assertTrue(result["ok"], result)

    def test_tijd_met_punt_matcht_tijd_met_dubbele_punt(self) -> None:
        self.assertOk(
            entry(
                "regio-mnc-veldrijden-starttijden",
                "2026-2027; 11:05; 11:30",
                "knwumidden.nl/competities",
            )
        )


# Oordeel per vraag uit de handmatige review van run 3 (#28): True = het
# antwoord is inhoudelijk goed mét juiste bron. De entries zelf komen uit
# eval/evalset.yaml, zodat evalset en test niet uit elkaar lopen; bij het
# verwijderen van een entry uit de evalset (review 2026-11-13) ook hier het id schrappen.
RUN3_OORDEEL = {
    # false negatives van de oude matcher/evalset
    "club-zmc-wanneer": True,
    "knwu-licentie-pakketten": True,
    "knwu-verzekering-dekking": True,
    "knwu-inschrijfgeld-jeugd": True,
    "knwu-nk-dispensatie-u10": True,
    "knwu-actuele-versie-titel20": True,
    # regel gewijzigd 2026-11-12: antwoorden mogen geen datums in het verleden
    # bevatten; het run-3-antwoord (met 29 maart t/m 27 september) faalt nu dus
    "regio-hvh-kalender-2026": False,
    "regio-juiste-knwu-regio": True,
    "regio-techniekwedstrijden-2026": True,
    # true positives
    "knwu-verzet-u15": True,
    "knwu-verzet-u17": True,
    # true negatives: moeten blijven falen
    "knwu-contact": False,  # inhoud goed, maar bron verkeerd toegeschreven
    "club-contributie-jeugd-2026": False,
    "club-vertrouwenspersoon": False,
    "club-gedragscode": False,
    "regio-nk-kwalificatie": False,
}


class Run3ReviewTests(unittest.TestCase):
    def test_evalset_oordeel_matcht_handmatige_review(self) -> None:
        evalset = run_eval.load_evalset(Path(run_eval.EVAL_DIR) / "evalset.yaml")
        by_id = {e["id"]: e for e in evalset}
        # alle gereviewde run-3-vragen moeten nog in de evalset zitten;
        # nieuwe entries zonder run-3-antwoord (#31) mogen er gewoon bij
        self.assertTrue(set(RUN3_OORDEEL) <= set(by_id))
        for eid, oordeel in RUN3_OORDEEL.items():
            with self.subTest(id=eid):
                # run-3-antwoorden kwamen uit de agent-flow (vóór #91); de
                # route-check (#92) telt daarom niet mee voor deze historische run
                result = run_eval.check_entry(
                    by_id[eid], RUN3[eid], route=by_id[eid].get("verwacht_route", "")
                )
                self.assertEqual(result["ok"], oordeel, result)


class KernfeitGrenzenTests(unittest.TestCase):
    def missing(self, verwacht: str, antwoord: str) -> list:
        return run_eval.check_entry(entry("x-y", verwacht, "doc.pdf"), antwoord + "\n\nBron: doc.pdf")[
            "missende_kernfeiten"
        ]

    def test_getal_matcht_niet_binnen_een_groter_getal(self) -> None:
        self.assertEqual(self.missing("5", "Er zijn 15 wedstrijden."), ["5"])

    def test_kort_woord_matcht_niet_binnen_een_langer_woord(self) -> None:
        self.assertEqual(self.missing("ja", "Dit jaar niet."), ["ja"])

    def test_bedrag_met_nullen_matcht_bedrag_met_streepje(self) -> None:
        self.assertEqual(self.missing("10,00", "maximaal € 10,- extra"), [])

    def test_tijd_met_voorloopnul_matcht_tijd_zonder(self) -> None:
        self.assertEqual(self.missing("08:30", "tussen 8.30 en 12.00 uur"), [])

    def test_art_matcht_artikel(self) -> None:
        # review 2026-11-12: modellen schrijven "art. 20.1.007" waar de evalset
        # "artikel 20.1.007" verwacht — inhoudelijk hetzelfde, moet matchen
        self.assertEqual(self.missing("artikel 20.1.007", "max 6,70 meter (art. 20.1.007)"), [])


class VerwachtMarkerTests(unittest.TestCase):
    """Optioneel veld `verwacht_marker` (#47): de [BRONCONFLICT]-markerregel moet
    in de ruwe agent-output staan (de eval-runner ziet de ruwe output; de proxy
    strip't de marker pas voor de gebruiker)."""

    def marker_entry(self) -> dict:
        e = entry("x-y", "U17; nieuweling", "TITEL_20.pdf")
        e["verwacht_marker"] = "[BRONCONFLICT]"
        return e

    def test_marker_aanwezig_is_ok(self) -> None:
        antwoord = (
            "U17 Nieuweling volgens Titel 20.\n"
            "[BRONCONFLICT] TITEL_20 art. 20.0.004: U17 Nieuweling | https://kenniscentrum.knwu.nl/x: U16 en U17\n\n"
            "Bron: TITEL_20.pdf"
        )
        result = run_eval.check_entry(self.marker_entry(), antwoord)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["marker_gevonden"])

    def test_marker_afwezig_faalt(self) -> None:
        result = run_eval.check_entry(self.marker_entry(), "U17 Nieuweling.\n\nBron: TITEL_20.pdf")
        self.assertFalse(result["ok"])
        self.assertFalse(result["marker_gevonden"])

    def test_zonder_verwacht_marker_geen_marker_check(self) -> None:
        result = run_eval.check_entry(entry("x-y", "U17", "TITEL_20.pdf"), "U17.\n\nBron: TITEL_20.pdf")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["verwacht_marker"], "")

    def test_evalset_bevat_bronconflict_entry_met_marker(self) -> None:
        evalset = run_eval.load_evalset(Path(run_eval.EVAL_DIR) / "evalset.yaml")
        e = {x["id"]: x for x in evalset}["knwu-bronconflict-u17-nieuweling"]
        self.assertEqual(e["verwacht_marker"], "[BRONCONFLICT]")
        self.assertIn("U17", e["verwacht_antwoord"])


class EnvTests(unittest.TestCase):
    def test_env_bestand_wint_van_verouderde_shellvariabele(self) -> None:
        import os
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("MISTRAL_API_KEY=\n", encoding="utf-8")
            with (
                patch.object(run_eval, "ENV_PATH", env),
                patch.dict(os.environ, {"MISTRAL_API_KEY": "verouderd-uit-de-shell"}),
                self.assertRaisesRegex(RuntimeError, "MISTRAL_API_KEY ontbreekt"),
            ):
                run_eval.main()


class VerhelderingTests(unittest.TestCase):
    """Type `verheldering`: vage vraag, bot stelt een wedervraag; geen bron-check."""

    def verheldering_entry(self, verwacht: str) -> dict:
        return {
            "id": "knwu-verheldering-x",
            "categorie": "knwu",
            "type": "verheldering",
            "vraag": "In welke categorie rijdt mijn kind mee?",
            "verwacht_antwoord": verwacht,
        }

    def test_wedervraag_zonder_bronregel_is_ok(self) -> None:
        antwoord = (
            "Om te bepalen in welke leeftijdscategorie je kind rijdt, heb ik het "
            "geboortejaar en het geslacht nodig. In welk jaar is je kind geboren, "
            "en is het een jongen of een meisje?"
        )
        result = run_eval.check_entry(
            self.verheldering_entry("geboortejaar; geslacht"), antwoord
        )
        self.assertTrue(result["bron_ok"])  # bron-check vervalt
        self.assertTrue(result["ok"], result)

    def test_ontbrekend_kernfeit_in_wedervraag_faalt(self) -> None:
        result = run_eval.check_entry(
            self.verheldering_entry("geboortejaar; geslacht"),
            "Daar heb ik meer informatie voor nodig.",
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["missende_kernfeiten"], ["geboortejaar", "geslacht"])

    def test_standaard_type_zonder_bronmatch_faalt_nog_steeds(self) -> None:
        # regressieguard: bij taalniveau B2 slaat alleen verheldering de bron-check over
        result = run_eval.check_entry(entry("x-y", "ja", "doc.pdf"), "Ja, dat klopt.")
        self.assertFalse(result["bron_ok"])
        self.assertFalse(result["ok"])


class TaalniveauTests(unittest.TestCase):
    """Taalniveau per entry (issue #52): B1 = standaard, geen Bron-regel; B2 = bron verplicht."""

    def b1_entry(self, verwacht: str = "U12") -> dict:
        return {
            "id": "knwu-b1-x",
            "categorie": "knwu",
            "type": "standaard",
            "taalniveau": "B1",
            "vraag": "?",
            "verwacht_antwoord": verwacht,
            "bron": "doc.pdf",
            "versiedatum": "2026",
        }

    def test_b1_zonder_bronregel_is_ok(self) -> None:
        result = run_eval.check_entry(self.b1_entry(), "Hij rijdt in U12.")
        self.assertTrue(result["bron_ok"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["taalniveau"], "B1")

    def test_b1_met_bronregel_faalt(self) -> None:
        result = run_eval.check_entry(self.b1_entry(), "Hij rijdt in U12.\n\nBron: doc.pdf")
        self.assertFalse(result["bron_ok"])
        self.assertFalse(result["ok"])

    def test_b2_zonder_bronregel_faalt(self) -> None:
        e = self.b1_entry()
        e["taalniveau"] = "B2"
        result = run_eval.check_entry(e, "Hij rijdt in U12.")
        self.assertFalse(result["bron_ok"])
        self.assertFalse(result["ok"])

    def test_b2_met_bronregel_is_ok(self) -> None:
        e = self.b1_entry()
        e["taalniveau"] = "B2"
        result = run_eval.check_entry(e, "Hij rijdt in U12.\n\nBron: doc.pdf, versie 2026")
        self.assertTrue(result["ok"], result)

    def test_runner_injecteert_taalniveau_in_context(self) -> None:
        from datetime import date
        from unittest.mock import patch

        sent = []

        def fake_send(message, api_key, timeout, agent_id=None, conversation_id=None):
            sent.append(message)
            return {"conversation_id": "c1", "outputs": [{"type": "message.output", "content": "ok"}]}

        rules = run_eval.knwu_categories.load_rules()
        b2 = {"id": "x", "categorie": "knwu", "type": "standaard", "taalniveau": "B2", "vraag": "b?"}
        b1_default = {"id": "y", "categorie": "knwu", "type": "standaard", "vraag": "b?"}
        with patch.object(run_eval, "send_message", side_effect=fake_send):
            run_eval.run_conversation(b2, "ag", "key", date(2026, 11, 9), rules, {})
            run_eval.run_conversation(b1_default, "ag", "key", date(2026, 11, 9), rules, {})
        self.assertIn("vastgesteld taalniveau: B2", sent[0])
        self.assertIn("vastgesteld taalniveau: B1", sent[1])  # default = B1


class NietInAntwoordTests(unittest.TestCase):
    """Optioneel veld `niet_in_antwoord`: woorden die het antwoord fout maken."""

    def licentie_entry(self) -> dict:
        return {
            "id": "knwu-verheldering-licentie-via-router",
            "categorie": "knwu",
            "type": "verheldering",
            "via": "router",
            "vraag": "Welke licentie moet ik aanvragen voor mijn zoon?",
            "verwacht_antwoord": "geboortejaar",
            "niet_in_antwoord": "MNC; Hans van den Hengel; WTC Woerden; discipline; geslacht",
        }

    def test_routeringsvraag_met_verzonnen_opties_faalt(self) -> None:
        # het echte foute antwoord van 2026-11-06 (router vroeg naar het licentietype)
        antwoord = (
            "Om je vraag goed te kunnen beantwoorden, wil ik eerst weten over welk "
            "type licentie het gaat. 1. KNWU-licentie 2. Regio-specifieke licentie "
            "(bijvoorbeeld via MNC, Hans van den Hengel of regio Midden). "
            "3. Clubspecifieke licentie (binnen WTC Woerden). Wat is het geboortejaar?"
        )
        result = run_eval.check_entry(self.licentie_entry(), antwoord)
        self.assertFalse(result["ok"])
        self.assertEqual(
            result["verboden_gevonden"], ["MNC", "Hans van den Hengel", "WTC Woerden"]
        )

    def test_vier_vragen_tegelijk_faalt(self) -> None:
        antwoord = (
            "Ik heb nodig: 1. Geboortejaar 2. Discipline: wegwielrennen of veldrijden? "
            "3. Doel van de licentie 4. Soort wedstrijden"
        )
        result = run_eval.check_entry(self.licentie_entry(), antwoord)
        self.assertFalse(result["ok"])
        self.assertEqual(result["verboden_gevonden"], ["discipline"])

    def test_alleen_geboortejaar_vragen_is_ok(self) -> None:
        antwoord = "In welk geboortejaar is je zoon geboren? Bijvoorbeeld 2014, 2017 of 2020."
        result = run_eval.check_entry(self.licentie_entry(), antwoord)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["verboden_gevonden"], [])

    def test_entry_zonder_veld_ongewijzigd(self) -> None:
        result = run_eval.check_entry(entry("x-y", "ja", "doc.pdf"), "Ja, via MNC.\n\nBron: doc.pdf")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["verboden_gevonden"], [])


class AgentKeuzeTests(unittest.TestCase):
    ENV = {
        "MISTRAL_AGENT_ID": "ag_router",
        "MISTRAL_AGENT_ID_KNWU": "ag_knwu",
    }

    def kies(self, e: dict) -> str:
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, self.ENV, clear=True):
            return run_eval.agent_id_for(e)

    def test_via_router_gaat_naar_de_router(self) -> None:
        self.assertEqual(self.kies({"categorie": "knwu", "via": "router"}), "ag_router")

    def test_zonder_via_gaat_naar_de_categorie_agent(self) -> None:
        self.assertEqual(self.kies({"categorie": "knwu"}), "ag_knwu")

    def test_categorie_zonder_eigen_agent_valt_terug_op_router(self) -> None:
        self.assertEqual(self.kies({"categorie": "club"}), "ag_router")

    def test_via_router_zonder_router_id_geeft_fout(self) -> None:
        import os
        from unittest.mock import patch

        with (
            patch.dict(os.environ, {"MISTRAL_AGENT_ID_KNWU": "ag_knwu"}, clear=True),
            self.assertRaisesRegex(RuntimeError, "MISTRAL_AGENT_ID"),
        ):
            run_eval.agent_id_for({"id": "x", "categorie": "knwu", "via": "router"})

    def test_evalset_bevat_licentievraag_via_router(self) -> None:
        evalset = run_eval.load_evalset(Path(run_eval.EVAL_DIR) / "evalset.yaml")
        e = {x["id"]: x for x in evalset}["knwu-verheldering-licentie-via-router"]
        self.assertEqual(e["via"], "router")
        self.assertEqual(e["categorie"], "knwu")
        self.assertEqual(e["verwacht_antwoord"], "geboortejaar")
        self.assertEqual(
            e["niet_in_antwoord"], "MNC; Hans van den Hengel; WTC Woerden; discipline; geslacht"
        )


class EvalsetSchemaTests(unittest.TestCase):
    BEKENDE_TYPES = {"standaard", "websearch", "strikethrough", "verheldering"}
    BEKENDE_AGENTS = {"router-agent", "knwu-agent", "regio-agent", "club-agent"}

    def test_alle_entries_heillopmen_bekend_type_en_verplichte_velden(self) -> None:
        evalset = run_eval.load_evalset(Path(run_eval.EVAL_DIR) / "evalset.yaml")
        ids = set()
        for e in evalset:
            with self.subTest(id=e["id"]):
                self.assertIn(e["type"], self.BEKENDE_TYPES)
                self.assertNotIn(e["id"], ids)  # id uniek
                ids.add(e["id"])
                self.assertTrue(e["vraag"])
                self.assertTrue(e["verwacht_antwoord"])
                if e["type"] != "verheldering":
                    self.assertTrue(e.get("bron"))
                    self.assertTrue(e.get("versiedatum"))
                self.assertIn(e.get("taalniveau", "B1"), {"B1", "B2"})
                if e["type"] == "strikethrough":
                    self.assertTrue(e.get("doorhaal_waarde"))
                self.assertIn(e.get("via", "router"), {"router"})
                beurten = e.get("beurten", [])
                self.assertIsInstance(beurten, list)
                self.assertTrue(all(isinstance(b, str) and b for b in beurten))
                self.assertIn(e.get("verwachte_agent", "knwu-agent"), self.BEKENDE_AGENTS)


class VerzetFunctionCallTests(unittest.TestCase):
    """#152: de runner beantwoordt function calls van de verzet-agent zoals de app."""

    ARGS = (
        '{"birth_year": 2011, "gender": "jongens", "chainring": 42, "smallest_sprocket": 14, '
        '"largest_sprocket": 28, "tire_width_mm": 28, "rim_diameter_mm": 622}'
    )

    def play(self, entry: dict, responses: list[dict], offer=None) -> tuple[dict, list[dict]]:
        sent = []

        def fake_send(message, api_key, timeout, agent_id=None, conversation_id=None):
            sent.append({"message": message, "agent_id": agent_id, "conversation_id": conversation_id})
            return responses[len(sent) - 1]

        rules = run_eval.knwu_categories.load_rules()
        with patch.object(run_eval, "send_message", side_effect=fake_send):
            run = run_eval.run_conversation(
                entry, "ag_verzet", "key", PEILDATUM, rules, {"ag_verzet": "verzet-agent"}, offer=offer
            )
        return run, sent

    def call_then_answer(self) -> list[dict]:
        return [
            {"conversation_id": "c1", "outputs": [
                {"type": "function.call", "tool_call_id": "t1", "name": "bereken_verzet", "arguments": self.ARGS},
            ]},
            {"conversation_id": "c1", "outputs": [
                {"type": "message.output", "agent_id": "ag_verzet", "content": "Je zwaarste verzet is 6,39 m."},
            ]},
        ]

    def test_function_call_wordt_uitgevoerd_en_beantwoord(self) -> None:
        entry = {"id": "x", "type": "standaard", "vraag": "Mag mijn fiets? 42, 14-28, 28-622"}
        run, sent = self.play(entry, self.call_then_answer())
        self.assertEqual(run["error"], "")
        self.assertEqual(run["antwoord"], "Je zwaarste verzet is 6,39 m.")
        self.assertEqual(sent[1]["conversation_id"], "c1")
        result = sent[1]["message"][0]
        self.assertEqual((result["type"], result["tool_call_id"]), ("function.result", "t1"))
        self.assertIn("6.39", result["result"])
        self.assertEqual(run["trace"][0]["function_calls"], ["bereken_verzet"])
        self.assertEqual(run["trace"][0]["agents"], ["verzet-agent"])

    def test_zonder_function_call_is_de_lijst_leeg(self) -> None:
        entry = {"id": "x", "type": "standaard", "vraag": "Mag mijn fiets?"}
        answer = {"conversation_id": "c1", "outputs": [
            {"type": "message.output", "agent_id": "ag_verzet", "content": "Wat is je ETRTO-maat?"}
        ]}
        run, _ = self.play(entry, [answer])
        self.assertEqual(run["trace"][0]["function_calls"], [])

    def test_agent_die_blijft_aanroepen_geeft_een_error(self) -> None:
        entry = {"id": "x", "type": "standaard", "vraag": "Mag mijn fiets?"}
        call = {"conversation_id": "c1", "outputs": [
            {"type": "function.call", "tool_call_id": "t1", "name": "bereken_verzet", "arguments": self.ARGS},
        ]}
        run, _ = self.play(entry, [call] * 20)
        self.assertIn("functieaanroepen", run["error"])

    def test_aangenomen_aanbod_start_een_verse_conversation_met_bypass_context(self) -> None:
        rules = run_eval.knwu_categories.load_rules()
        state = run_eval.replay_beurt(
            "Wat is het maximaal toegestane verzet voor een jongen geboren in 2011 bij wegwielrennen?",
            run_eval.lookups.NoLookupState(), "key", PEILDATUM, rules, is_first_turn=True,
        )
        offer = run_eval.lookups.accepted_verzet_offer("Ja, graag", state)
        entry = {"id": "x", "type": "standaard", "beurten": ["eerdere vraag"], "vraag": "Ja, graag"}
        answer = {"conversation_id": "c1", "outputs": [
            {"type": "message.output", "agent_id": "ag_verzet", "content": "Welk kettingblad?"}
        ]}
        run, sent = self.play(entry, [answer], offer=offer)
        self.assertEqual(len(sent), 1)  # de bypass-beurt gaat niet naar de agent
        self.assertEqual(sent[0]["agent_id"], "ag_verzet")
        self.assertIn("geboortejaar 2011", sent[0]["message"])
        self.assertIn("7,68", sent[0]["message"])
        self.assertEqual(run["antwoord"], "Welk kettingblad?")


class ToolAanroepCheckTests(unittest.TestCase):
    ENTRY = {
        "id": "x", "categorie": "knwu", "type": "standaard", "vraag": "Vraag?",
        "verwacht_antwoord": "ETRTO",
    }

    def check(self, expected: bool, calls: list[str]) -> dict:
        entry = {**self.ENTRY, "verwacht_tool_aanroep": expected}
        trace = [{"vraag": "Vraag?", "agents": [], "function_calls": calls}]
        return run_eval.check_entry(entry, "Wat is je ETRTO-maat?", trace)

    def test_verwachte_aanroep_ontbreekt_faalt(self) -> None:
        self.assertFalse(self.check(True, [])["ok"])
        self.assertTrue(self.check(True, ["bereken_verzet"])["ok"])

    def test_onverwachte_aanroep_faalt(self) -> None:
        result = self.check(False, ["bereken_verzet"])
        self.assertFalse(result["ok"])
        self.assertFalse(result["tool_ok"])
        self.assertTrue(self.check(False, [])["ok"])

    def test_zonder_verwachting_geen_check(self) -> None:
        trace = [{"vraag": "Vraag?", "agents": [], "function_calls": ["bereken_verzet"]}]
        self.assertTrue(run_eval.check_entry(self.ENTRY, "ETRTO", trace)["ok"])


class VerzetPlanTests(unittest.TestCase):
    """#152: plan_entry spiegelt de route na het verzetaanbod van de bypass."""

    ENV = {"MISTRAL_AGENT_ID": "ag_router", "MISTRAL_AGENT_ID_VERZET": "ag_verzet"}

    def test_ja_na_het_aanbod_gaat_zonder_intake_naar_de_verzet_agent(self) -> None:
        entry = {
            "id": "x",
            "beurten": ["Wat is het maximaal toegestane verzet voor een jongen geboren in 2011 bij wegwielrennen?"],
            "vraag": "Ja, graag",
        }
        rules = run_eval.knwu_categories.load_rules()
        with patch.dict(os.environ, self.ENV), patch.object(run_eval.intake, "classify_message") as classify:
            plan = run_eval.plan_entry(entry, "key", PEILDATUM, rules)
        classify.assert_not_called()
        self.assertEqual(plan["route"], "direct-verzet")
        self.assertEqual(plan["route_reden"], "verzet_offer_accepted")
        self.assertEqual(plan["agent_id"], "ag_verzet")
        self.assertIsNotNone(plan["offer"])

    def test_zonder_verzet_agent_faalt_de_verzetroute_hard(self) -> None:
        entry = {
            "id": "x",
            "beurten": ["Wat is het maximaal toegestane verzet voor een jongen geboren in 2011 bij wegwielrennen?"],
            "vraag": "Ja, graag",
        }
        rules = run_eval.knwu_categories.load_rules()
        with patch.dict(os.environ, {"MISTRAL_AGENT_ID": "ag_router"}, clear=True), self.assertRaisesRegex(
            RuntimeError, "MISTRAL_AGENT_ID_VERZET"
        ):
            run_eval.plan_entry(entry, "key", PEILDATUM, rules)

    def test_vraag_om_verzetadvies_gaat_zonder_intake_naar_de_verzet_agent(self) -> None:
        entry = {"id": "x", "vraag": "ik wil mijn verzet aanpassen"}
        rules = run_eval.knwu_categories.load_rules()
        with patch.dict(os.environ, self.ENV), patch.object(run_eval.intake, "classify_message") as classify:
            plan = run_eval.plan_entry(entry, "key", PEILDATUM, rules)
        classify.assert_not_called()
        self.assertEqual(plan["route"], "direct-verzet")
        self.assertEqual(plan["route_reden"], "verzetadvies_vraag")
        self.assertEqual(plan["agent_id"], "ag_verzet")
        self.assertIsNone(plan["offer"])


class VerzetEvalsetTests(unittest.TestCase):
    """#152: de getallen in de verzet-entries komen uit de rekenmodule (ADR-0010)."""

    # id -> (kettingbladen, cassette, ETRTO) van een jongen geboren in 2011 (U17 Nieuweling, 7,68 m)
    SETUPS = {
        "verzet-voldoet": dict(chainring=42, small_chainring=None, smallest_sprocket=12, largest_sprocket=28),
        "verzet-te-zwaar-kransje": dict(chainring=52, small_chainring=None, smallest_sprocket=12, largest_sprocket=28),
        "verzet-te-zwaar-blad": dict(chainring=54, small_chainring=36, smallest_sprocket=14, largest_sprocket=28),
        "verzet-reguliere-cassette": dict(chainring=52, small_chainring=36, smallest_sprocket=14, largest_sprocket=28),
        "verzet-te-licht": dict(chainring=36, small_chainring=None, smallest_sprocket=13, largest_sprocket=28),
    }

    def advice(self, setup: dict):
        args = dict(birth_year=2011, gender="jongens", year=2026, tire_width_mm=28, rim_diameter_mm=622)
        args.update(setup)
        return run_eval.verzet_advies.advise(**args, rules=run_eval.knwu_categories.load_rules())

    def numbers(self, advice) -> set[str]:
        values = [advice.limit_m, advice.current.heaviest_gear_m]
        values += [a.result.heaviest_gear_m for a in advice.advices]
        return {f"{v:.2f}".replace(".", ",") for v in values}

    def test_verwachte_getallen_komen_uit_de_rekenmodule(self) -> None:
        entries = {e["id"]: e for e in run_eval.load_evalset(EVALSET)}
        for entry_id, setup in self.SETUPS.items():
            with self.subTest(entry_id):
                entry = entries[entry_id]
                expected = {t for t in run_eval.tokens(entry["verwacht_antwoord"]) if "," in t}
                self.assertTrue(expected)
                self.assertLessEqual(
                    {run_eval._canoniek(n) for n in expected}, {run_eval._canoniek(n) for n in self.numbers(self.advice(setup))}
                )

    def test_ruim_te_licht_is_te_licht_en_voldoet_niet(self) -> None:
        self.assertTrue(self.advice(self.SETUPS["verzet-te-licht"]).too_light)
        self.assertFalse(self.advice(self.SETUPS["verzet-voldoet"]).too_light)
        self.assertTrue(self.advice(self.SETUPS["verzet-voldoet"]).current.within_limit)

    def test_reguliere_cassette_geeft_1x_met_12t(self) -> None:
        regular = self.advice(self.SETUPS["verzet-reguliere-cassette"]).advice(3)
        assert regular is not None
        self.assertEqual((regular.result.setup.chainring, regular.result.setup.smallest_sprocket), (42, 12))

    def test_alle_verzet_entries_routeren_naar_de_verzet_agent_of_bypass(self) -> None:
        entries = [e for e in run_eval.load_evalset(EVALSET) if e["id"].startswith("verzet-")]
        routes = {e["id"]: e.get("verwacht_route") for e in entries}
        self.assertEqual(sum(r == "bypass" for r in routes.values()), 1)
        self.assertGreaterEqual(sum(r == "direct-verzet" for r in routes.values()), 7)
        self.assertTrue(all(routes.values()))

if __name__ == "__main__":
    unittest.main()


class PlanEntryTests(unittest.TestCase):
    """#92: plan_entry spiegelt de route-beslissing van de app (bypass/direct/router)."""

    def setUp(self) -> None:
        from datetime import date

        self.rules = run_eval.knwu_categories.load_rules()
        self.today = date(2026, 11, 9)

    def test_bypass_bij_pure_lookup_zonder_intake_call(self) -> None:
        entry = {
            "id": "x",
            "vraag": "In welke leeftijdscategorie rijdt een jongen geboren in 2015 bij wegwielrennen?",
        }
        with patch.object(run_eval.intake, "classify_message") as classify:
            plan = run_eval.plan_entry(entry, "key", self.today, self.rules)
        classify.assert_not_called()  # bypass gebeurt vóór de intake, 0 LLM-calls
        self.assertEqual(plan["route"], "bypass")
        self.assertEqual(plan["route_reden"], "regex_lookup")
        self.assertIsNone(plan["agent_id"])
        self.assertIn("**Geboortejaar 2015**", run_eval.lookups.render_answer(plan["lookup"], "B1"))

    def test_via_router_forceert_router(self) -> None:
        entry = {"id": "x", "vraag": "Hoe zit het met die wedstrijd?", "via": "router"}
        with patch.dict(os.environ, {"MISTRAL_AGENT_ID": "ag_router"}):
            plan = run_eval.plan_entry(entry, "key", self.today, self.rules)
        self.assertEqual(plan["route"], "router")
        self.assertEqual(plan["agent_id"], "ag_router")

    def test_beurten_replay_in_order_through_the_lookup_state(self) -> None:
        entry = {"vraag": "weg", "beurten": ["wat is categorie 1", "wlk verzet voor u8"]}
        with patch.object(run_eval.intake, "classify_message") as classify:
            plan = run_eval.plan_entry(entry, "key", self.today, self.rules)
        classify.assert_not_called()
        self.assertEqual(plan["route"], "bypass")
        answer = run_eval.lookups.render_answer(plan["lookup"], "B2")
        self.assertIn("5,50 meter", answer)
        self.assertNotIn("Veldrijden", answer)
        self.assertNotIn("Oude cat.", answer)

    def test_rejected_beurt_ends_reuse_of_the_earlier_profile(self) -> None:
        entry = {"vraag": "alleen meisjes", "beurten": ["Welke categorie voor JO11?", "Waarom?"]}
        with patch.dict(os.environ, {"MISTRAL_AGENT_ID": "ag_router"}), patch.object(
            run_eval.intake, "classify_message", return_value=dict(run_eval.intake.FALLBACK)
        ) as classify:
            plan = run_eval.plan_entry(entry, "key", self.today, self.rules)
        classify.assert_called_once()
        self.assertEqual(plan["route"], "router")

    def test_earlier_incomplete_beurt_gets_the_intake_completion_like_the_app(self) -> None:
        entry = {"vraag": "alleen meisjes", "beurten": ["Welk verzet? 2011"]}
        intake_result = {**run_eval.intake.FALLBACK, "intentie": "lookup", "geboortejaar": 2011}
        with patch.object(
            run_eval.intake, "classify_message", return_value=intake_result
        ) as classify:
            plan = run_eval.plan_entry(entry, "key", self.today, self.rules)
        classify.assert_called_once()  # alleen voor de eerdere beurt
        self.assertEqual(plan["route"], "bypass")
        self.assertEqual(plan["route_reden"], "regex_lookup")
        answer = run_eval.lookups.render_answer(plan["lookup"], "B1")
        self.assertIn("**Geboortejaar 2011**", answer)
        self.assertNotIn("Jongens", answer)

    def test_intake_direct_to_expert_bij_hoge_confidence(self) -> None:
        entry = {"id": "x", "vraag": "Wat kost de contributie bij WTC Woerden?"}
        intake_result = {
            "intentie": "regelgeving",
            "domein": "club",
            "discipline": "onbekend",
            "geboortejaar": None,
            "leeftijd": None,
            "confidence": 0.95,
        }
        env = {"MISTRAL_AGENT_ID": "ag_router", "MISTRAL_AGENT_ID_CLUB": "ag_club"}
        with patch.dict(os.environ, env), patch.object(
            run_eval.intake, "classify_message", return_value=intake_result
        ):
            plan = run_eval.plan_entry(entry, "key", self.today, self.rules)
        self.assertEqual(plan["route"], "direct-club")
        self.assertEqual(plan["agent_id"], "ag_club")
        self.assertGreaterEqual(plan["intake_ms"], 0.0)

    def test_intake_lage_confidence_route_router(self) -> None:
        entry = {"id": "x", "vraag": "Iets vaags over een wedstrijd"}
        intake_result = {
            "intentie": "onbekend",
            "domein": "club",
            "discipline": "onbekend",
            "geboortejaar": None,
            "leeftijd": None,
            "confidence": 0.3,
        }
        env = {"MISTRAL_AGENT_ID": "ag_router", "MISTRAL_AGENT_ID_CLUB": "ag_club"}
        with patch.dict(os.environ, env), patch.object(
            run_eval.intake, "classify_message", return_value=intake_result
        ):
            plan = run_eval.plan_entry(entry, "key", self.today, self.rules)
        self.assertEqual(plan["route"], "router")
        self.assertEqual(plan["agent_id"], "ag_router")

    def test_intake_kan_onvolledige_lookup_compleet_maken(self) -> None:
        # het kale jaartal is pas met de intake een geboortejaar -> intake-bypass
        entry = {"id": "x", "vraag": "Welk verzet? 2011"}
        intake_result = {**run_eval.intake.FALLBACK, "intentie": "lookup", "geboortejaar": 2011}
        with patch.dict(os.environ, {"MISTRAL_AGENT_ID": "ag_router"}), patch.object(
            run_eval.intake, "classify_message", return_value=intake_result
        ):
            plan = run_eval.plan_entry(entry, "key", self.today, self.rules)
        self.assertEqual(plan["route"], "bypass")
        self.assertEqual(plan["route_reden"], "intake_lookup")
        self.assertIn("**Geboortejaar 2011**", run_eval.lookups.render_answer(plan["lookup"], "B1"))

    def test_intake_redt_afgewezen_invoer_niet(self) -> None:
        entry = {"id": "x", "vraag": "Welke categorie voor geboortejaar 2015 in 2025?"}
        intake_result = {
            **run_eval.intake.FALLBACK, "intentie": "lookup", "geboortejaar": 2015, "discipline": "weg",
        }
        with patch.dict(os.environ, {"MISTRAL_AGENT_ID": "ag_router"}), patch.object(
            run_eval.intake, "classify_message", return_value=intake_result
        ):
            plan = run_eval.plan_entry(entry, "key", self.today, self.rules)
        self.assertEqual(plan["route"], "router")


class RouteAssertionTests(unittest.TestCase):
    """#92: verwacht_route assert de gespiegde route in check_entry."""

    def entry(self, **kw) -> dict:
        base = {
            "id": "x",
            "categorie": "knwu",
            "type": "standaard",
            "vraag": "Vraag?",
            "verwacht_antwoord": "U12",
            "bron": "doc.pdf",
            "taalniveau": "B2",
        }
        base.update(kw)
        return base

    def test_matchende_route_is_ok(self) -> None:
        result = run_eval.check_entry(self.entry(verwacht_route="bypass"), "U12\n\nBron: doc.pdf", [], route="bypass")
        self.assertTrue(result["ok"])
        self.assertTrue(result["route_ok"])
        self.assertEqual(result["route"], "bypass")

    def test_mismatchende_route_faalt(self) -> None:
        result = run_eval.check_entry(self.entry(verwacht_route="router"), "U12\n\nBron: doc.pdf", [], route="bypass")
        self.assertFalse(result["ok"])
        self.assertFalse(result["route_ok"])

    def test_zonder_verwacht_route_geen_route_check(self) -> None:
        result = run_eval.check_entry(self.entry(), "U12\n\nBron: doc.pdf", [], route="bypass")
        self.assertTrue(result["ok"])
        self.assertTrue(result["route_ok"])

    def test_b1_bypass_heeft_geen_bronregel(self) -> None:
        entry = self.entry(taalniveau="B1")
        bypass_without_source = run_eval.check_entry(entry, "U12", [], route="bypass")
        bypass_with_source = run_eval.check_entry(
            entry, "U12\n\nBron: doc.pdf", [], route="bypass"
        )
        agent = run_eval.check_entry(entry, "U12\n\nBron: doc.pdf", [], route="router")
        self.assertTrue(bypass_without_source["bron_ok"])
        self.assertFalse(bypass_with_source["bron_ok"])
        self.assertFalse(agent["bron_ok"])


class BypassTemplateEvalsetTests(unittest.TestCase):
    """#92/#136: alle evalset-entries met verwacht_route: bypass moeten via
    dezelfde recognize/render-operaties als de app de checks halen, zonder intake."""

    def test_bypass_entries_halen_checks_met_template(self) -> None:
        entries = run_eval.load_evalset(EVALSET)
        rules = run_eval.knwu_categories.load_rules()
        bypass_entries = [e for e in entries if e.get("verwacht_route") == "bypass"]
        self.assertGreaterEqual(len(bypass_entries), 4)  # oa. de 2 baseline-lookup-vragen
        for e in bypass_entries:
            with self.subTest(e["id"]):
                with patch.object(
                    run_eval.intake, "classify_message", return_value=dict(run_eval.intake.FALLBACK)
                ):
                    plan = run_eval.plan_entry(e, "key", PEILDATUM, rules)
                self.assertEqual(plan["route"], "bypass", "geen lookup herkend")
                self.assertEqual(plan["route_reden"], "regex_lookup")
                antwoord = run_eval.lookups.render_answer(plan["lookup"], e.get("taalniveau", "B1"))
                result = run_eval.check_entry(e, antwoord, [], route="bypass")
                self.assertTrue(result["ok"], f"{e['id']}: {result}")


class PeildatumTests(unittest.TestCase):
    """Live runner en offline tests rekenen met dezelfde peildatum uit de
    evalset, zodat seizoensafhankelijke verwachtingen niet vals falen."""

    def test_live_runner_rekent_met_de_peildatum_van_de_evalset(self) -> None:
        class Stop(Exception):
            pass

        seen = []

        def capture(entry, api_key, today, rules):
            seen.append(today)
            raise Stop

        with (
            patch.object(run_eval, "load_dotenv"),
            patch.dict(os.environ, {"MISTRAL_API_KEY": "key"}),
            patch.object(run_eval, "plan_entry", side_effect=capture),
            self.assertRaises(Stop),
        ):
            run_eval.main()
        self.assertEqual(seen, [PEILDATUM])

    def test_ontbrekende_peildatum_faalt_luid(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evalset.yaml"
            path.write_text("evalset: []\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "peildatum"):
                run_eval.load_peildatum(path)
