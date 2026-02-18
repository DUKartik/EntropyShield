
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
}

export interface ComplianceReport {
  timestamp: string;
  total_violations: number;
  details: ViolationDetail[];
}

export interface DatabaseTables {
  expenses: Record<string, any>[];
  employees: Record<string, any>[];
  contracts: Record<string, any>[];
}
