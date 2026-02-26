// examples of configs: https://github.com/e-mission/nrel-openpath-deploy-configs/tree/main/configs

export type DeploymentConfig = {
  url_abbreviation?: string; // TODO: this should probably be required; we could fill it in for old configs based on filename
  version: number;
  ts: number;
  server?: ServerConnConfig; // TODO: this is required for any real deployments but missing for dev-emulator- configs, so I have to mark it as optional. Maybe the dev-emulator- configs should explicitly say localhost here so we can mark this as required
  opcode?: OpcodeConfig;
  intro: IntroConfig;
  survey_info?: {
    "trip-labels": "MULTILABEL" | "ENKETO";
    surveys: EnketoSurveyConfig;
    buttons?: SurveyButtonsConfig;
  };
  label_options?: `https://${string}`;
  vehicle_identities?: VehicleIdentity[];
  reminderSchemes?: ReminderSchemesConfig;
  tracking?: Partial<TrackingConfig>;
  sync?: Partial<SyncConfig>;
  display_config: {
    use_imperial: boolean;
  };
  metrics?: MetricsConfig;
  push_notifications?: any; // TODO: fill in
  profile_controls: any; // TODO: fill in
  admin_dashboard: AdminDashboardConfig;
};

export type ServerConnConfig = {
  connectUrl: `https://${string}`;
  aggregate_call_auth: "no_auth" | "user_only" | "never";
};

export type OpcodeConfig = {
  autogen: boolean;
  subgroups?: string[];
  suspended_subgroups?: string[];
};

export type IntroConfig = {
  program_or_study: "program" | "study";
  app_required?: boolean;
  start_month: string; // might be "M" or "MM"; TODO maybe this should be a number
  start_year: string; // "YYYY"; TODO maybe this should be a number
  mode_studied?: string | string[];
  program_admin_email: string;
  program_admin_contact: string;
  deployment_partner_name: string;
  translated_text: {
    [lang: string]: {
      deployment_partner_name: string;
      deployment_name: string;
      summary_line_1: string;
      summary_line_2: string;
      summary_line_3: string;
      short_textual_description: string;
      why_we_collect: string;
      why_we_collect_es?: string; // TODO this seems like it should be removed
      raw_data_use?: string; // oddly, this is ONLY defined for denver-casr
      research_questions: string[];
    };
  };
};

export type EnketoSurveyConfig = {
  [surveyName: string]: {
    formPath: string;
    labelTemplate: { [lang: string]: string };
    labelVars?: { [activity: string]: { [key: string]: string; type: string } };
    version: number;
    compatibleWith: number;
    dataKey?: string;
  };
};
export type SurveyButtonConfig = {
  surveyName: string;
  "not-filled-in-label": {
    [lang: string]: string;
  };
  showsIf?: string; // a JS expression that evaluates to a boolean
};
export type SurveyButtonsConfig = {
  [k in "trip-label" | "trip-notes" | "place-label" | "place-notes"]?:
    | SurveyButtonConfig
    | SurveyButtonConfig[];
};

export type VehicleIdentity = {
  value: string;
  bluetooth_major_minor: string[]; // e.g. ['aaaa:bbbb', 'cccc:dddd']
  text: string;
  baseMode: string;
  met_equivalent: string;
  kgCo2PerKm: number;
  vehicle_info: {
    type: string; // TODO what is the point of this if we already have base mode and engine type?
    make: string;
    model: string;
    year: number;
    engine: "ICE" | "HEV" | "PHEV" | "BEV" | "HYDROGENV" | "BIOV";
    license?: string;
    color?: string;
    mpge?: number;
  };
};

export type ReminderSchemesConfig = {
  [schemeKey: string]: {
    schedule: {
      start: number;
      end?: number;
      intervalInDays: number;
    }[];
    title?: { [lang: string]: string };
    text?: { [lang: string]: string };
    defaultTime?: string; // format is HH:MM in 24 hour time
  };
};

// corresponds to LocationTrackingConfig in e-mission-data-collection
export type TrackingConfig = {
  is_duty_cycling: boolean;
  simulate_user_interaction: boolean;
  accuracy: number;
  accuracy_threshold: number;
  filter_distance: number;
  filter_time: number;
  geofence_radius: number;
  ios_use_visit_notifications_for_detection: boolean;
  ios_use_remote_push_for_sync: boolean;
  android_geofence_responsiveness: number;
  is_fleet: boolean;
};

// corresponds to ServerSyncConfig in cordova-server-sync
export type SyncConfig = {
  sync_interval: number; // seconds
  ios_use_remote_push: boolean;
};

// the available metrics that can be displayed in the phone dashboard
export type MetricName =
  | "distance"
  | "count"
  | "duration"
  | "response_count"
  | "footprint";
// the available trip / userinput properties that can be used to group the metrics
export type GroupingField =
  | "mode_confirm"
  | "purpose_confirm"
  | "replaced_mode_confirm"
  | "primary_ble_sensed_mode"
  | "survey";
export type MetricList = { [k in MetricName]?: GroupingField[] };
export type MetricsUiSection = "footprint" | "movement" | "surveys" | "travel";
export type FootprintGoal = {
  label: { [lang: string]: string };
  value: number;
  color?: string;
};
export type FootprintGoals = {
  carbon: FootprintGoal[];
  energy: FootprintGoal[];
  goals_footnote?: { [lang: string]: string };
};
export type MetricsConfig = {
  include_test_users: boolean;
  phone_dashboard_ui?: {
    sections: MetricsUiSection[];
    metric_list: MetricList;
    footprint_options?: {
      unlabeled_uncertainty: boolean;
      goals?: FootprintGoals;
    };
    movement_options?: {};
    surveys_options?: {};
    travel_options?: {};
  };
};

export type AdminDashboardConfig = {
  data_trips_columns_exclude?: string[];
  additional_trip_columns?: string[];
  data_uuids_columns_exclude?: string[];
  data_trajectories_columns_exclude?: string[];
  token_prefix?: string;
  token_generate?: boolean;
  overview_users?: boolean;
  overview_active_users?: boolean;
  overview_trips?: boolean;
  overview_signup_trends?: boolean;
  overview_trips_trend?: boolean;
  data_uuids?: boolean;
  data_trips?: boolean;
  map_heatmap?: boolean;
  map_bubble?: boolean;
  map_trip_lines?: boolean;
  push_send?: boolean;
  options_uuids?: boolean;
  options_emails?: boolean;
  admin_access?: string[]; // list of email addresses
};

export default DeploymentConfig;
