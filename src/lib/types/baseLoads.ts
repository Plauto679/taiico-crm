export interface BaseLoadPreviewStats {
    allowed_agent_keys: number;
    source_rows: number;
    rows_after_agent_filter: number;
    unique_a_x_rows: number;
    duplicate_a_x_rows: number;
    unique_incoming_policies: number;
    unique_policy_periods: number;
    policies_with_multiple_rows: number;
    existing_policies_updated: number;
    new_policies_added: number;
    current_policies_preserved_as_exceptions: number;
    current_rows_preserved_as_exceptions: number;
    rows_with_preserved_y_plus_data: number;
    final_policy_count: number;
    final_row_count: number;
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
