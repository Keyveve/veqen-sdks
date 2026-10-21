export type Verdict = "admit" | "review" | "refuse";

export interface Reason {
  code: string;
  impact: number;
  message: string;
  source?: "email" | "ip" | "phone" | "signup" | null;
}

export interface Risk {
  score: number;
  level: "low" | "medium" | "high";
  verdict: Verdict;
  reasons: Reason[];
}

export interface DomainInfo {
  exists: boolean;
  accepts_mail: boolean | null;
  mx: string[];
  null_mx: boolean;
  spf: boolean;
  dmarc: boolean;
  registered_at: string | null;
  age_days: number | null;
  registrar: string | null;
}

export interface EmailCheck {
  email: string;
  valid_syntax: boolean;
  syntax_error?: string | null;
  normalized?: string | null;
  canonical?: string | null;
  local_part?: string | null;
  domain?: string | null;
  disposable?: boolean | null;
  free_provider?: boolean | null;
  role_account?: boolean | null;
  plus_addressed?: boolean | null;
  did_you_mean?: string | null;
  domain_info?: DomainInfo | null;
  mailbox?: { checked: boolean; result: "deliverable" | "undeliverable" | "catch_all" | "unknown"; smtp_code?: number | null; reason?: string | null } | null;
  risk: Risk;
}

export interface IpCheck {
  ip: string;
  valid: boolean;
  version?: number | null;
  type?: "public" | "private" | "loopback" | "link_local" | "multicast" | "reserved" | "special" | null;
  location?: {
    country_code: string | null;
    country: string | null;
    in_eu: boolean | null;
    region: string | null;
    city: string | null;
    continent: string | null;
    latitude: number | null;
    longitude: number | null;
  } | null;
  network?: {
    asn: number | null;
    organization: string | null;
    kind: "cloud" | "hosting" | "cdn" | "vpn_hosting" | "isp" | "unknown";
    kind_label: string;
    known_network: string | null;
  } | null;
  flags?: { hosting: boolean; vpn_likely: boolean; relay: boolean; tor: boolean } | null;
  risk: Risk;
}

export interface PhoneCheck {
  input: string;
  valid: boolean;
  possible: boolean;
  error?: string | null;
  e164?: string | null;
  international?: string | null;
  national?: string | null;
  calling_code?: number | null;
  country_code?: string | null;
  country?: string | null;
  location?: string | null;
  line_type?: string | null;
  line_type_label?: string | null;
  carrier?: string | null;
  time_zones: string[];
  risk: Risk;
}

export interface DomainCheck extends Partial<DomainInfo> {
  input: string;
  valid: boolean;
  domain?: string | null;
  disposable?: boolean | null;
  free_provider?: boolean | null;
  risk: Risk;
}

export interface SignupCheck {
  email: EmailCheck | null;
  ip: IpCheck | null;
  phone: PhoneCheck | null;
  risk: Risk;
}

export interface VeqenOptions {
  apiKey?: string;
  baseUrl?: string;
  timeoutMs?: number;
  maxRetries?: number;
  fetch?: typeof fetch;
}

export class VeqenError extends Error {
  status: number;
  type: string;
  requestId: string | null;
}

export class Veqen {
  constructor(options?: VeqenOptions);
  email(email: string, options?: { verifyMailbox?: boolean; idempotencyKey?: string }): Promise<EmailCheck>;
  emails(emails: string[], options?: { verifyMailbox?: boolean }): Promise<EmailCheck[]>;
  ip(ip: string, options?: { idempotencyKey?: string }): Promise<IpCheck>;
  phone(phone: string, options?: { country?: string; idempotencyKey?: string }): Promise<PhoneCheck>;
  domain(domain: string, options?: { idempotencyKey?: string }): Promise<DomainCheck>;
  signup(input: { email?: string; ip?: string; phone?: string; phoneCountry?: string; verifyMailbox?: boolean; idempotencyKey?: string }): Promise<SignupCheck>;
  account(): Promise<{ email: string; balance: { free: number; paid: number; total: number }; free_monthly_credits: number; free_resets_at: string; costs: Record<string, number>; rate_limit_per_second: number }>;
  usage(days?: number): Promise<{ days: { date: string; credits: number; calls: number; by_check: Record<string, number> }[]; total_credits: number; total_calls: number }>;
}

export default Veqen;
