import Foundation

// Mock services for SwiftUI previews and unit tests. These are UI-development /
// test fixtures only; the running app always uses the Live* services against
// the real backend.

public enum Fixtures {
    /// What the backend sends as a built-in's editor choices.
    static func choices(name: String, channels: Set<Channel>) -> CustomTemplateDraft {
        var draft = CustomTemplateDraft()
        draft.displayName = name
        draft.category = "work"
        draft.persona = "manager"
        draft.reason = "work_urgent_task"
        draft.urgency = "high"
        draft.channels = channels
        return draft
    }

    public static func template(
        id: String = "tpl-boss-urgent",
        code: String = "coworker_urgent_work_issue",
        name: String = "Boss — urgent work issue",
        category: TemplateCategory = .work,
        channels: Set<Channel> = [.call, .text]
    ) -> TemplateSummary {
        TemplateSummary(
            id: id, code: code, displayName: name,
            description: "Your boss calls about an urgent work issue.",
            category: category, callerPersona: "boss", reasonCode: "urgent_work_issue",
            senderPersonaKey: "boss", senderDisplayName: "Boss", supportsContactSave: true,
            choices: choices(name: name, channels: channels),
            supportedChannels: channels, callMaxDurationSeconds: 60,
            previewOpeningLine: "Hi, sorry to call — there's an urgent issue I need you on.",
            previewSMSBody: "Need you on an urgent work issue — can you call back?"
        )
    }

    public static func senderIdentity(
        bindingID: String = "binding-1",
        persona: String = "boss",
        displayName: String = "Boss",
        phone: String = "+15551234567",
        promptRecommended: Bool = true
    ) -> SenderIdentity {
        SenderIdentity(bindingID: bindingID, personaKey: persona, displayName: displayName,
                       phoneE164: phone, contactPromptRecommended: promptRecommended)
    }

    public static let templates: [TemplateSummary] = [
        template(),
        template(id: "tpl-boss-travel", code: "boss_travel_assignment",
                 name: "Boss — work trip abroad", category: .work, channels: [.call]),
        template(id: "tpl-sibling", code: "sibling_family_checkin",
                 name: "Sibling — family check-in", category: .family, channels: [.call, .text]),
        template(id: "tpl-roommate", code: "roommate_issue_at_home",
                 name: "Roommate — issue at home", category: .logistics, channels: [.text]),
        template(id: "tpl-friend", code: "best_friend_need_you_outside",
                 name: "Best friend — needs you outside", category: .social, channels: [.call, .text]),
        template(id: "tpl-safety", code: "safety_checkin",
                 name: "Safety check-in", category: .safety, channels: [.call, .text]),
    ]

    public static var templateOptions: TemplateOptions = {
        var o = TemplateOptions()
        o.categories = ["work", "home_logistics", "family_care", "social_exit",
                        "relationship_privacy", "travel_transition", "personal_boundaries",
                        "safety_discomfort"]
        o.personas = [
            TemplateOption(code: "manager", label: "your manager"),
            TemplateOption(code: "roommate", label: "your roommate"),
            TemplateOption(code: "best_friend", label: "your best friend"),
            TemplateOption(code: "partner", label: "your partner"),
        ]
        o.reasons = [
            TemplateOption(code: "work_urgent_task", label: "an urgent task"),
            TemplateOption(code: "home_problem", label: "a problem at home"),
            TemplateOption(code: "social_friend_outside", label: "waiting outside"),
        ]
        o.urgencies = ["low", "medium", "high", "immediate"]
        o.outcomes = [TemplateOption(code: "step_out_briefly", label: "Step out briefly"),
                      TemplateOption(code: "leave_now", label: "Leave now")]
        o.settings = [TemplateOption(code: "date", label: "Date"),
                      TemplateOption(code: "work_meeting", label: "Work meeting")]
        o.detailProfiles = ["minimal", "grounded", "contextual", "continuity"]
        o.discretionLevels = ["public_safe", "normal", "direct"]
        o.tones = ["warm", "casual", "professional", "firm"]
        o.formalities = ["casual", "neutral", "professional"]
        o.expectedResponses = [TemplateOption(code: "no_reply_needed", label: "No reply needed"),
                               TemplateOption(code: "say_on_my_way", label: "Say on my way")]
        o.followupBehaviors = [TemplateOption(code: "one_touch_only", label: "One touch only")]
        o.continuityScopes = ["one_off", "same_day", "weekend", "two_weeks"]
        o.contextModules = ["work", "home", "family", "relationship", "transition"]
        o.voiceStyles = ["neutral", "warm"]
        o.channels = [.call, .text]
        var p = ProfileOptions()
        p.workSettings = [TemplateOption(code: "site_field", label: "Site/field"),
                          TemplateOption(code: "office", label: "Office")]
        p.livingSetups = [TemplateOption(code: "with_roommate", label: "With roommate"),
                          TemplateOption(code: "alone", label: "Alone")]
        p.homeResponsibilities = [TemplateOption(code: "dog", label: "A dog"),
                                  TemplateOption(code: "keys_access", label: "Keys")]
        o.profile = p
        return o
    }()

    public static func profile(credits: Int = 3, activeRequest: RequestSummary? = nil) -> UserProfile {
        UserProfile(
            id: "user-1", locale: "en", timezone: "UTC",
            phone: VerifiedPhoneSummary(maskedNumber: "+14******123"),
            entitlements: EntitlementSummary(creditsAvailable: credits, planCodes: ["free"]),
            activeRequest: activeRequest
        )
    }

    public static func scheduledRequest(channel: Channel = .call, seconds: TimeInterval = 27) -> RequestSummary {
        RequestSummary(id: "req-1", channel: channel, status: .scheduled, scheduledKind: "delayed",
                       executeAt: Date().addingTimeInterval(seconds), requestedAt: Date(),
                       cancelable: true, lastErrorCode: nil)
    }

    public static let history: [HistoryEntry] = [
        HistoryEntry(id: "p1", channel: .call, templateLabel: "Boss — urgent work issue",
                     requestedAt: Date(), executeAt: Date().addingTimeInterval(180),
                     status: .scheduled, cancelable: true,
                     durationSeconds: nil, preview: nil),
        HistoryEntry(id: "h1", channel: .call, templateLabel: "Boss — urgent work issue",
                     requestedAt: Date().addingTimeInterval(-3600), status: .completed,
                     durationSeconds: 42, preview: "Brief call about a work issue."),
        HistoryEntry(id: "h2", channel: .text, templateLabel: "Best friend — needs you outside",
                     requestedAt: Date().addingTimeInterval(-7200), status: .completed,
                     durationSeconds: nil, preview: "I'm outside — come out for a sec?"),
        HistoryEntry(id: "h3", channel: .call, templateLabel: "Sibling — family check-in",
                     requestedAt: Date().addingTimeInterval(-90000), status: .canceled,
                     durationSeconds: nil, preview: nil),
    ]

    public static let creditPackages: [CreditPackage] = [
        CreditPackage(code: "credits_10", displayName: "10 Credits", credits: 10,
                      fulfillmentMode: "app_store_iap", priceLabel: "€4.99",
                      badgeText: nil, sortOrder: 10,
                      storeProductID: "com.believablecall.app.credits10"),
        CreditPackage(code: "credits_25", displayName: "25 Credits", credits: 25,
                      fulfillmentMode: "app_store_iap", priceLabel: "€9.99",
                      badgeText: "Popular", sortOrder: 20,
                      storeProductID: "com.believablecall.app.credits25"),
        CreditPackage(code: "credits_60", displayName: "60 Credits", credits: 60,
                      fulfillmentMode: "app_store_iap", priceLabel: "€19.99",
                      badgeText: "Best value", sortOrder: 30,
                      storeProductID: "com.believablecall.app.credits60"),
    ]
}

public final class MockAuthService: AuthServicing, @unchecked Sendable {
    public var startResult: PhoneStartResult
    public var session: Session
    public var startError: Error?
    public var confirmError: Error?
    public private(set) var startedPhone: String?
    public private(set) var confirmedCode: String?

    public init(startResult: PhoneStartResult = .init(verificationID: "vid-1", channel: "sms", expiresInSeconds: 600),
                session: Session = .init(token: "tok-1", userID: "user-1", maskedNumber: "+14******123")) {
        self.startResult = startResult
        self.session = session
    }

    public func start(phoneNumber: String, locale: String, deviceID: String?) async throws -> PhoneStartResult {
        startedPhone = phoneNumber
        if let startError { throw startError }
        return startResult
    }

    public func confirm(verificationID: String, code: String, deviceID: String?) async throws -> Session {
        confirmedCode = code
        if let confirmError { throw confirmError }
        return session
    }

    public func logout() async throws {}
}

public final class MockTemplateService: TemplateServicing, @unchecked Sendable {
    public var templates: [TemplateSummary]
    public var error: Error?
    public var createError: Error?
    public private(set) var deletedIDs: [String] = []
    public init(templates: [TemplateSummary] = Fixtures.templates) { self.templates = templates }
    public func list() async throws -> [TemplateSummary] {
        if let error { throw error }
        return templates
    }

    public func options() async throws -> TemplateOptions {
        if let error { throw error }
        return Fixtures.templateOptions
    }

    public func createCustom(_ draft: CustomTemplateDraft) async throws -> TemplateSummary {
        if let createError { throw createError }
        let created = TemplateSummary(
            id: "custom-\(templates.count + 1)", code: "custom_\(draft.persona)",
            displayName: draft.displayName, description: draft.description.isEmpty ? nil : draft.description,
            category: TemplateCategory(wireValue: draft.category), callerPersona: draft.persona,
            reasonCode: draft.reason, senderPersonaKey: draft.persona, senderDisplayName: draft.persona,
            supportsContactSave: true, isCustom: true, choices: draft, supportedChannels: draft.channels,
            callMaxDurationSeconds: draft.channels.contains(.call) ? draft.callMaxSeconds : nil,
            previewOpeningLine: draft.channels.contains(.call) ? "Hey, it's me. Got a minute?" : nil,
            previewSMSBody: draft.channels.contains(.text) ? "Call me when you can." : nil
        )
        templates.append(created)
        return created
    }

    public private(set) var updated: [(id: String, draft: CustomTemplateDraft)] = []

    public func update(id: String, _ draft: CustomTemplateDraft) async throws -> TemplateSummary {
        if let createError { throw createError }
        updated.append((id, draft))
        guard let index = templates.firstIndex(where: { $0.id == id }) else {
            throw APIError.api(code: "not_found", message: "Template not found.", retryable: false, requestID: nil)
        }
        let old = templates[index]
        let saved = TemplateSummary(
            id: old.isCustom || old.isEdited ? old.id : "edited-\(old.id)", code: old.code,
            displayName: draft.displayName,
            description: draft.description.isEmpty ? nil : draft.description,
            category: old.isCustom ? TemplateCategory(wireValue: draft.category) : old.category,
            callerPersona: draft.persona, reasonCode: draft.reason,
            isCustom: old.isCustom, isEdited: !old.isCustom,
            originalId: old.isCustom ? nil : (old.originalId ?? old.id), choices: draft,
            supportedChannels: draft.channels,
            callMaxDurationSeconds: draft.channels.contains(.call) ? draft.callMaxSeconds : nil,
            previewOpeningLine: draft.channels.contains(.call) ? "Hey, it's me. Got a minute?" : nil,
            previewSMSBody: draft.channels.contains(.text) ? "Call me when you can." : nil
        )
        if !old.isCustom && !old.isEdited { originals[saved.id] = old }
        templates[index] = saved
        return saved
    }

    /// Built-ins replaced by an edited copy, so a reset can bring them back.
    private var originals: [String: TemplateSummary] = [:]

    public func delete(id: String) async throws {
        deletedIDs.append(id)
        if let original = originals.removeValue(forKey: id),
           let index = templates.firstIndex(where: { $0.id == id }) {
            templates[index] = original
        } else {
            templates.removeAll { $0.id == id }
        }
    }
}

public final class MockRequestService: RequestServicing, @unchecked Sendable {
    public var created: RequestSummary
    public var createError: Error?
    public var cancelStatus: RequestStatus = .canceled
    public var cancelError: Error?
    public private(set) var lastDraft: RequestDraft?
    public private(set) var canceledIDs: [String] = []

    public init(created: RequestSummary = Fixtures.scheduledRequest()) { self.created = created }

    public func create(_ draft: RequestDraft) async throws -> RequestSummary {
        lastDraft = draft
        if let createError { throw createError }
        return created
    }

    public func get(id: String) async throws -> RequestSummary { created }

    public func cancel(id: String) async throws -> RequestSummary {
        if let cancelError { throw cancelError }
        canceledIDs.append(id)
        return RequestSummary(id: id, channel: created.channel, status: cancelStatus, scheduledKind: nil,
                              executeAt: created.executeAt, requestedAt: nil, cancelable: false, lastErrorCode: nil)
    }
}

public final class MockHistoryService: HistoryServicing, @unchecked Sendable {
    public var page: HistoryPage
    public var error: Error?
    public init(items: [HistoryEntry] = Fixtures.history, hasMore: Bool = false) {
        self.page = HistoryPage(items: items, hasMore: hasMore, nextOffset: items.count)
    }
    public func list(limit: Int, offset: Int) async throws -> HistoryPage {
        if let error { throw error }
        return page
    }
}

public final class MockProfileService: ProfileServicing, @unchecked Sendable {
    public var profile: UserProfile
    public var error: Error?
    public init(profile: UserProfile = Fixtures.profile()) { self.profile = profile }
    public func me() async throws -> UserProfile {
        if let error { throw error }
        return profile
    }
    public func update(locale: String?, timezone: String?) async throws -> UserProfile {
        if let error { throw error }
        if let locale { profile.locale = locale }
        if let timezone { profile.timezone = timezone }
        return profile
    }
    /// Stands in for the server's first-name list.
    public var knownFirstNames = ["Jana", "Jonas", "Julia", "Jürgen", "Mehmet"]
    public func setFirstName(_ name: String?) async throws -> UserProfile {
        if let error { throw error }
        if let name, !knownFirstNames.contains(name) {
            throw APIError.api(code: "unknown_first_name", message: "Pick a first name from the list.", retryable: false, requestID: nil)
        }
        profile.firstName = name
        return profile
    }
    public func firstNames(matching prefix: String) async throws -> [String] {
        if let error { throw error }
        return knownFirstNames.filter { $0.lowercased().hasPrefix(prefix.lowercased()) }
    }
    public private(set) var deleted = false
    public func deleteAccount() async throws {
        if let error { throw error }
        deleted = true
    }
}

public final class MockDeviceService: DeviceServicing, @unchecked Sendable {
    public private(set) var registered = false
    public init() {}
    public func register(deviceID: String, pushToken: String?, appVersion: String?, osVersion: String?) async throws {
        registered = true
    }
}

public final class MockContextProfileService: ContextProfileServicing, @unchecked Sendable {
    public var profile: ContextProfile
    public var error: Error?
    public init(profile: ContextProfile = ContextProfile()) { self.profile = profile }
    public func get() async throws -> ContextProfile {
        if let error { throw error }
        return profile
    }
    public func update(_ profile: ContextProfile) async throws -> ContextProfile {
        if let error { throw error }
        self.profile = profile
        return profile
    }
}

public final class MockContactsService: ContactsServicing, @unchecked Sendable {
    public var status: ContactAuthorization
    /// What `requestAccess()` resolves to when starting from `.notDetermined`.
    public var grantResult: ContactAuthorization
    public private(set) var requestAccessCalled = false

    public init(status: ContactAuthorization = .notDetermined,
                grantResult: ContactAuthorization = .authorized) {
        self.status = status
        self.grantResult = grantResult
    }

    public func authorizationStatus() -> ContactAuthorization { status }

    public func requestAccess() async -> ContactAuthorization {
        requestAccessCalled = true
        if status == .notDetermined { status = grantResult }
        return status
    }
}

public final class MockCreditPackagesService: CreditPackagesServicing, @unchecked Sendable {
    public var packages: [CreditPackage]
    public var listError: Error?
    public var acquireError: Error?
    public var costs: CreditCosts? = CreditCosts(call: 2, text: 1)
    public var firstPurchaseBonus = 3
    public private(set) var redeemed: [String] = []
    /// Running balance the mock reports after each grant, so view models can
    /// assert the post-grant value.
    public var balance: Int
    public private(set) var acquiredCodes: [String] = []

    public init(packages: [CreditPackage] = Fixtures.creditPackages, balance: Int = 3) {
        self.packages = packages
        self.balance = balance
    }

    public func catalog() async throws -> CreditCatalog {
        if let listError { throw listError }
        return CreditCatalog(packages: packages, costs: costs, firstPurchaseBonus: firstPurchaseBonus)
    }

    public func redeem(signedTransaction: String) async throws -> CreditAcquisition {
        if let acquireError { throw acquireError }
        redeemed.append(signedTransaction)
        let product = signedTransaction.split(separator: ":").dropFirst().first.map(String.init)
        let pack = packages.first { $0.storeProductID == product }
        let granted = (pack?.credits ?? 0) + firstPurchaseBonus
        firstPurchaseBonus = 0
        balance += granted
        return CreditAcquisition(claimID: "claim-\(signedTransaction)", status: "granted",
                                 grantedCredits: granted, creditsAvailable: balance,
                                 planCode: pack?.code ?? "")
    }

    public func acquire(code: String, clientRequestID: String) async throws -> CreditAcquisition {
        if let acquireError { throw acquireError }
        acquiredCodes.append(code)
        let credits = packages.first { $0.code == code }?.credits ?? 0
        balance += credits
        return CreditAcquisition(claimID: "claim-\(clientRequestID)", status: "granted",
                                 grantedCredits: credits, creditsAvailable: balance,
                                 planCode: code)
    }
}
