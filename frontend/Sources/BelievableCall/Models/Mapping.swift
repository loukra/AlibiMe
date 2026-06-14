import Foundation

// DTO → app-model translation. This is the only place backend wire shapes turn
// into product-language models.

extension TemplateCategory {
    init(wireValue: String) {
        self = TemplateCategory(rawValue: wireValue) ?? .social
    }
}

extension TemplateSummary {
    init(dto: TemplateOutDTO) {
        let channels = dto.supported_channels.compactMap { Channel(wireValue: $0) }
        self.init(
            id: dto.id,
            code: dto.code,
            displayName: dto.display_name,
            description: dto.description,
            category: TemplateCategory(wireValue: dto.category),
            callerPersona: dto.caller_persona,
            reasonCode: dto.reason_code,
            senderPersonaKey: dto.sender_persona_key,
            senderDisplayName: dto.sender_display_name,
            supportsContactSave: dto.supports_contact_save,
            supportedChannels: Set(channels),
            callMaxDurationSeconds: dto.call_max_duration_seconds,
            previewOpeningLine: dto.preview_opening_line,
            previewSMSBody: dto.preview_sms_body
        )
    }
}

extension SenderIdentity {
    init(dto: SenderIdentityDTO) {
        self.init(
            bindingID: dto.sender_binding_id,
            personaKey: dto.sender_persona_key,
            displayName: dto.sender_display_name,
            phoneE164: dto.sender_phone_e164,
            contactPromptRecommended: dto.contact_prompt_recommended
        )
    }
}

extension EntitlementSummary {
    init(creditsAvailable: Int, items: [EntitlementSummaryItemDTO]) {
        self.init(
            creditsAvailable: creditsAvailable,
            planCodes: items.compactMap { $0.plan_code }
        )
    }
    init(dto: EntitlementsResponseDTO) {
        self.init(
            creditsAvailable: dto.credits_available,
            planCodes: dto.active_entitlements.compactMap { $0.plan_code }
        )
    }
}

extension RequestSummary {
    /// Built from the lightweight active-request summary on `/v1/me`.
    init?(active: ActiveRequestSummaryDTO?) {
        guard let active else { return nil }
        guard let channel = Channel(wireValue: active.channel),
              let executeAt = BCCoding.parseDate(active.execute_at) else { return nil }
        self.init(
            id: active.request_id,
            channel: channel,
            status: RequestStatus(wireValue: active.status),
            scheduledKind: nil,
            executeAt: executeAt,
            requestedAt: nil,
            cancelable: RequestStatus(wireValue: active.status).isLive,
            lastErrorCode: nil
        )
    }

    init(dto: CreateRequestResponseDTO) {
        self.init(
            id: dto.request_id,
            channel: Channel(wireValue: dto.channel) ?? .call,
            status: RequestStatus(wireValue: dto.status),
            scheduledKind: nil,
            executeAt: dto.execute_at,
            requestedAt: nil,
            cancelable: dto.cancelable,
            lastErrorCode: nil,
            senderIdentity: dto.sender_identity.map(SenderIdentity.init(dto:))
        )
    }

    init(dto: RequestDetailDTO) {
        self.init(
            id: dto.request_id,
            channel: Channel(wireValue: dto.channel) ?? .call,
            status: RequestStatus(wireValue: dto.status),
            scheduledKind: dto.scheduled_kind,
            executeAt: dto.execute_at,
            requestedAt: dto.requested_at,
            cancelable: dto.cancelable,
            lastErrorCode: dto.last_error_code,
            senderIdentity: dto.sender_identity.map(SenderIdentity.init(dto:))
        )
    }
}

extension HistoryEntry {
    init(dto: HistoryItemDTO) {
        // History keeps an immutable sender snapshot; rebuild a SenderIdentity
        // for the save-contact re-entry point when a binding was recorded.
        let sender: SenderIdentity? = dto.sender_binding_id.map { bindingID in
            SenderIdentity(
                bindingID: bindingID,
                personaKey: dto.sender_persona_key,
                displayName: dto.sender_display_name,
                phoneE164: dto.sender_phone_e164,
                contactPromptRecommended: false
            )
        }
        self.init(
            id: dto.request_id,
            channel: Channel(wireValue: dto.channel) ?? .call,
            templateLabel: dto.template_label,
            requestedAt: dto.requested_at,
            status: RequestStatus(wireValue: dto.final_status),
            durationSeconds: dto.duration_seconds,
            preview: dto.delivered_preview,
            senderIdentity: sender
        )
    }
}

extension UserProfile {
    init(dto: MeResponseDTO) {
        self.init(
            id: dto.id,
            locale: dto.locale,
            timezone: dto.timezone,
            displayName: dto.display_name,
            phone: VerifiedPhoneSummary(maskedNumber: dto.phone_number_masked),
            entitlements: EntitlementSummary(
                creditsAvailable: dto.credits_available,
                items: dto.active_entitlements
            ),
            activeRequest: RequestSummary(active: dto.active_request)
        )
    }
}

// MARK: Outgoing request mapping

/// Bundles the user's home-screen selection into the backend request body,
/// without ever including a destination number.
public struct RequestDraft: Equatable, Sendable {
    public let templateID: String
    public let channel: Channel
    public let timing: TimingOption
    public let clientRequestID: String

    public init(templateID: String,
                channel: Channel,
                timing: TimingOption,
                clientRequestID: String = UUID().uuidString) {
        self.templateID = templateID
        self.channel = channel
        self.timing = timing
        self.clientRequestID = clientRequestID
    }

    func toBody() -> CreateRequestBodyDTO {
        CreateRequestBodyDTO(
            client_request_id: clientRequestID,
            template_id: templateID,
            channel: channel.wireValue,
            delay_seconds: timing.delaySeconds,
            scheduled_at: timing.scheduledAt
        )
    }
}
