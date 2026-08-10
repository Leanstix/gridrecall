import { useEffect, useMemo, useState } from "react";
import { demoApi } from "./api";
import type { ActionType, DemoState, Incident } from "./types";

const actionLabels: Record<ActionType, string> = {
  continue_monitoring: "Continue monitoring",
  inspect_ventilation: "Inspect ventilation",
  approved_inverter_reset: "Approved inverter reset",
  inspect_connections: "Inspect connections",
  reduce_noncritical_load: "Reduce noncritical load",
  isolate_component: "Isolate component",
  dispatch_technician: "Dispatch technician",
  escalate_engineer: "Escalate to engineer",
};

const phaseLabels = {
  ready: "Awaiting incident",
  first_resolved: "Memory captured",
  memory_proven: "Memory transfer proven",
};

function App() {
  const [state, setState] = useState<DemoState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    demoApi
      .state()
      .then(setState)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  const currentIncident = state?.incidents.at(-1);
  const firstIncident = state?.incidents[0];
  const nextEndpoint = useMemo(() => {
    if (!state || state.phase === "ready") return demoApi.firstIncident;
    if (state.phase === "first_resolved") return demoApi.secondIncident;
    return demoApi.reset;
  }, [state]);

  async function advanceDemo() {
    setLoading(true);
    setError(null);
    try {
      setState(await nextEndpoint());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The demo could not continue.");
    } finally {
      setLoading(false);
    }
  }

  if (!state && loading) {
    return <div className="screen-message">Loading operational memory…</div>;
  }

  if (!state) {
    return (
      <div className="screen-message error-message">
        <strong>Dashboard could not reach the GridRecall API.</strong>
        <span>{error}</span>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div>
            <strong>GridRecall</strong>
            <small>Operational memory</small>
          </div>
        </div>
        <div className="topbar-status">
          <span className="live-dot" />
          Demo environment
        </div>
      </header>

      <aside className="sidebar">
        <div className="sidebar-label">Fleet overview</div>
        <nav>
          <button className="nav-item active">
            <Icon name="grid" /> Operations
          </button>
          <button className="nav-item">
            <Icon name="pulse" /> Incidents
            <span className="nav-count">{state.incidents.length}</span>
          </button>
          <button className="nav-item">
            <Icon name="memory" /> Memory
            <span className="nav-count">{state.metrics.operational_memories}</span>
          </button>
        </nav>

        <div className="sidebar-label site-label">Connected sites</div>
        <div className="site-list">
          {state.sites.map((site) => (
            <div className="site-row" key={site.id}>
              <span className={`site-indicator ${site.status}`} />
              <div>
                <strong>{site.name.replace(" Mini-Grid", "")}</strong>
                <small>{site.capacity_kw} kW · {site.inverter_model}</small>
              </div>
              <span className="site-status">{site.status}</span>
            </div>
          ))}
        </div>

        <div className="sidebar-foot">
          <span>GR</span>
          <div>
            <strong>Field operations</strong>
            <small>Human approval enabled</small>
          </div>
        </div>
      </aside>

      <main className="content">
        <section className="page-heading">
          <div>
            <p className="eyebrow">Command centre</p>
            <h1>Every fault makes the next repair faster.</h1>
            <p>{state.message}</p>
          </div>
          <button className="demo-button" onClick={advanceDemo} disabled={loading}>
            {loading ? "Running scenario…" : state.next_action}
            <span aria-hidden="true">→</span>
          </button>
        </section>

        {error && <div className="inline-error">{error}</div>}

        <section className="phase-strip">
          <div>
            <span className="phase-kicker">Demo state</span>
            <strong>{phaseLabels[state.phase]}</strong>
          </div>
          <div className="phase-track" aria-label={`Demo phase: ${phaseLabels[state.phase]}`}>
            <span className="complete" />
            <i className={state.phase !== "ready" ? "complete" : ""} />
            <span className={state.phase !== "ready" ? "complete" : ""} />
            <i className={state.phase === "memory_proven" ? "complete" : ""} />
            <span className={state.phase === "memory_proven" ? "complete" : ""} />
          </div>
          <div className="phase-names">
            <span>Detect</span>
            <span>Remember</span>
            <span>Improve</span>
          </div>
        </section>

        <section className="metrics-grid">
          <Metric
            label="Outage time avoided"
            value={`${state.metrics.minutes_of_outage_avoided}`}
            unit="minutes"
            accent="green"
          />
          <Metric
            label="Failed steps not repeated"
            value={`${state.metrics.failed_actions_not_repeated}`}
            unit="actions"
            accent="amber"
          />
          <Metric
            label="Energy unavailability avoided"
            value={`${state.metrics.unavailable_energy_avoided_kwh}`}
            unit="kWh"
            accent="blue"
          />
          <Metric
            label="Outcome-scored memories"
            value={`${state.metrics.operational_memories}`}
            unit="cases"
            accent="violet"
          />
        </section>

        <section className="workspace-grid">
          <div className="panel incident-panel">
            <PanelHeader
              eyebrow="Active investigation"
              title={currentIncident?.context.site_name ?? "No incident selected"}
              badge={currentIncident ? "Resolved" : "Standing by"}
            />
            {currentIncident ? (
              <IncidentDetail incident={currentIncident} phase={state.phase} />
            ) : (
              <EmptyIncident />
            )}
          </div>

          <div className="right-stack">
            <div className="panel memory-panel">
              <PanelHeader
                eyebrow="Recommendation intelligence"
                title="Memory influence"
                badge={`${currentIncident?.recommendation.evidence.length ?? 0} matches`}
              />
              {currentIncident?.recommendation.evidence.length ? (
                <MemoryInfluence incident={currentIncident} />
              ) : (
                <div className="empty-memory">
                  <div className="memory-orb"><Icon name="memory" /></div>
                  <strong>No relevant outcome memory yet</strong>
                  <p>The first incident begins with the approved base playbook.</p>
                </div>
              )}
            </div>

            <div className="panel comparison-panel">
              <PanelHeader eyebrow="Cross-site learning" title="What changed?" />
              <Comparison first={firstIncident} current={currentIncident} />
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function Metric({
  label,
  value,
  unit,
  accent,
}: {
  label: string;
  value: string;
  unit: string;
  accent: string;
}) {
  return (
    <article className={`metric-card ${accent}`}>
      <div className="metric-icon"><Icon name="pulse" /></div>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{unit}</span>
    </article>
  );
}

function PanelHeader({ eyebrow, title, badge }: { eyebrow: string; title: string; badge?: string }) {
  return (
    <header className="panel-header">
      <div>
        <span>{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      {badge && <em>{badge}</em>}
    </header>
  );
}

function EmptyIncident() {
  return (
    <div className="empty-incident">
      <div className="radar" aria-hidden="true"><span /></div>
      <h3>Fleet telemetry is normal</h3>
      <p>Run the first scenario to inject a controlled inverter fault at Ajegunle.</p>
    </div>
  );
}

function IncidentDetail({ incident, phase }: { incident: Incident; phase: DemoState["phase"] }) {
  const telemetry = incident.context.telemetry;
  return (
    <div className="incident-detail">
      <div className="alert-banner">
        <span>!</span>
        <div>
          <strong>Thermal derating detected</strong>
          <small>{incident.context.inverter_model} · human-reviewed resolution</small>
        </div>
      </div>
      <div className="telemetry-row">
        <TelemetryValue label="Inverter temp" value={telemetry.inverter_temperature_c} suffix="°C" hot />
        <TelemetryValue label="Power output" value={telemetry.power_output_kw} suffix=" kW" />
        <TelemetryValue label="Irradiance" value={telemetry.solar_irradiance_w_m2} suffix=" W/m²" />
        <TelemetryValue label="Battery" value={telemetry.battery_state_of_charge_pct} suffix="%" />
      </div>
      <div className="recommendation-card">
        <div className="recommendation-topline">
          <span>Recommended next action</span>
          <em>{Math.round(incident.recommendation.confidence * 100)}% confidence</em>
        </div>
        <h3>{incident.recommendation.title}</h3>
        <p>{incident.recommendation.explanation}</p>
        <div className="safety-row">
          <span>✓</span>
          {incident.recommendation.safety_status}
        </div>
      </div>
      <div className="attempts">
        <span className="section-caption">Recorded action outcomes</span>
        {incident.attempts.map((attempt, index) => (
          <div className="attempt" key={`${attempt.action}-${index}`}>
            <span className={attempt.succeeded ? "success" : "failed"}>
              {attempt.succeeded ? "✓" : "×"}
            </span>
            <div>
              <strong>{actionLabels[attempt.action]}</strong>
              <p>{attempt.observation}</p>
            </div>
            <em>{attempt.duration_minutes} min</em>
          </div>
        ))}
      </div>
      {phase === "memory_proven" && incident.recommendation.avoided_actions.length > 0 && (
        <div className="avoided-callout">
          <span>↘</span>
          <div>
            <strong>Failed step avoided</strong>
            <p>{actionLabels[incident.recommendation.avoided_actions[0]]} was demoted by remembered evidence.</p>
          </div>
        </div>
      )}
    </div>
  );
}

function TelemetryValue({ label, value, suffix, hot = false }: {
  label: string;
  value: number;
  suffix: string;
  hot?: boolean;
}) {
  return (
    <div className={hot ? "telemetry-value hot" : "telemetry-value"}>
      <span>{label}</span>
      <strong>{value}{suffix}</strong>
    </div>
  );
}

function MemoryInfluence({ incident }: { incident: Incident }) {
  const evidence = incident.recommendation.evidence[0];
  return (
    <div className="memory-content">
      <div className="match-score">
        <div>
          <span>Top operational match</span>
          <strong>{evidence.site_name}</strong>
        </div>
        <b>{Math.round(evidence.influence_score * 100)}%</b>
      </div>
      <div className="score-bar"><span style={{ width: `${evidence.influence_score * 100}%` }} /></div>
      <p className="memory-summary">{evidence.summary}</p>
      <dl>
        <div>
          <dt>Worked</dt>
          <dd className="worked">{actionLabels[evidence.successful_action]}</dd>
        </div>
        <div>
          <dt>Failed</dt>
          <dd className="failed-text">{evidence.failed_actions.map((item) => actionLabels[item]).join(", ")}</dd>
        </div>
      </dl>
      <div className="traceability">Memory ID · {evidence.memory_id.slice(0, 8)}</div>
    </div>
  );
}

function Comparison({ first, current }: { first?: Incident; current?: Incident }) {
  if (!first) {
    return <p className="comparison-empty">Resolve two related incidents to compare their investigation paths.</p>;
  }
  const secondExists = current && current.id !== first.id;
  return (
    <div className="comparison-content">
      <div className="comparison-row">
        <div>
          <span>Ajegunle · no memory</span>
          <strong>{first.attempts.length} diagnostic steps</strong>
        </div>
        <b>{first.time_to_restore_minutes} min</b>
      </div>
      <div className={`comparison-row ${secondExists ? "improved" : "pending"}`}>
        <div>
          <span>Kura · memory assisted</span>
          <strong>{secondExists ? `${current.attempts.length} diagnostic step` : "Awaiting scenario"}</strong>
        </div>
        <b>{secondExists ? `${current.time_to_restore_minutes} min` : "—"}</b>
      </div>
      <div className="comparison-result">
        {secondExists ? (
          <><strong>16 minutes faster</strong><span>because the failed reset was not repeated</span></>
        ) : (
          <><strong>Memory is now ready</strong><span>Run Kura to prove cross-site transfer</span></>
        )}
      </div>
    </div>
  );
}

function Icon({ name }: { name: "grid" | "pulse" | "memory" }) {
  if (name === "grid") {
    return <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="3" width="7" height="7" rx="2" /><rect x="3" y="14" width="7" height="7" rx="2" /><rect x="14" y="14" width="7" height="7" rx="2" /></svg>;
  }
  if (name === "memory") {
    return <svg viewBox="0 0 24 24"><path d="M12 3a4 4 0 0 0-4 4v.2A4.5 4.5 0 0 0 6.5 16H8v1a4 4 0 0 0 8 0v-1h1.5A4.5 4.5 0 0 0 16 7.2V7a4 4 0 0 0-4-4Z" /><path d="M9 9h6M9 13h6" /></svg>;
  }
  return <svg viewBox="0 0 24 24"><path d="M3 12h4l2-6 4 12 2-6h6" /></svg>;
}

export default App;
