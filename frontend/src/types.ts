
export enum Severity {
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW',
}

export interface Rule {
  rule_id: string;
  description: string;
  sql_query?: string; // Added for Uploader preview
  quote: string;
  severity: Severity;
}

export interface Policy {
  policy_id: string;
  name: string;
  rules: Rule[];
}

export type ViolatingRecord = Record<string, any>;

export interface ViolationDetail {
  policy_name: string;
  rule_id: string;
  severity: Severity;
  description: string;
  quote: string;
  violation_reason?: string; // Added for Dashboard feed
  violating_records: ViolatingRecord[];
  total_matches?: number; // Total count from optimized query
}

export interface ComplianceReport {
  timestamp: string;
  total_violations: number;
  details: ViolationDetail[];
}

export interface DatabaseTables {
  expenses: Record<string, any>[];
  employees: Record<string, any>[];
  financial_transactions: Record<string, any>[];
  gdpr_violations: Record<string, any>[];
}

export interface SystemStats {
  risk_score: 'Low' | 'Medium' | 'High';
  total_violations: number;
  active_policies: number;
  real_time_events: number;
}
