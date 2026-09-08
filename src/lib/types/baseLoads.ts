export interface BaseLoadPreviewStats {
    allowed_agent_keys: number;
    source_rows: number;
    rows_after_agent_filter: number;
    unique_incoming_policies: number;
    existing_policies_updated: number;
    new_policies_added: number;
    current_policies_preserved_as_exceptions: number;
    final_policy_count: number;
    final_row_count: number;
    unique_a_x_rows?: number;
    duplicate_a_x_rows?: number;
    unique_policy_periods?: number;
    policies_with_multiple_rows?: number;
    current_rows_preserved_as_exceptions?: number;
    rows_with_preserved_y_plus_data?: number;
    duplicate_policy_rows?: number;
    statuses_changed?: number;
    statuses_unchanged?: number;
    rows_with_preserved_internal_data?: number;
}

export interface BaseLoadPreview {
    token: string;
    filename: string;
    size: number;
    sha256: string;
    created_at: string;
    preview: BaseLoadPreviewStats;
}

export interface BaseLoadApplyResult extends BaseLoadPreviewStats {
    applied: true;
    filename: string;
    backup_file_id: string;
    backup_name: string;
    backup_url: string;
    backup_folder_id: string;
    canonical_path: string;
    drive_file_id: string;
    drive_name: string;
    drive_url: string;
    drive_md5: string;
    drive_size: string;
    drive_modified_time: string;
    drive_version: string;
}
