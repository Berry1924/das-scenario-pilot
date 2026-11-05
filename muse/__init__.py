"""ScenarioPilot — Meta Muse Spark integration layer for DAAS-V2V experiments.

Thin adapters only: this package never reimplements simulator internals.
It validates scenarios, reviews them with the Meta Model API (Muse Spark 1.3,
credentials from environment variables), drives the EXISTING daas_impl world
for one baseline arm and one DAAS-V2V arm under identical conditions, and
persists evidence in the existing RunContext-compatible format.

Roles are separated (see docs/implementation/CHANGES.md):

  scenario.py      strict schema + validation (authoritative, deterministic)
  spark_adapter.py optional model-API review (advisory only, no metrics)
  adapter.py       calls the existing SimulationWorld; metrics come only from
                   WorldMetrics' existing implementations
  reporting.py     report rendering (formats computed numbers, never
                   recomputes them)
"""

__version__ = "muse 0.1.0"
