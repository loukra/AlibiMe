import Foundation

// Raw data-transfer objects at the network boundary. These mirror the backend
// JSON exactly — including its internal naming (`scenario`-era names are not
// present here, the backend already uses `template`/`request`). App-facing
// models (see Models/) translate these into product language.

// MARK: Auth

struct PhoneStartRequestDTO: Encodable {
    let phone_number: String
    let device_id: String?
    let locale: String
}

struct PhoneStartResponseDTO: Decodable {
    let verification_id: String
    let channel: String
    let expires_in_seconds: Int
}

struct PhoneConfirmRequestDTO: Encodable {
    let verification_id: String
    let code: String
    let device_id: String?
}

struct UserPublicDTO: Decodable {
    let id: String
    let locale: String
    let phone_number_masked: String?
}

struct PhoneConfirmResponseDTO: Decodable {
    let session_token: String
    let user: UserPublicDTO
}

struct LogoutResponseDTO: Decodable {
    let status: String
}

// MARK: Me / profile

struct EntitlementSummaryItemDTO: Decodable {
    let plan_code: String?
    let status: String
}

struct ActiveRequestSummaryDTO: Decodable {
    let request_id: String
    let channel: String
    let status: String
    let execute_at: String
}

struct MeResponseDTO: Decodable {
    let id: String
    let locale: String
    let timezone: String
    let display_name: String?
    let phone_number_masked: String?
    let credits_available: Int
    let active_entitlements: [EntitlementSummaryItemDTO]
    let active_request: ActiveRequestSummaryDTO?
}

struct MeUpdateDTO: Encodable {
    var locale: String?
    var timezone: String?
    var display_name: String?
}

// MARK: Devices

struct DeviceUpsertDTO: Encodable {
    let device_id: String
    let platform: String
    let push_token: String?
    let app_version: String?
    let os_version: String?
}

struct DeviceResponseDTO: Decodable {
    let id: String
    let device_id: String
    let platform: String
}

// MARK: Templates

struct TemplateOutDTO: Decodable {
    let id: String
    let code: String
    let display_name: String
    let description: String?
    let category: String
    let caller_persona: String
    let reason_code: String
    let sender_persona_key: String
    let sender_display_name: String
    let supports_contact_save: Bool
    let supported_channels: [String]
    let call_max_duration_seconds: Int?
    let preview_opening_line: String?
    let preview_sms_body: String?
}

struct TemplateListResponseDTO: Decodable {
    let templates: [TemplateOutDTO]
}

// MARK: Requests

struct CreateRequestBodyDTO: Encodable {
    let client_request_id: String
    let template_id: String
    let channel: String
    let delay_seconds: Int?
    let scheduled_at: Date?
}

struct SenderIdentityDTO: Decodable {
    let sender_binding_id: String
    let sender_persona_key: String?
    let sender_display_name: String?
    let sender_phone_e164: String?
    let contact_prompt_recommended: Bool
}

struct CreateRequestResponseDTO: Decodable {
    let request_id: String
    let channel: String
    let status: String
    let execute_at: Date
    let credits_available: Int
    let cancelable: Bool
    let sender_identity: SenderIdentityDTO?
}

struct AttemptSummaryDTO: Decodable {
    let status: String
    let provider_status: String?
    let duration_seconds: Int?
    let failure_reason: String?
}

struct RequestDetailDTO: Decodable {
    let request_id: String
    let channel: String
    let status: String
    let scheduled_kind: String
    let execute_at: Date
    let requested_at: Date
    let cancelable: Bool
    let last_error_code: String?
    let latest_attempt: AttemptSummaryDTO?
    let sender_identity: SenderIdentityDTO?
}

struct CancelResponseDTO: Decodable {
    let request_id: String
    let status: String
}

// MARK: History

struct HistoryItemDTO: Decodable {
    let request_id: String
    let channel: String
    let template_label: String
    let requested_at: Date
    let final_status: String
    let duration_seconds: Int?
    let delivered_preview: String?
    let sender_binding_id: String?
    let sender_persona_key: String?
    let sender_display_name: String?
    let sender_phone_e164: String?
}

struct HistoryResponseDTO: Decodable {
    let items: [HistoryItemDTO]
    let limit: Int
    let offset: Int
    let has_more: Bool
}

// MARK: Entitlements

struct EntitlementItemDTO: Decodable {
    let plan_code: String?
    let status: String
}

struct EntitlementsResponseDTO: Decodable {
    let credits_available: Int
    let active_entitlements: [EntitlementItemDTO]
}

// MARK: Credit packages

struct CreditPackageDTO: Decodable {
    let code: String
    let display_name: String
    let credits: Int
    let fulfillment_mode: String
    let price_label: String
    let badge_text: String?
    let active: Bool
    let sort_order: Int
}

struct CreditPackagesResponseDTO: Decodable {
    let packages: [CreditPackageDTO]
}

struct AcquirePackageRequestDTO: Encodable {
    let client_request_id: String
}

struct AcquirePackageResponseDTO: Decodable {
    let claim_id: String
    let status: String
    let granted_credits: Int
    let credits_available: Int
    let plan_code: String
}

// MARK: Error envelope

struct ErrorBodyDTO: Decodable {
    let code: String
    let message: String
    let retryable: Bool
    let request_id: String?
}

struct ErrorResponseDTO: Decodable {
    let error: ErrorBodyDTO
}
