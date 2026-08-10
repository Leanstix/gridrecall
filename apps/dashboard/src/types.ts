export type ActionType =
  | "continue_monitoring"
  | "inspect_ventilation"
  | "approved_inverter_reset"
  | "inspect_connections"
  | "reduce_noncritical_load"
  | "isolate_component"
  | "dispatch_technician"
  | "escalate_engineer";

export interface Site {
  id: string;
  name: string;
  community: string;
  capacity_kw: number;
  inverter_model: string;
  status: string;
}

export interface MemoryEvidence {
  memory_id: string;
  site_name: string;
  similarity: number;
  influence_score: number;
  successful_action: ActionType;
  failed_actions: ActionType[];
  summary: string;
}

export interface Recommendation {
  action: ActionType;
  title: string;
  explanation: string;
  confidence: number;
  safety_status: string;
  escalation_condition: string;
  evidence: MemoryEvidence[];
  avoided_actions: ActionType[];
}

export interface RepairAttempt {
  action: ActionType;
  succeeded: boolean;
  observation: string;
  duration_minutes: number;
}

export interface Incident {
  id: string;
  context: {
    site_name: string;
    inverter_model: string;
    fault_type: string;
    symptoms: string[];
    telemetry: {
      inverter_temperature_c: number;
      power_output_kw: number;
      solar_irradiance_w_m2: number;
      battery_state_of_charge_pct: number;
      ambient_temperature_c: number;
      load_demand_kw: number;
      alarms: string[];
    };
  };
  status: string;
  recommendation: Recommendation;
  attempts: RepairAttempt[];
  time_to_restore_minutes: number | null;
  baseline_restore_minutes: number;
  unavailable_energy_avoided_kwh: number;
}

export interface DemoState {
  phase: "ready" | "first_resolved" | "memory_proven";
  message: string;
  sites: Site[];
  incidents: Incident[];
  memories: unknown[];
  metrics: {
    incidents_resolved: number;
    minutes_of_outage_avoided: number;
    failed_actions_not_repeated: number;
    unavailable_energy_avoided_kwh: number;
    operational_memories: number;
  };
  next_action: string;
}
