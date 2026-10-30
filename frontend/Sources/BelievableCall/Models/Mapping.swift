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
            isCustom: dto.is_custom ?? false,
            supportedChannels: Set(channels),
            callMaxDurationSeconds: dto.call_max_duration_seconds,
            previewOpeningLine: dto.preview_opening_line,
            previewSMSBody: dto.preview_sms_body
        )
    }
}

private func _opts(_ items: [TemplateOptionItemDTO]) -> [TemplateOption] {
    items.map { TemplateOption(code: $0.code, label: $0.label) }
}

extension ProfileOptions {
    init(dto: ProfileOptionsDTO) {
        var p = ProfileOptions()
        p.workIndustries = _opts(dto.work_industries)
        p.workRoleLevels = _opts(dto.work_role_levels)
        p.workSettings = _opts(dto.work_settings)
        p.workSchedules = _opts(dto.work_schedules)
        p.workTravelScopes = _opts(dto.work_travel_scopes)
        p.livingSetups = _opts(dto.living_setups)
        p.homeResponsibilities = _opts(dto.home_responsibilities)
        p.dependentContexts = _opts(dto.dependent_contexts)
        p.familySupportLevels = _opts(dto.family_support_levels)
        p.familyProximities = _opts(dto.family_proximities)
        p.relationshipVisibilities = _opts(dto.relationship_visibilities)
        p.relationshipStages = _opts(dto.relationship_stages)
        p.privacyPreferences = _opts(dto.privacy_preferences)
        p.transitionStates = _opts(dto.transition_states)
        p.transitionHorizons = _opts(dto.transition_horizons)
        self = p
    }
}

extension TemplateOptions {
    init(dto: TemplateOptionsResponseDTO) {
        var o = TemplateOptions()
        o.categories = dto.categories
        o.personas = _opts(dto.personas)
        o.reasons = _opts(dto.reasons)
        o.urgencies = dto.urgencies
        o.outcomes = _opts(dto.outcomes)
        o.settings = _opts(dto.settings)
        o.detailProfiles = dto.detail_profiles
        o.discretionLevels = dto.discretion_levels
        o.tones = dto.tones
        o.formalities = dto.formalities
        o.expectedResponses = _opts(dto.expected_responses)
        o.followupBehaviors = _opts(dto.followup_behaviors)
        o.continuityScopes = dto.continuity_scopes
        o.contextModules = dto.context_modules
        o.voiceStyles = dto.voice_styles
        o.channels = dto.channels.compactMap { Channel(wireValue: $0) }
        o.callSecondsMin = dto.call_seconds_min
        o.callSecondsMax = dto.call_seconds_max
        o.callSecondsDefault = dto.call_seconds_default
        o.profile = ProfileOptions(dto: dto.profile)
        self = o
    }
}

extension ContextProfile {
    init(dto: ContextProfileDTO) {
        self.init(
            workIndustry: dto.work_industry_code,
            workRoleLevel: dto.work_role_level_code,
            workSetting: dto.work_setting_code,
            workSchedule: dto.work_schedule_code,
            workTravelScope: dto.work_travel_scope_code,
            livingSetup: dto.living_setup_code,
            homeResponsibilities: dto.home_responsibility_codes_json ?? [],
            dependentContexts: dto.dependent_context_codes_json ?? [],
            familySupportLevel: dto.family_support_level_code,
            familyProximity: dto.family_proximity_code,
            relationshipVisibility: dto.relationship_visibility_code,
            relationshipStage: dto.relationship_stage_code,
            privacyPreference: dto.privacy_preference_code,
            transitionState: dto.transition_state_code,
            transitionHorizon: dto.transition_horizon_code
        )
    }

    func toDTO() -> ContextProfileDTO {
        ContextProfileDTO(
            work_industry_code: workIndustry,
            work_role_level_code: workRoleLevel,
            work_setting_code: workSetting,
            work_schedule_code: workSchedule,
            work_travel_scope_code: workTravelScope,
            living_setup_code: livingSetup,
            home_responsibility_codes_json: homeResponsibilities,
            dependent_context_codes_json: dependentContexts,
            family_support_level_code: familySupportLevel,
            family_proximity_code: familyProximity,
            relationship_visibility_code: relationshipVisibility,
            relationship_stage_code: relationshipStage,
            privacy_preference_code: privacyPreference,
            transition_state_code: transitionState,
            transition_horizon_code: transitionHorizon
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
            executeAt: dto.execute_at,
            status: RequestStatus(wireValue: dto.final_status),
            cancelable: dto.cancelable ?? false,
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

extension CreditPackage {
    init(dto: CreditPackageDTO) {
        self.init(
            code: dto.code,
            displayName: dto.display_name,
            credits: dto.credits,
            fulfillmentMode: dto.fulfillment_mode,
            priceLabel: dto.price_label,
            badgeText: dto.badge_text,
            sortOrder: dto.sort_order,
            storeProductID: dto.store_product_id
        )
    }
}

extension CreditAcquisition {
    init(dto: AcquirePackageResponseDTO) {
        self.init(
            claimID: dto.claim_id,
            status: dto.status,
            grantedCredits: dto.granted_credits,
            creditsAvailable: dto.credits_available,
            planCode: dto.plan_code
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
