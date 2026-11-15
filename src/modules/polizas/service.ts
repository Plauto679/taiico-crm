import { fetchFromApi } from '@/lib/api';
export type PolicyInput = {policy_number:string;rfc:string;product_id:string;effective_start_date:string;effective_end_date:string;premium_amount:string;payment_frequency:string;status:string;document_link:string;agent:string;insured_names:string[];emission_row?:number;emission_fingerprint?:string};
export type PolicyRow = PolicyInput & {id:string;client_id:string;insurer_id:string;client_name:string;client_folder:string|null;insurer:string;branch:string;product:string;issues:string[];fingerprint:string;registry:{agent?:string;insured_names?:string[];emission?:unknown;source_conflicts?:unknown[]};origin:string;created_at:string;updated_at:string};
export type PolicyDetail = PolicyRow & {assignments:{name:string;rate:number;from:string;to:string|null;active:boolean;source:string}[];renewals:{date:string;status:string;next_policy_id:string|null}[];documents:{name:string;category:string;url:string}[];history:{date:string;source:string;actor:string;before:unknown;after:unknown}[]};
export type Inventory = {rows:PolicyRow[];total:number;inventory_total:number;review_count:number;page:number;pages:number};
export type Options = {can_operate:boolean;products:{id:string;name:string;branch:string;insurer_id:string}[]};
export type PreviewRow = {kind:string;policy_number:string;client_name?:string;message?:string;applied?:boolean;dismissed?:boolean;changes?:{field:string;before:string;after:string}[]};
export type ImportPreview = {id:string;name?:string;date?:string;status:string;rows:PreviewRow[]};
export function api<T>(path:string,body?:unknown,method='POST'):Promise<T>{return fetchFromApi<T>('/polizas'+path,body===undefined?undefined:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
