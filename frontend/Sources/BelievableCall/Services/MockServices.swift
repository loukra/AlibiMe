import Foundation

// Mock services for SwiftUI previews and unit tests. These are UI-development /
// test fixtures only; the running app always uses the Live* services against
// the real backend.

public enum Fixtures {
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

    public static func profile(credits: Int = 3, activeRequest: RequestSummary? = nil) -> UserProfile {
        UserProfile(
            id: "user-1", locale: "en", timezone: "UTC", displayName: "Alex",
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
    public init(templates: [TemplateSummary] = Fixtures.templates) { self.templates = templates }
    public func list() async throws -> [TemplateSummary] {
        if let error { throw error }
        return templates
    }
}

public final class MockRequestService: RequestServicing, @unchecked Sendable {
    public var created: RequestSummary
    public var createError: Error?
    public var cancelStatus: RequestStatus = .canceled
    public private(set) var lastDraft: RequestDraft?

    public init(created: RequestSummary = Fixtures.scheduledRequest()) { self.created = created }

    public func create(_ draft: RequestDraft) async throws -> RequestSummary {
        lastDraft = draft
        if let createError { throw createError }
        return created
    }

    public func get(id: String) async throws -> RequestSummary { created }

    public func cancel(id: String) async throws -> RequestSummary {
        RequestSummary(id: id, channel: created.channel, status: cancelStatus, scheduledKind: nil,
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
    public func update(locale: String?, timezone: String?, displayName: String?) async throws -> UserProfile {
        if let error { throw error }
        if let displayName { profile.displayName = displayName }
        if let locale { profile.locale = locale }
        if let timezone { profile.timezone = timezone }
        return profile
    }
}

public final class MockDeviceService: DeviceServicing, @unchecked Sendable {
    public private(set) var registered = false
    public init() {}
    public func register(deviceID: String, pushToken: String?, appVersion: String?, osVersion: String?) async throws {
        registered = true
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
